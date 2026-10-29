"""``MemoryOffset`` of every parameter, per tag.

Every tag owns an independent counter.  The rule is the same for all tags:

    the counter starts at 0 and, for every parameter that carries the tag,
    advances by  ``sizeof(value) * array size``

A parameter that does not carry the tag gets offset 0 and consumes nothing.

Example for the *Loggable* tag::

    P1  uint16_t          loggable       -> offset 0    (uses 2 bytes)
    P2  uint8_t           not loggable   -> no offset, uses nothing
    P3  uint64_t          loggable       -> offset 2    (uses 8 bytes)
    P4  uint32_t          loggable       -> offset 10   (uses 4 bytes)
    P5  uint16_t[4]       loggable       -> offset 14   (uses 8 bytes)
                                            total: 22 bytes

The sizes come from the C standard (``uint16_t`` is 2 bytes everywhere), so the
generated offsets are identical on every compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..model.parameter import Parameter, ParameterKind
from ..model.parameter_list import ParameterList
from ..model.tags import TAG_REGISTRY, TagSpec


def reserved_size(parameter: Parameter) -> int:
    """Bytes one parameter occupies inside the area of a tag it carries.

    This is a *memory* size, so it depends on the C type: a ``float64_t[4]``
    takes 32 bytes and a ``uint8_t[4]`` takes 4.  The number itself lives on the
    model, because a struct field has to add up its own members.
    """
    return parameter.reserved_size


def reserved_log_ids(parameter: Parameter) -> int:
    """How many consecutive log ids one parameter takes.

    A log id numbers a *value*, not a byte, so unlike :func:`reserved_size` this
    does not depend on the data type at all:

      * a scalar parameter always takes exactly one id, whether it is a
        ``uint8_t`` or a ``float64_t``;
      * an array takes one id per element, so a ``float64_t[10]`` starting at
        410 occupies 410..419 and the next free id is 420.

    Keeping the two rules apart matters: the memory map and the log stream are
    different things, and a log id that advanced by ``sizeof`` would leave big
    unusable gaps in the id space for no reason.
    """
    return max(1, parameter.array_size)


def log_id_span(parameter: Parameter) -> int:
    """How many consecutive log ids one *top level entry* occupies.

    For a plain value this is :func:`reserved_log_ids`.  For a structure it is
    the whole block: the entry's ``LogId`` is the first id, and every value
    inside it takes ids out of that block in tree order, so a structure with two
    fields, one of them a ``[4]`` array, and an array size of 3 occupies
    ``3 * (1 + 4) = 15`` ids.  Disabled nodes generate nothing and take none.
    """
    if not parameter.enable:
        return 0
    if parameter.kind is ParameterKind.STRUCT:
        inside = sum(log_id_span(child) for child in parameter.children)
        return max(1, parameter.array_size) * inside
    return reserved_log_ids(parameter)


@dataclass
class OffsetEntry:
    """The offset one parameter got inside the area of one tag."""

    tag_id: str
    parameter: Parameter
    offset: int
    size: int


@dataclass
class OffsetArea:
    """Everything allocated for a single tag."""

    tag: TagSpec
    entries: List[OffsetEntry] = field(default_factory=list)
    total: int = 0     #: total number of bytes used by this tag


class OffsetMap:
    """Lookup of ``(tag, parameter) -> offset``."""

    def __init__(self, areas: Dict[str, OffsetArea]) -> None:
        self._areas = areas
        self._lookup: Dict[Tuple[str, str], OffsetEntry] = {
            (entry.tag_id, entry.parameter.name): entry
            for area in areas.values() for entry in area.entries
        }

    @property
    def areas(self) -> Dict[str, OffsetArea]:
        return self._areas

    def area(self, tag_id: str) -> Optional[OffsetArea]:
        return self._areas.get(tag_id)

    def has_entry(self, tag_id: str, parameter_name: str) -> bool:
        return (tag_id, parameter_name) in self._lookup

    def offset(self, tag_id: str, parameter_name: str) -> int:
        entry = self._lookup.get((tag_id, parameter_name))
        return entry.offset if entry is not None else 0

    def size(self, tag_id: str, parameter_name: str) -> int:
        entry = self._lookup.get((tag_id, parameter_name))
        return entry.size if entry is not None else 0

    def total(self, tag_id: str) -> int:
        area = self._areas.get(tag_id)
        return area.total if area is not None else 0


def build_offset_map(model: ParameterList) -> OffsetMap:
    """Allocate an offset for every (parameter, tag) pair that carries the tag."""
    areas: Dict[str, OffsetArea] = {}

    for spec in TAG_REGISTRY:
        area = OffsetArea(tag=spec)
        cursor = 0

        for parameter in model.flatten():
            if not parameter.has_active_tag(spec.tag_id):
                continue
            step = reserved_size(parameter)
            area.entries.append(OffsetEntry(spec.tag_id, parameter, cursor, step))
            cursor += step

        area.total = cursor
        areas[spec.tag_id] = area

    return OffsetMap(areas)
