"""Rules about the data type, the array size and the type of a parameter."""

from __future__ import annotations

from ...errors import DiagnosticCollector
from ...model.defines import COLUMN_TYPES, type_enum_member
from ...model.parameter_list import ParameterList
from ...model.types import resolve_value_type, supported_type_names
from .rule_base import ValidationRule, declared_values, enabled_leaves

#: Parameter types declared by ``parameter_descriptor.h``.  The diagnostic
#: codes keep their GRP prefix on purpose: a code is a stable identifier, and
#: the TYPE prefix already belongs to the rules about the *value* type.  A type listed in the
#: 'TYPES' drop-down list but not here would not compile.
KNOWN_TYPES = ("MONITORING", "SETTING", "COMMAND")

MAX_ARRAY_SIZE = 65535


class ValueTypeRule(ValidationRule):
    """The data type must be one of the supported primitive types."""

    rule_id = "TYPE"
    description = "Every value must have one of the supported data types."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            if not parameter.value_type_name:
                diagnostics.error(
                    "TYPE001", "No data type is set.", parameter.source,
                    hint=f"Pick one in the 'Value type' list ({supported_type_names()}). "
                         f"To hold other parameters instead of a value, make it a "
                         f"structure: '+ Add variable' > 'User defined…'.")
                continue
            if resolve_value_type(parameter.value_type_name) is None:
                diagnostics.error(
                    "TYPE002",
                    f"Data type '{parameter.value_type_name}' is not supported.",
                    parameter.source,
                    hint=f"Supported types: {supported_type_names()}. A structure is "
                         f"not a data type here: build it with '+ Add variable' > "
                         f"'User defined…' and give each field inside it one of these "
                         f"types.")


class DeclaredTypeRule(ValidationRule):
    """The data type should also be listed in the *Defines* sheet."""

    rule_id = "TYPE_DECLARED"
    description = "Data types should be listed in the 'TYPES' drop-down list."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        declared = model.defines.types
        if not declared:
            return
        for parameter in enabled_leaves(model):
            name = parameter.value_type_name
            if name and name not in declared and resolve_value_type(name) is not None:
                diagnostics.warning(
                    "TYPE003",
                    f"Data type '{name}' is not listed in the 'TYPES' column of the "
                    f"'TYPES' list.", parameter.source)


class ParameterTypeRule(ValidationRule):
    """The type must be one of the enumerators of ``eParameterType``."""

    rule_id = "PARAMETER_TYPE"
    description = "The parameter type must exist in parameter_descriptor.h."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        declared = model.defines.get(COLUMN_TYPES)
        for parameter in declared_values(model):
            if not parameter.param_type:
                diagnostics.error(
                    "GRP001",
                    "No type is set (and no structure above it sets one).",
                    parameter.source,
                    hint=f"Set 'Type' to one of {', '.join(KNOWN_TYPES)}. A field "
                         f"inherits the type of its structure, so setting it on the "
                         f"structure covers every field inside.")
                continue
            param_type = parameter.param_type.strip().upper()
            if param_type not in KNOWN_TYPES:
                diagnostics.error(
                    "GRP002",
                    f"Type '{parameter.param_type}' has no matching enumerator "
                    f"({type_enum_member(param_type)}) in parameter_descriptor.h.",
                    parameter.source,
                    hint=f"Known types: {', '.join(KNOWN_TYPES)}.")
            elif declared and parameter.param_type not in declared:
                diagnostics.warning(
                    "GRP003",
                    f"Type '{parameter.param_type}' is not in the 'TYPE' list.",
                    parameter.source)


class ArraySizeRule(ValidationRule):
    """The array size must be a sensible positive integer."""

    rule_id = "ARRAY"
    description = "Array sizes must be integers between 1 and 65535."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            size = parameter.array_size
            if size < 1:
                diagnostics.error(
                    "ARR001",
                    f"Array size {size} is invalid; it must be 1 or greater.",
                    parameter.source,
                    hint="Leave the cell empty for a scalar parameter.")
            elif size > MAX_ARRAY_SIZE:
                diagnostics.error(
                    "ARR002",
                    f"Array size {size} exceeds the maximum of {MAX_ARRAY_SIZE}.",
                    parameter.source,
                    hint=f"Every element becomes its own descriptor row, so this one "
                         f"parameter would be {size} rows. Split it into several "
                         f"parameters.")
