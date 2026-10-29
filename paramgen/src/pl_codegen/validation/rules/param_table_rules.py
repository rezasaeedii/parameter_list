"""Rules that only apply to the ``param_table`` format.

The older firmware's table is a flat list of single values.  It has no
structures, no arrays and no boolean type, and nothing in it is logged or
encrypted - so a parameter list that uses any of those is fine in a
``smart_data`` project and wrong in this one.

Every rule here begins by asking the project's format and does nothing at all
unless it is ``param_table``.  That is the whole mechanism behind "the same
list, opened by two projects, is judged by two different sets of rules": the
list is not the thing that changed, the project reading it is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from ...config import FORMAT_PARAM_TABLE
from ...codegen.files.param_table_h import ADDRESS_MAX, system_of
from ...errors import DiagnosticCollector, SourceLocation
from ...model.defines import COLUMN_SYSTEM_NAMES
from ...model.parameter import Parameter
from ...model.parameter_list import ParameterList
from .rule_base import ValidationRule, declared_values, enabled_nodes


class ParamTableRule(ValidationRule):
    """Base class: does nothing unless the project wants a parameter table."""

    @property
    def wanted(self) -> bool:
        return self.config.output.format == FORMAT_PARAM_TABLE


class ParamTableShapeRule(ParamTableRule):
    """No structures and no arrays: every row is one value."""

    rule_id = "PARAM_TABLE_SHAPE"
    description = "The parameter-table format has no structures and no arrays."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        if not self.wanted:
            return

        for parameter in enabled_nodes(model):
            if parameter.is_struct:
                diagnostics.error(
                    "PTB001",
                    f"'{parameter.name}' is a structure, and this project "
                    f"generates a parameter table, which has none.",
                    parameter.source,
                    hint="Every row of the table is one value. Replace the "
                         "structure with one parameter per field, or set "
                         "output.format to 'smart_data' in the project file.")
            elif parameter.array_size > 1:
                diagnostics.error(
                    "PTB002",
                    f"'{parameter.name}' has array size {parameter.array_size}, "
                    f"and a parameter table holds one value per row.",
                    parameter.source,
                    hint=f"Write {parameter.array_size} parameters instead, or "
                         f"set output.format to 'smart_data' in the project "
                         f"file.")


class ParamTableTypeRule(ParamTableRule):
    """The table's type enum has no boolean."""

    rule_id = "PARAM_TABLE_TYPE"
    description = "The parameter-table format has no boolean type."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        if not self.wanted:
            return

        for parameter in declared_values(model):
            value_type = parameter.value_type
            if value_type is not None and value_type.is_bool:
                diagnostics.error(
                    "PTB006",
                    f"'{parameter.name}' is a bool_t, and the parameter table "
                    f"has no boolean type.",
                    parameter.source,
                    hint="Use uint8_t with minimum 0 and maximum 1, which is "
                         "what the table's own rows do.")


class ParamTableAddressRule(ParamTableRule):
    """The address column holds a whole number the table can take."""

    rule_id = "PARAM_TABLE_ADDRESS"
    description = "Each parameter's Address is a whole number from 0 to 4294967295."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        if not self.wanted:
            return

        for parameter in model.parameters:
            address = parameter.address
            if isinstance(address, bool) or not isinstance(address, int) \
                    or not 0 <= address <= ADDRESS_MAX:
                diagnostics.error(
                    "PTB009",
                    f"'{parameter.name}' has address {address!r}, and an address is "
                    f"a whole number from 0 to {ADDRESS_MAX}.",
                    parameter.source,
                    hint="0 means the firmware places the parameter itself - the "
                         "usual value. Set a fixed address only where the table "
                         "needs one.")


class ParamTableSystemRule(ParamTableRule):
    """In this format the file name says which sub-system a list belongs to."""

    rule_id = "PARAM_TABLE_SYSTEM"
    description = "Each sub list's file name must name a known sub-system."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        if not self.wanted:
            return

        known = {name.upper() for name in model.defines.get(COLUMN_SYSTEM_NAMES)}
        seen: Set[str] = set()
        for path in self.config.inputs.model_files:
            if str(path) in seen:
                continue
            seen.add(str(path))

            system = system_of(path)
            if system in known:
                continue
            diagnostics.error(
                "PTB005",
                f"'{path.name}' does not name a sub-system: '{system}' is not "
                f"in the 'SYSTEM NAMES' list.",
                SourceLocation(file=str(path)),
                hint=f"In this format the file name says which sub-system the "
                     f"sub list is - name it '<system>_paramTable.xml', in any "
                     f"case. Known: {', '.join(sorted(known)) or 'none'}.")


class ParamTableSystemTagRule(ParamTableRule):
    """Every parameter of a list says the sub-system its file names.  (Reported.)

    The table's SYS column comes from the file name, so a tag that says
    otherwise changes nothing in this project.  But the list is the database,
    and a smart-data project reading the same file decides the sub-system by
    the tag.  The editor writes it into every list it opens and saves; this
    finds the lists of the build that have not been saved that way yet.
    """

    rule_id = "PARAM_TABLE_SYSTEM_TAG"
    description = ("Every parameter of a sub list carries its file's sub-system "
                   "in Tag System Name.")

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        if not self.wanted:
            return

        spelled = {str(name).upper(): name
                   for name in model.defines.get(COLUMN_SYSTEM_NAMES) or []}
        by_file: Dict[str, List[Parameter]] = {}
        for parameter in model.parameters:
            if parameter.source is not None and parameter.source.file:
                by_file.setdefault(parameter.source.file, []).append(parameter)

        for file, parameters in by_file.items():
            system = spelled.get(system_of(Path(file)))
            if system is None:
                continue            # the file names no sub-system: PTB005 says so
            wrong = [parameter for parameter in parameters
                     if parameter.tags.get("SystemName") != system]
            if not wrong:
                continue
            said = wrong[0].tags.get("SystemName") or "nothing"
            diagnostics.warning(
                "PTB008",
                f"{len(wrong)} parameter(s) of '{Path(file).name}' do not say "
                f"{system} in Tag System Name - '{wrong[0].name}' says '{said}'.",
                SourceLocation(file=file,
                               parameter=wrong[0].source.parameter or wrong[0].name),
                hint="In a parameter table the file name decides the sub-system, "
                     "and the editor writes it into every parameter of a sub list "
                     "it opens: open this sub list and save it. The tag is what a project "
                     "generating smart data from the same file uses.")
