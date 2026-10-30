"""All validation rules.

To add a check: create a class deriving from :class:`ValidationRule` in this
folder and append it to :data:`ALL_RULES`.
"""

from __future__ import annotations

from typing import List, Type

from .defines_rules import DefinesSheetRule
from .enum_rules import EnumTypeRule, EnumUseRule
from .name_rules import (GeneratedIdentifierRule, IndexMacroCollisionRule, NameSyntaxRule,
                         NameUniquenessRule, StructRule)
from .range_rules import (DefaultInRangeRule, IntegralValueRule, MetadataRule,
                          MinMaxOrderRule, NativeRangeRule, RequiredValuesRule)
from .rule_base import ValidationRule
from .struct_type_rules import (StructTypeClashRule, StructTypeCycleRule,
                                StructTypeDeclarationRule, StructTypeOwnerRule,
                                StructTypeRule)
from .param_table_rules import (ParamTableAddressRule, ParamTableShapeRule,
                                ParamTableSystemRule, ParamTableSystemTagRule,
                                ParamTableTypeRule)
from .tag_rules import (FreeTagSyntaxRule, LogIdRule, MandatoryTagRule,
                        TagEnumValueRule, TagValueRangeRule, UserNameRule)
from .type_rules import (ArraySizeRule, ValueTypeRule, DeclaredTypeRule,
                         ParameterTypeRule)

#: Executed in this order; the order only affects the report, not the result.
ALL_RULES: List[Type[ValidationRule]] = [
    DefinesSheetRule,
    NameSyntaxRule,
    NameUniquenessRule,
    IndexMacroCollisionRule,
    GeneratedIdentifierRule,
    StructRule,
    StructTypeRule,
    StructTypeDeclarationRule,
    StructTypeCycleRule,
    StructTypeClashRule,
    StructTypeOwnerRule,
    EnumTypeRule,
    EnumUseRule,
    ValueTypeRule,
    DeclaredTypeRule,
    ParameterTypeRule,
    ArraySizeRule,
    NativeRangeRule,
    MinMaxOrderRule,
    DefaultInRangeRule,
    IntegralValueRule,
    RequiredValuesRule,
    MetadataRule,
    MandatoryTagRule,
    TagEnumValueRule,
    TagValueRangeRule,
    FreeTagSyntaxRule,
    UserNameRule,
    LogIdRule,
    # Only for a project whose output.format is 'param_table'; they do nothing
    # at all in the other one, which is what lets one list be judged by two
    # different sets of rules depending on who opened it.
    ParamTableShapeRule,
    ParamTableTypeRule,
    ParamTableAddressRule,
    ParamTableSystemRule,
    ParamTableSystemTagRule,
]

__all__ = ["ALL_RULES", "ValidationRule"]
