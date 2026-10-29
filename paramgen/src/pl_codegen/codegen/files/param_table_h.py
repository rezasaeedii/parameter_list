"""Builds ``nsrParamTables.h`` - the whole of the ``param_table`` output.

The older firmware has no smart data and no descriptor table.  It has one
header full of ``ADD_PARAM(...)`` lines, split per sub-system by
``#if DESIRED_SUB_SYSTEM == ...``, and the application defines what ``ADD_PARAM``
means before including it.  So this one builder is nearly the whole of that
format: no typedefs and no ``.c`` file.  Beside it are ``param_offsets_h.py``,
which writes a note - comments and nothing else - saying where in memory each
of these values ends up, and ``system_names_h.py``, which writes the
``SYS_...`` names this table's ``#if`` lines compare.

Two things are different enough from the other builders to be worth saying out
loud:

**The sub-system comes from the file name.**  ``sys_gs_manager_paramTable.xml``
is the parameter list of ``SYS_GS_MANAGER``.  The ``Tag System Name`` inside the
file is ignored here, which is exactly what lets one list be opened by a
``smart_data`` project - where that tag *is* what counts - and by this one.

**The index restarts at zero in every block.**  It numbers the parameters of one
sub-system, not of the build, because that is what the firmware's own table
does.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ...model.defines import COLUMN_PARAM_MODES
from ...model.parameter import Parameter
from ...model.types import CValueType
from ..literals import escape_string
from .file_builder import FileBuilder

#: The file this format produces.  Fixed: it is the name the firmware includes,
#: and a project that renamed it would simply not compile.
FILE_NAME = "nsrParamTables.h"

#: Dropped off the end of a list's file name to leave the sub-system.
NAME_SUFFIX = "_PARAMTABLE"

#: The macro the firmware sets to pick one sub-system, and the value that means
#: "all of them".
SELECTOR = "DESIRED_SUB_SYSTEM"
EVERYTHING = "SYS_ALL"

#: The two lines at the top of the hand-written file, kept word for word - they
#: are warnings to whoever edits the table, and they are still true.
WARNINGS = (
    "WARNING: Order of subsytems should comply SYS_GS_ enum "
    "(at least for last system)",
    "WARNING: DO NOT ADD NEW ITEMS BETWEEN OLD ITEM",
)

#: What each column of ADD_PARAM is, written above the table the way the
#: hand-written file writes it.
LEGEND = ("ADD_PARAM(data type, TYPE_ENUM, PR_NAME, \"gs name\", "
          "SYS_NAME, param index, default value, min, max, resolution, "
          "mode (0 is recommended), address (0 :: auto), \"description\")")

#: The value type as this format spells it.  ``float32_t`` and ``float64_t``
#: are the tool's names; the firmware's table calls them what C calls them.
_C_NAME = {"float32_t": "float", "float64_t": "double"}

#: The enum beside the type.  ``uint8_t`` -> ``TYPE_UINT8`` by dropping the
#: ``_t``, which works for every integer; the two floats are called what C
#: calls them rather than what the tool does.
_TYPE_ENUM = {"float32_t": "TYPE_FLOAT", "float64_t": "TYPE_DOUBLE"}

#: The biggest address accepted: one uint32_t, like every other number of the
#: descriptor.  The address is the parameter's own Address field - it used to be
#: read out of Tag1, which left Tag1 unable to mean what it means elsewhere.
ADDRESS_MAX = 0xFFFFFFFF

#: Tags an ``ADD_PARAM`` row has no column for.  Look at the generated file and
#: they are simply not in it: this format stores nothing itself and logs
#: nothing.  They stay in the parameter list, and they are set here like any
#: other tag, because the same list may be built by a smart-data project where
#: each of them decides something real.  One switched on is warned about.
IGNORED_TAGS = ("ResetProof", "Loggable", "LogEncryption")

#: And the tag this format takes from the FILE NAME instead of from the file.
FILE_OWNED_TAGS = ("SystemName",)

#: So: what the editor shows but will not let a parameter-table project change -
#: only the sub-system, which the file name decides and the editor writes into
#: every parameter.  The form renders it read-only and ``Document.update`` keeps
#: what the parameter already had, because a form that does not send a tag must
#: not clear it.  (Reset proof and the two logging tags used to be read-only too;
#: they are editable now - asked for.)
READ_ONLY_TAGS = FILE_OWNED_TAGS

#: How many columns one ADD_PARAM row has.
_COLUMNS = 13

#: Every column but the last is padded to a common width - the width of THE
#: WHOLE FILE, not of one block - so that every comma stands under the comma
#: above it from the first row of the table to the last, and a column can be
#: read down as easily as a row is read across.  The description is last, so
#: nothing is read after it and padding it would only put trailing spaces
#: before the ``)``.
_ALIGNED = _COLUMNS - 1


def system_of(list_file: Path) -> str:
    """``sys_gs_manager_paramTable.xml`` -> ``SYS_GS_MANAGER``.

    Upper-cased on both sides, so the case of the file name never matters:
    people write file names in lower case and system names in upper, and both
    spellings have to mean the same sub-system.
    """
    stem = Path(list_file).stem.upper().replace("-", "_").replace(" ", "_")
    if stem.endswith(NAME_SUFFIX):
        stem = stem[: -len(NAME_SUFFIX)]
    return stem.strip("_")


def blocks_by_system(parameters: List[Parameter],
                     model_files: Sequence[Path]) -> List[Tuple[str, List[Parameter]]]:
    """The parameters grouped by the list file they came from, in build order.

    Grouped by the file rather than by the ``Tag System Name``, because in this
    format the file *is* the sub-system.  The reader always records which file a
    parameter was read from, so this works on a merged model of any number of
    lists.

    It lives here, on its own, because two files are built from it - the table
    and the offsets note beside it - and they have to put the same parameters in
    the same sub-system in the same order, or the index in one would not be the
    index in the other.
    """
    order = [str(path) for path in model_files]
    grouped: Dict[str, List[Parameter]] = {}
    for parameter in parameters:
        grouped.setdefault(str(parameter.source.file or ""), []).append(parameter)

    # the configured order first, then anything else in the order it arrived -
    # a model built in memory has no configured files at all
    blocks: List[Tuple[str, List[Parameter]]] = []
    for source in order:
        if source in grouped:
            blocks.append((source, grouped.pop(source)))
    for source, rows in grouped.items():
        blocks.append((source, rows))
    return [(system_of(Path(source)), rows) for source, rows in blocks if rows]


def c_type_of(value_type: CValueType) -> str:
    return _C_NAME.get(value_type.c_name, value_type.c_name)


def type_enum_of(value_type: CValueType) -> str:
    name = value_type.c_name
    if name in _TYPE_ENUM:
        return _TYPE_ENUM[name]
    return "TYPE_" + name[:-2].upper() if name.endswith("_t") else "TYPE_" + name.upper()


def plain_number(value, fallback=0, floating: bool = False) -> str:
    """A number as the table writes it: no ``U``, no ``f``, no brackets.

    The smart-data code needs literals a C compiler cannot mistake - ``31U``,
    ``0.04f``, ``(-1)`` - because they are assigned to typed fields.  Here they
    are macro arguments in a hand-maintained-looking table, and the hand-written
    file writes them plainly.  Matching it keeps the generated file diffable
    against the one it replaces.

    A float parameter keeps its point even when the number is whole, because
    that is what the file being replaced does - ``70.0, -1000.0, 10000.0, 1.0``
    on a ``float`` row, ``31, 0, 255, 1`` on a ``uint8_t`` one - and a column
    of numbers is read by eye.
    """
    if value is None:
        value = fallback
    if isinstance(value, bool):
        return "1" if value else "0"
    number = float(value)
    if number.is_integer() and abs(number) < 1e16:
        return f"{int(number)}.0" if floating else str(int(number))
    # short, and exactly what was written: 0.04 stays 0.04
    text = repr(number)
    return text[:-2] if text.endswith(".0") else text


class ParamTableHeader(FileBuilder):
    """The single header the ``param_table`` format generates."""

    @property
    def file_name(self) -> str:
        return FILE_NAME

    def generate(self) -> str:
        text = ""

        # ---- banner ------------------------------------------------------
        text += self.banner.generate(
            self.file_name,
            "Parameter tables of every sub-system, as ADD_PARAM() lines.",
            self.generation_notes())
        text += "\n"

        # ---- the warnings and the legend ---------------------------------
        for line in WARNINGS:
            text += f"//{line}\n"
        text += "\n"
        text += f"//{LEGEND}\n"
        text += "\n"

        # ---- the access modes --------------------------------------------
        text += self._modes()

        # ---- one block per sub-system ------------------------------------
        #
        # Every row of the file is built before any of it is written, because
        # the columns are aligned across the WHOLE file: one long name in the
        # last sub-system widens that column in the first one too, and that is
        # what keeps every comma under the comma above it to the end of the
        # table.
        table = [(system, self._rows(system, parameters))
                 for system, parameters in self._blocks()]
        widths = self._widths([row for _, rows in table for row in rows])
        for system, rows in table:
            text += self._block(system, rows, widths)

        return text

    # -- the access modes --------------------------------------------------
    def _modes(self) -> str:
        """``#define PARAM_MODE_USER (0)`` for every mode, in order.

        Straight from the machine's drop-down list, numbered from zero in the
        order it is written - which is the order the firmware's own enum uses,
        so adding a mode in the middle renumbers the ones after it.  That is
        why the editor's list says to add new values at the end.
        """
        modes = self.model.defines.get(COLUMN_PARAM_MODES)
        if not modes:
            return ""
        # +5, so the value column lands exactly where the hand-written
        # file it replaces puts it and a diff of the two is empty here.
        width = max(len(name) for name in modes) + 5
        text = ""
        for index, name in enumerate(modes):
            text += f"#define {name:<{width}}({index})\n"
        return text + "\n"

    # -- the blocks --------------------------------------------------------
    def _blocks(self) -> List[Tuple[str, List[Parameter]]]:
        """This build's parameters, grouped into sub-systems."""
        return blocks_by_system(self.parameters, self.config.inputs.model_files)

    def _rows(self, system: str, parameters: List[Parameter]) -> List[List[str]]:
        """The cells of one block's rows, numbered from zero."""
        rows = [self._cells(parameter, system, index)
                for index, parameter in enumerate(parameters)]
        return [row for row in rows if row is not None]

    @staticmethod
    def _widths(rows: List[List[str]]) -> List[int]:
        """How wide each padded column has to be for the whole file."""
        return [max((len(row[column]) for row in rows), default=0)
                for column in range(_ALIGNED)]

    def _block(self, system: str, rows: List[List[str]],
               widths: List[int]) -> str:
        """One ``#if`` block, with its columns lined up.

        Aligned because the file is read far more often than it is generated: a
        table of three hundred rows is only searchable by eye when every column
        starts in the same place on every line.  The widths are the file's, so
        the columns keep going straight across a block boundary too.
        """
        text = f"#if {SELECTOR} == {system} || {SELECTOR} == {EVERYTHING}\n"
        for row in rows:
            # The value is padded and the comma comes after the padding, not
            # after the value: that is what puts every comma of the file under
            # the comma above it, all the way down, instead of only lining up
            # the place each column starts.
            padded = "".join(f"{value:<{widths[column]}}, "
                             for column, value in enumerate(row[:_ALIGNED]))
            text += f"ADD_PARAM({padded}{row[_ALIGNED]})\n"
        text += "\n#endif\n\n"
        return text

    # -- one ADD_PARAM line ------------------------------------------------
    def _cells(self, parameter: Parameter, system: str,
               index: int) -> Optional[List[str]]:
        value_type = parameter.value_type
        if value_type is None:
            # Validation has already refused this, by name.  Leaving the row out
            # rather than writing a broken one keeps the rest of the file
            # readable while it is fixed.
            return None

        return [
            c_type_of(value_type),
            type_enum_of(value_type),
            parameter.name,
            escape_string(parameter.user_name or parameter.name),
            system,
            str(index),
            # The limits as WRITTEN, not the effective ones: an empty minimum
            # and maximum mean "no range" here and are written 0 / 0, which is
            # what the hand-written table does.  Falling back to the type's
            # native range would put 18446744073709551615 in a column somebody
            # reads.
            plain_number(parameter.default_value, floating=value_type.is_float),
            plain_number(parameter.minimum, floating=value_type.is_float),
            plain_number(parameter.maximum, floating=value_type.is_float),
            plain_number(parameter.resolution, value_type.default_resolution,
                         floating=value_type.is_float),
            str(parameter.tags.get("ParamMode") or "0"),
            _address_of(parameter),
            escape_string(parameter.description or ""),
        ]


def _address_of(parameter: Parameter) -> str:
    """The ParamLib address: the parameter's own Address field, 0 unless set.

    Zero means "work it out yourself" to the firmware, which is what every
    parameter but the first of a sub-system wants.
    """
    address = parameter.address
    if isinstance(address, bool) or not isinstance(address, int):
        return "0"
    return str(address)
