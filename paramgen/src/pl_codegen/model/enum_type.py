"""Enumeration types: an integer that may hold only the values it names.  (Asked for.)

An enumeration is declared in a sublist's types file, beside its structure
types, and belongs to that sublist the same way::

    <EnumType name="eFlightMode" baseType="uint8_t">
      <Value name="FLIGHT_MODE_MANUAL" value="0" />
      <Value name="FLIGHT_MODE_HOLD" value="5" />
    </EnumType>

A parameter - or a structure field - of an enumeration is still a parameter of
its base type, ``valueType="uint8_t"``, with ``enumType="eFlightMode"`` beside
it.  So everything that works for a ``uint8_t`` works for it unchanged: its
smart data object, the ...ByIndex functions, the tag offsets, an older version
of the tool reading the file.  What the enumeration adds is generated:

* ``typedef uint8_t eFlightMode;`` - so the code can tell the type apart,
* one ``#define`` per value,
* ``IS_VALID_eFlightMode(value_)`` - every value compared, one by one,
* a check on the parameter's smart data object, so that every write refuses a
  number that is none of the values - the ones between them included.

The smart data range of such a parameter is the smallest to the largest value,
its resolution 1, and its default one of the values: :func:`fit_limits` keeps
the model that way, so every rule about limits holds for it as for any value.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:                      # pragma: no cover - typing only
    from .parameter import Parameter

#: The base types an enumeration may have: the integers.  A bool has two values
#: of its own already, and a float has no exact values to name.
ENUM_BASE_TYPES = ("uint8_t", "int8_t", "uint16_t", "int16_t",
                   "uint32_t", "int32_t", "uint64_t", "int64_t")

#: What an enumeration starts as.
DEFAULT_BASE_TYPE = "uint8_t"


@dataclass
class EnumValue:
    """One named value of an enumeration."""

    name: str
    value: int = 0

    def copy(self) -> "EnumValue":
        return replace(self)


@dataclass
class EnumType:
    """An enumeration: its C name, the integer it is, and the values it names."""

    name: str
    base_type_name: str = DEFAULT_BASE_TYPE
    values: List[EnumValue] = field(default_factory=list)

    def copy(self) -> "EnumType":
        return EnumType(name=self.name, base_type_name=self.base_type_name,
                        values=[item.copy() for item in self.values])

    @property
    def minimum(self) -> Optional[int]:
        return min((item.value for item in self.values), default=None)

    @property
    def maximum(self) -> Optional[int]:
        return max((item.value for item in self.values), default=None)

    def name_of(self, number: object) -> Optional[str]:
        """The name of the value *number*, or ``None`` when it is none of them."""
        try:
            wanted = int(float(number))          # 5, 5.0 and "5" alike
        except (TypeError, ValueError):
            return None
        if float(number) != wanted:
            return None
        return next((item.name for item in self.values if item.value == wanted), None)

    def number_of(self, name: str) -> Optional[int]:
        return next((item.value for item in self.values if item.name == name), None)

    def contains(self, number: object) -> bool:
        return self.name_of(number) is not None


def fit_limits(node: "Parameter", enum_type: Optional[EnumType]) -> None:
    """Give a value of *enum_type* the limits the enumeration decides.

    Its base type, a range from the smallest to the largest value and
    resolution 1; a value with no default yet gets the first value.  A default
    that is none of the values is left as it is - validation names it rather
    than this quietly picking another.  A parameter that names no enumeration,
    or one that does not exist, is left alone too: validation says so by name.
    """
    if enum_type is None or not enum_type.values:
        return
    node.value_type_name = enum_type.base_type_name
    node.minimum = enum_type.minimum
    node.maximum = enum_type.maximum
    node.resolution = 1
    if node.default_value is None or (isinstance(node.default_value, str)
                                      and not node.default_value.strip()):
        node.default_value = enum_type.values[0].value
