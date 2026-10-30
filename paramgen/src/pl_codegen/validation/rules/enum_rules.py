"""Rules for enumerations and the values that use them.  (Asked for.)

An enumeration becomes C - a typedef, one ``#define`` per value and an
``IS_VALID_<name>()`` macro - so its names follow the rules of C names, every
value has to fit the integer it is, and two values may not share a name or a
number.  A parameter of one has to name an enumeration its own sublist
declares, be of its base type and start at one of its values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from ...config import FORMAT_PARAM_TABLE
from ...errors import DiagnosticCollector, SourceLocation
from ...model.defines import COLUMN_PARAM_MODES, COLUMN_SYSTEM_NAMES
from ...model.enum_type import ENUM_BASE_TYPES, EnumType
from ...model.parameter_list import ParameterList
from ...model.types import resolve_value_type
from ...naming import is_reserved_keyword, is_valid_c_identifier
from .rule_base import ValidationRule, enabled_nodes


def _shown(list_file: Optional[str]) -> str:
    return Path(str(list_file)).name if list_file else "?"


class EnumTypeRule(ValidationRule):
    """Every enumeration of the build is something C can be given."""

    rule_id = "ENUM"
    description = ("An enumeration has a C name, an integer base type and at least one "
                   "value; its values have C names and numbers that fit, none twice.")

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        library = model.struct_types
        # the other #defines of the same header
        defines = {name: column for column in (COLUMN_SYSTEM_NAMES, COLUMN_PARAM_MODES)
                   for name in model.defines.get(column)}
        value_owner: Dict[str, str] = {}

        for enum_type in library.enums():
            owners = model.enum_owners.get(enum_type.name) or [None]
            where = SourceLocation(file=owners[0])
            self._check_name(enum_type, library, where, diagnostics)
            base = resolve_value_type(enum_type.base_type_name)
            if enum_type.base_type_name not in ENUM_BASE_TYPES or base is None:
                diagnostics.error(
                    "ENUM002",
                    f"Enumeration '{enum_type.name}' is a '{enum_type.base_type_name}', "
                    f"and an enumeration is an integer.",
                    where, hint=f"Make it one of {', '.join(ENUM_BASE_TYPES)}.")
                base = None
            if not enum_type.values:
                diagnostics.error(
                    "ENUM003", f"Enumeration '{enum_type.name}' has no values.", where,
                    hint="Give it at least one value ('Enum types…').")

            names: Dict[str, int] = {}
            numbers: Dict[int, str] = {}
            for item in enum_type.values:
                if not is_valid_c_identifier(item.name) or is_reserved_keyword(item.name):
                    diagnostics.error(
                        "ENUM004",
                        f"'{item.name}' in enumeration '{enum_type.name}' is not a C name; "
                        f"every value becomes a #define.", where,
                        hint="Use letters, digits and '_', do not start with a digit, "
                             "and do not use a C keyword.")
                if item.name in names:
                    diagnostics.error(
                        "ENUM005", f"Enumeration '{enum_type.name}' has '{item.name}' twice.",
                        where, hint="Give every value a name of its own.")
                names[item.name] = item.value
                if item.value in numbers:
                    diagnostics.error(
                        "ENUM006",
                        f"'{numbers[item.value]}' and '{item.name}' of enumeration "
                        f"'{enum_type.name}' are both {item.value}, so the code cannot tell "
                        f"them apart.", where,
                        hint="Give one of them another number.")
                else:
                    numbers[item.value] = item.name
                if base is not None and base.native_min is not None and not (
                        base.native_min <= item.value <= base.native_max):
                    diagnostics.error(
                        "ENUM007",
                        f"'{item.name}' of enumeration '{enum_type.name}' is {item.value}, "
                        f"which a {enum_type.base_type_name} cannot hold "
                        f"({int(base.native_min)} to {int(base.native_max)}).", where,
                        hint="Change the number, or give the enumeration a larger base type.")
                other = value_owner.get(item.name)
                if other is not None and other != enum_type.name:
                    diagnostics.error(
                        "ENUM008",
                        f"'{item.name}' is a value of both '{other}' and '{enum_type.name}'; "
                        f"the two #defines would collide.", where,
                        hint="Rename it in one of the two enumerations.")
                value_owner.setdefault(item.name, enum_type.name)
                if item.name in defines:
                    diagnostics.error(
                        "ENUM008",
                        f"'{item.name}' of enumeration '{enum_type.name}' is also in the "
                        f"'{defines[item.name]}' drop-down list; the two #defines would "
                        f"collide.", where,
                        hint="Rename the value, or the entry of the drop-down list.")

        # one enumeration, declared by two sublists
        for name, files in model.enum_owners.items():
            if len(files) > 1:
                diagnostics.error(
                    "ENUM009",
                    f"Enumeration '{name}' is declared by more than one parameter sublist: "
                    f"{', '.join(_shown(item) for item in files)}. An enumeration belongs "
                    f"to one sublist only.",
                    SourceLocation(file=files[-1]),
                    hint=f"Rename '{name}' in every sublist but one ('Enum types…'), or "
                         f"delete it where nothing uses it.")

    @staticmethod
    def _check_name(enum_type: EnumType, library, where: SourceLocation,
                    diagnostics: DiagnosticCollector) -> None:
        if not is_valid_c_identifier(enum_type.name) or is_reserved_keyword(enum_type.name):
            diagnostics.error(
                "ENUM001", f"'{enum_type.name}' is not a C name; it becomes a typedef.",
                where, hint="Use letters, digits and '_', and do not start with a digit.")
        if library.get(enum_type.name) is not None:
            diagnostics.error(
                "ENUM001",
                f"'{enum_type.name}' is both a structure type and an enumeration.",
                where, hint="Rename one of them.")


class EnumUseRule(ValidationRule):
    """A value of an enumeration names one of its own sublist, and fits it."""

    rule_id = "ENUM_USE"
    description = ("A parameter or field of an enumeration names one its sublist declares, "
                   "is of its base type and starts at one of its values.")

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        library = model.struct_types

        for use in model.foreign_enums:
            if not model.enum_owners.get(use.type_name):
                continue                    # declared nowhere: ENUM010 below says so
            here = _shown(use.list_file)
            owners = " and ".join(_shown(item) for item in model.enum_owners[use.type_name])
            what = (f"Field '{use.where}'" if use.in_type else f"'{use.where}'")
            diagnostics.error(
                "ENUM011",
                f"{what} of {here} is of enumeration '{use.type_name}', which {here} does "
                f"not declare - it is one of {owners}. A sublist uses only its own "
                f"enumerations.",
                SourceLocation(file=use.list_file, parameter=None if use.in_type else use.where),
                hint=f"Declare an enumeration in {here} ('Enum types…') and use that.")

        table = self.config.output.format == FORMAT_PARAM_TABLE
        for node in enabled_nodes(model):
            name = node.enum_type_name
            if not name:
                continue
            if table:
                diagnostics.error(
                    "ENUM013",
                    f"'{node.name}' is of enumeration '{name}', and a parameter table has "
                    f"no enumerations.", node.source,
                    hint="Give it a data type, or build this sublist as smart data.")
                continue
            enum_type = library.get_enum(name)
            if enum_type is None:
                if not model.enum_owners.get(name):
                    diagnostics.error(
                        "ENUM010",
                        f"'{node.name}' is of enumeration '{name}', which no sublist declares.",
                        node.source,
                        hint="Declare it ('Enum types…'), or give the parameter a data type.")
                continue
            if node.value_type_name != enum_type.base_type_name:
                diagnostics.error(
                    "ENUM014",
                    f"'{node.name}' is a '{node.value_type_name}', and enumeration "
                    f"'{name}' is a '{enum_type.base_type_name}'.", node.source,
                    hint="Choose the enumeration again as the data type; its base type "
                         "comes with it.")
            if node.is_primitive and node.default_value is not None \
                    and not enum_type.contains(node.default_value):
                diagnostics.error(
                    "ENUM015",
                    f"The default of '{node.name}' is {node.default_value}, which is none "
                    f"of the values of '{name}'.", node.source,
                    hint=f"Pick one of {', '.join(item.name for item in enum_type.values)}.")
