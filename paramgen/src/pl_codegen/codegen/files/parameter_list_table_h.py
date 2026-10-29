"""Builds ``cg_parameter_list_table.h``.

This file contains no code at all: it draws the parameter list as ASCII tables
inside comment blocks, so a developer can see the whole parameter list next to
the generated code without opening the tool that produced it.  Disabled entries
are shown too.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from typing import List

from ...layout.tag_offset import log_id_span, reserved_size
from ...model.parameter import Parameter
from ...model.tags import TAG_REGISTRY
from ...naming import strip_array_indices
from .file_builder import FileBuilder

BRIEF = "The parameter list, drawn as a table. Documentation only - no code."


class ParameterListTableHeader(FileBuilder):
    """Draws the parameter sheet and the tag sheet as ASCII tables."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._indices = None

    @property
    def file_name(self) -> str:
        return self.table_header

    def generate(self) -> str:
        text = ""

        # ---- banner and guards -----------------------------------------
        text += self.banner.generate(self.file_name, BRIEF, self.generation_notes())
        text += "\n"
        text += self.guard.generate_open(self.guard_name)
        text += "\n"
        text += self.cpp.generate_open()
        text += "\n"

        text += self.marker.generate("Includes")

        # ---- table 1: the value of every parameter -----------------------
        text += self.marker.generate("Exported defines")
        text += self.comment.generate_block(
            self.table.generate(self._value_rows()) + self._value_note(),
            title="Parameter list - values")
        text += "\n"

        # ---- table 2: the tag columns ------------------------------------
        text += self.comment.generate_block(
            self.table.generate(self._tag_rows()),
            title="Parameter list - tags")
        text += "\n"

        # ---- table 3: the MemoryOffset of every parameter, per tag --------
        text += self.comment.generate_block(
            self.table.generate(self._offset_rows()) + self._offset_note(),
            title="MemoryOffset of every parameter, per tag")
        text += "\n"

        text += self.marker.generate("Exported macros")
        text += self.marker.generate("Exported types")
        text += self.marker.generate("Exported functions")
        text += self.marker.generate("Exported variables")
        text += "\n"

        # ---- closing guards and footer ------------------------------------
        text += self.cpp.generate_close()
        text += "\n"
        text += self.guard.generate_close(self.guard_name)
        text += "\n"
        text += self.footer.generate()
        return text

    # -- table 1 : name, type, range ---------------------------------------
    def _value_rows(self) -> List[List[str]]:
        """One row per top level entry, plus the fields of every structure.

        The ``#`` column is the real index - the one the generated ``#define``
        holds - so it is taken from the flattened list rather than counted here.
        A structure has no index of its own (it is not a row of the table), and
        neither has a disabled entry; both show ``-``.
        """
        rows = [["Index", "En", "Name", "User Name", "Type", "ValueType", "Arr",
                 "Default", "Min", "Max", "Res", "Unit"]]
        for depth, path, parameter in self._all_entries():
            rows.append([
                self._index_of(path, parameter),
                "x" if parameter.enable else " ",
                "  " * depth + parameter.name,
                parameter.user_name or "-",
                (parameter.param_type or "-").upper(),
                "struct" if parameter.is_struct else (parameter.value_type_name or "-"),
                str(parameter.array_size),
                _number(parameter.default_value),
                _number(parameter.minimum),
                _number(parameter.maximum),
                _number(parameter.resolution),
                parameter.unit or "-",
            ])
        return rows

    # -- table 2 : the tags -------------------------------------------------
    def _tag_rows(self) -> List[List[str]]:
        """The tags, which belong to the top level entries and to nobody else.

        The log id is shown here too, because it is classification information
        the reader wants next to the tags - but it is not one of them, so it
        gets its own column rather than a place in the tag loop.
        """
        rows = [["Index", "Name"] + [spec.tag_id for spec in TAG_REGISTRY] + ["LogID range"]]
        for parameter in self.model.parameters:
            row = [self._index_of(parameter.name, parameter), parameter.name]
            for spec in TAG_REGISTRY:
                row.append(_tag(parameter.tags.get(spec.tag_id)))
            row.append(self._log_id_range(parameter))
            rows.append(row)
        return rows

    def _all_entries(self):
        """``(depth, dotted path, node)`` for every node of the tree, in order."""
        def walk(nodes, depth, prefix):
            for node in nodes:
                path = f"{prefix}.{node.name}" if prefix else node.name
                yield depth, path, node
                yield from walk(node.children, depth + 1, path)

        return list(walk(self.model.parameters, 0, ""))

    def _index_of(self, path: str, parameter: Parameter) -> str:
        """The table index of a node, or ``-`` when it has none.

        A struct array has several: its first element's index is the useful one
        to show, and the range says how many follow.
        """
        if parameter.is_struct or not parameter.enable:
            return "-"
        try:
            return str(self._index_by_path[path])
        except KeyError:
            return "-"

    @property
    def _index_by_path(self):
        """``dotted tree path -> index`` for every value in the table.

        The leaves of a struct array carry an element index in their name
        (``Wheels[1].Speed``), which the tree above does not; the first element
        is the one that answers "where does this row start".
        """
        if self._indices is None:
            self._indices = {}
            for index, leaf in enumerate(self.parameters):
                self._indices.setdefault(strip_array_indices(leaf.name), index)
        return self._indices

    def _log_id_range(self, parameter: Parameter) -> str:
        """The ids this entry occupies - a count of values, never of bytes.

        A ``float64_t[10]`` at 410 occupies 410..419, exactly as a
        ``uint8_t[10]`` would: a log id numbers a value, and the type of the
        value plays no part in it.
        """
        log_id = parameter.log_id
        if not isinstance(log_id, int) or isinstance(log_id, bool):
            return "-"
        span = log_id_span(parameter)
        if span <= 1:
            return str(log_id)
        return f"{log_id}..{log_id + span - 1}"

    # -- table 3 : the offsets ---------------------------------------------
    def _offset_rows(self) -> List[List[str]]:
        tags = [spec for spec in TAG_REGISTRY
                if self.offsets.area(spec.tag_id) and self.offsets.area(spec.tag_id).entries]
        rows = [["Index", "Name", "Bytes"] + [spec.tag_id for spec in tags]]

        for index, parameter in enumerate(self.parameters):
            row = [str(index), parameter.name, str(reserved_size(parameter))]
            for spec in tags:
                if self.offsets.has_entry(spec.tag_id, parameter.name):
                    row.append(str(self.offsets.offset(spec.tag_id, parameter.name)))
                else:
                    row.append("-")
            rows.append(row)

        totals = ["", "TOTAL (bytes)", ""]
        totals.extend(str(self.offsets.total(spec.tag_id)) for spec in tags)
        rows.append(totals)
        return rows

    def _value_note(self) -> List[str]:
        note = [
            "",
            "'Index' is the index in the parameter list, the value of the matching",
            "#define in the defines header. A structure is not a row of the table,",
            "so it has no index of its own; only the values inside it have one.",
        ]
        if any(node.is_array for _path, node in self.model.struct_parameters()):
            note += [
                "A structure with an array size is expanded element by element, so",
                "the index shown for one of its fields is that of the FIRST element;",
                "the next elements follow one full set of fields apart.",
            ]
        return note

    @staticmethod
    def _offset_note() -> List[str]:
        return [
            "",
            "Every tag owns an independent counter that starts at 0 and advances by",
            "sizeof(value) * array size for every parameter that carries the tag.",
            "'-' means the tag is not active for that parameter, so its offset is 0.",
        ]


def _number(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _tag(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "x" if value else " "
    return str(value)
