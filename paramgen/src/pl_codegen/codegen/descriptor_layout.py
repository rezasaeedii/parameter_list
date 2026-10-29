"""Field order of ``sParameterDescriptor``.

The generated initialiser uses *designated initialisers in declaration order*,
which is valid in C99 **and** in C++20.  The order below therefore has to match
``parameter_descriptor.h`` exactly.
"""

from __future__ import annotations

from typing import List

from ..model.tags import TAG_REGISTRY

FIELD_NAME = "pName"
#: The name a person reads - one per VALUE, so an element of an array or a
#: field of a structure may read differently from the rest.
FIELD_USER_NAME = "pUserName"
FIELD_TYPE = "Type"
FIELD_SMART_DATA = "pSmartData"
#: The log id.  It sits with the plain scalars and *before* the tags, because
#: it is not one: a tag is classification a parameter carries, and a log id is
#: not that - it numbers a value in the log stream, nothing else.
FIELD_LOG_ID = "LogId"
FIELD_DESCRIPTION = "pDescription"

#: Fields that come before the tag fields, in declaration order.
#:
#: There is deliberately no ArraySize and no pUnit here.  One descriptor is one
#: *value*: an array declaration produces one row per element, so a count would
#: always be 1, and the unit lives on the smart data object so that a value
#: carries it wherever it is passed.
LEADING_FIELDS: List[str] = [FIELD_NAME, FIELD_USER_NAME, FIELD_TYPE, FIELD_SMART_DATA,
                             FIELD_LOG_ID]

#: Fields that come after the tag fields, in declaration order.
TRAILING_FIELDS: List[str] = [FIELD_DESCRIPTION]


def descriptor_field_order() -> List[str]:
    """Full field order of ``sParameterDescriptor``."""
    return LEADING_FIELDS + [spec.descriptor_field for spec in TAG_REGISTRY] + TRAILING_FIELDS
