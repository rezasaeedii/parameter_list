"""The drop-down lists: the allowed values for the enum-like fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

#: Names of the drop-down lists.
COLUMN_TYPES = "TYPE"
COLUMN_VALUE_TYPES = "VALUE TYPES"
COLUMN_SYSTEM_NAMES = "SYSTEM NAMES"
COLUMN_PARAM_MODES = "PARAM MODES"
COLUMN_BOOLEANS = "BOOLEANS"

#: Lists whose names are written into the smart-data header as ``#define``s,
#: each with a number of its own.  They used to be two ``typedef enum``s, which
#: numbered them by their place in the list and clashed with a firmware that
#: defines ``SYS_NAV`` itself; a define can be given any number, and is only
#: written ``#ifndef`` it is defined already.  (Asked for.)
GENERATED_DEFINES: Tuple[str, ...] = (COLUMN_SYSTEM_NAMES, COLUMN_PARAM_MODES)

#: The largest number one of them can have: it is stored in a uint32_t tag.
DEFINE_NUMBER_MAX = 0xFFFFFFFF

#: The smallest: a negative number is allowed too, as far as an int32_t goes.
#: The tag still holds 32 bits, so -1 is stored as 0xFFFFFFFF - exactly what C
#: makes of ``(uint32_t)(-1)`` - and the firmware's ``tag == SYS_TEST`` holds.
#: (Asked for.)
DEFINE_NUMBER_MIN = -0x80000000


def define_tag_value(number: int) -> int:
    """What the uint32_t tag holds for *number*: -1 and 0xFFFFFFFF are one value."""
    return number & DEFINE_NUMBER_MAX


@dataclass
class Defines:
    """Allowed values collected from every parameter list of the project."""

    values: Dict[str, List[str]] = field(default_factory=dict)
    #: The numbers written for the names of a :data:`GENERATED_DEFINES` list,
    #: ``{column: {name: number}}`` - only the ones somebody gave.  A name
    #: without one is the number of the name above it plus one, the first 0:
    #: exactly what the enum used to give, so a list nobody numbered keeps the
    #: numbers it always had.  See :meth:`numbered`.
    numbers: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def add(self, column: str, value: str) -> None:
        bucket = self.values.setdefault(column.upper(), [])
        if value not in bucket:
            bucket.append(value)

    def get(self, column: str) -> List[str]:
        return self.values.get(column.upper(), [])

    def contains(self, column: str, value: str) -> bool:
        return value in self.get(column)

    def number_of(self, column: str, name: str) -> Optional[int]:
        """The number somebody gave *name*, or ``None`` when it takes the next one."""
        return self.numbers.get(column.upper(), {}).get(name)

    def numbered(self, column: str) -> List[Tuple[str, int]]:
        """``(name, number)`` for every name of the list, in order.

        A name without a number of its own takes the one after the name above
        it - ``SYS_A = 5`` then ``SYS_B`` makes ``SYS_B`` 6 - and the first
        takes 0.
        """
        result: List[Tuple[str, int]] = []
        following = 0
        for name in self.get(column):
            given = self.number_of(column, name)
            number = given if given is not None else following
            result.append((name, number))
            following = number + 1
        return result

    def merge(self, other: "Defines") -> None:
        for column, entries in other.values.items():
            for entry in entries:
                self.add(column, entry)
        for column, given in other.numbers.items():
            mine = self.numbers.setdefault(column, {})
            for name, number in given.items():
                mine.setdefault(name, number)

    @property
    def param_types(self) -> List[str]:
        return self.get(COLUMN_TYPES)

    @property
    def types(self) -> List[str]:
        return self.get(COLUMN_VALUE_TYPES)

    @property
    def system_names(self) -> List[str]:
        return self.get(COLUMN_SYSTEM_NAMES)

    @property
    def param_modes(self) -> List[str]:
        return self.get(COLUMN_PARAM_MODES)


def type_enum_member(param_type: str) -> str:
    """``MONITORING`` -> ``ePARAMETER_TYPE_MONITORING`` (see parameter_descriptor.h)."""
    return f"ePARAMETER_TYPE_{param_type.strip().upper()}"
