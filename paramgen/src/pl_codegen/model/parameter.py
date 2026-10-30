"""In-memory description of a single parameter.

A parameter is either a **primitive** (it holds one value, possibly an array of
values) or a **struct** (it holds other parameters, which may themselves be
structs).  The tree can be nested as deeply as needed.

**Tags and the type belong to the top level entry**, never to a field inside a
structure.  A structure is one thing that belongs to one subsystem, is reset
proof or is not, and is logged or is not; its fields are the smart-data objects
that make it up, and they all share that classification.  So a field carries
only what is really its own: name, type, array size, unit, limits, description.


The code generator never walks the tree itself: it asks
:meth:`~pl_codegen.model.parameter_list.ParameterList.flatten` for the list of
*leaves*, where every leaf is a primitive with a dotted name such as
``Position.Home.Lat``.  That keeps the generated descriptor table exactly the
same shape it had before structs existed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Iterator, List, Optional, Sequence, Union

from ..errors import SourceLocation
from .types import CValueType, resolve_value_type

#: Value a tag can hold once it has been read from the GUI / XML.
TagValue = Union[bool, int, str, None]

#: Numeric value of a parameter (default / min / max / resolution).
NumericValue = Union[int, float, bool, None]


def element_key(indices: Sequence[int]) -> str:
    """The key a value's own description is kept under: its element path.

    ``Speed[3]`` is "3", ``Wheels[1].Speed`` is "1" and
    ``Wheels[1].Samples[5]`` is "1.5"; a value that is nobody's element is "".
    Only arrays count, so a scalar structure adds nothing to the path.
    """
    return ".".join(str(int(index)) for index in indices)


def nearest_text(entries: Dict[str, str], own: Optional[str],
                 indices: Sequence[int]) -> Optional[str]:
    """The text of the nearest row at or above *indices* that has one.

    *entries* are a node's per-row texts, keyed by element path; *own* is the
    node's declaration's.  ``(1, 5)`` asks "1.5" first - the value
    Wheels[1].Samples[5] - then "1" - the row Wheels[1].Samples - and the
    declaration last.  ``None`` when none of them says anything.
    """
    for length in range(len(indices), 0, -1):
        text = entries.get(element_key(indices[:length]))
        if text and text.strip():
            return text
    return own if (own or "").strip() else None


class ParameterKind(Enum):
    """What a parameter is."""

    PRIMITIVE = "primitive"   #: holds a value of a supported C type
    STRUCT = "struct"         #: holds other parameters


@dataclass
class Parameter:
    """One node of the parameter tree."""

    name: str
    kind: ParameterKind = ParameterKind.PRIMITIVE
    enable: bool = True
    #: The name a person reads - in the ground station, in a log, in an
    #: agreement document.
    user_name: Optional[str] = None
    param_type: Optional[str] = None
    value_type_name: Optional[str] = None
    #: The enumeration this value is, when it is one - ``value_type_name`` is
    #: then its base type, so the value is a plain integer to everything else.
    #: See :mod:`pl_codegen.model.enum_type`.  (Asked for.)
    enum_type_name: Optional[str] = None
    array_size: int = 1
    default_value: NumericValue = None
    minimum: NumericValue = None
    maximum: NumericValue = None
    resolution: NumericValue = None
    unit: Optional[str] = None
    #: Identifier the logging sub-system uses for this value.  Not a tag: it
    #: has no offset area of its own and is a plain ``uint16_t`` in the
    #: descriptor.  ``None`` means "no id given".
    log_id: Optional[int] = None
    #: The parameter table's address column (``ADD_PARAM``'s "address").  0 means
    #: the firmware places the parameter itself.  Kept by every list whatever
    #: its project generates, so a list has the same fields in both formats; only
    #: a parameter-table project shows it.
    address: int = 0
    tags: Dict[str, TagValue] = field(default_factory=dict)
    description: Optional[str] = None
    #: Descriptions that belong to ONE ROW of the grid instead of to the whole
    #: declaration, keyed by the element path from the top level entry: "3" is
    #: Speed[3], "1" is Wheels[1] - or Wheels[1].Speed on the field - and "1.5"
    #: is Wheels[1].Samples[5].  "1" on Samples is the row Wheels[1].Samples,
    #: which says what every Samples value of THAT wheel means.  Indices rather
    #: than names, so renaming a parameter cannot orphan them.
    #:
    #: A value reads the nearest row at or above it that says something: its
    #: own, then the rows it is under, up to the top level declaration - so a
    #: text written on a row reaches everything under it EXCEPT what somebody
    #: has already written something for.  (Asked for: a row used to reach the
    #: same field in every element.)  See ``_collect`` in parameter_list.py.
    element_descriptions: Dict[str, str] = field(default_factory=dict)
    #: User Names that belong to ONE row, keyed and read exactly like
    #: :attr:`element_descriptions`.
    element_user_names: Dict[str, str] = field(default_factory=dict)
    children: List["Parameter"] = field(default_factory=list)
    source: SourceLocation = field(default_factory=SourceLocation)

    #: filled in by :meth:`ParameterList.flatten` - the C expression that
    #: reaches this leaf, e.g. ``Cg_SmartData_Position.Home.Lat``
    c_object: Optional[str] = None

    #: filled in by :meth:`ParameterList.flatten` - which element of an array
    #: declaration this leaf is, or ``None`` when the declaration is a scalar.
    #: Every element of an array is its own row of the descriptor table, so this
    #: is what turns ``Cg_SmartData_PosDrone`` into ``...PosDrone[2]``.
    element_index: Optional[int] = None

    #: filled in by :meth:`ParameterList.flatten` - how many elements the
    #: *declaration* this leaf came from has.  The array size belongs to the
    #: declaration, not to the value: it sizes the C object and the size macro,
    #: and every element of one declaration reports the same number.
    declared_array_size: int = 1

    #: filled in by :meth:`ParameterList.flatten` - the declaration this leaf's
    #: array size macro is named after.  A field's array belongs to its
    #: structure TYPE - every parameter of the type has the same one - so a
    #: value of ``MyStr.alive``, with ``MyStr`` of type ``Stest``, says
    #: ``Stest.alive`` (``STEST_ALIVE_ARRAY_SIZE``); a top level value says its
    #: own name.
    array_declaration: Optional[str] = None

    # -- what kind of node is this ---------------------------------------
    @property
    def is_struct(self) -> bool:
        return self.kind is ParameterKind.STRUCT

    @property
    def is_primitive(self) -> bool:
        return self.kind is ParameterKind.PRIMITIVE

    @property
    def value_type(self) -> Optional[CValueType]:
        """Resolved data type, or ``None`` for a struct/unknown type."""
        return resolve_value_type(self.value_type_name) if self.is_primitive else None

    @property
    def is_array(self) -> bool:
        return self.array_size > 1

    @property
    def range_disabled(self) -> bool:
        """True when this value is not meant to have an allowed range.

        Writing a zero minimum **and** a zero maximum means "the whole range of
        the type", as the module specification requires.  Leaving both cells
        empty means the same thing - the user simply did not ask for a range.

        What that turns into in the generated code is the *native* range of the
        C type, never ``0, 0``: the smart-data constructor refuses a default
        value outside ``[min, max]``, so ``0, 0`` would make every value with a
        non-zero default fail at run time.
        """
        return _is_zero_or_empty(self.minimum) and _is_zero_or_empty(self.maximum)

    @property
    def effective_minimum(self) -> NumericValue:
        """The minimum the generated constructor will actually be given."""
        return self._effective_limit(self.minimum, native=True, low=True)

    @property
    def effective_maximum(self) -> NumericValue:
        """The maximum the generated constructor will actually be given."""
        return self._effective_limit(self.maximum, native=True, low=False)

    def _effective_limit(self, value: NumericValue, native: bool, low: bool) -> NumericValue:
        value_type = self.value_type
        if value_type is None or not value_type.has_range:
            return None
        if self.range_disabled and native:
            return value_type.native_min if low else value_type.native_max
        # only one of the two cells was filled in: the empty one counts as zero
        return 0 if value is None else value

    @property
    def reserved_size(self) -> int:
        """Bytes this value occupies: ``sizeof(value) * array size``.

        This one number is how far it moves the ``MemoryOffset`` counter of
        every tag it carries.  It is not what a log id counts: a log id numbers
        values, not bytes - see ``reserved_log_ids`` in ``layout/tag_offset.py``.
        """
        value_type = self.value_type
        if value_type is None:
            return 0
        return value_type.value_size * max(1, self.array_size)

    # -- tags -------------------------------------------------------------
    def tag(self, tag_id: str) -> TagValue:
        return self.tags.get(tag_id)

    def effective_tag(self, tag_id: str) -> TagValue:
        """The value of a tag as the generated code will see it."""
        return self.tags.get(tag_id)

    @property
    def effective_log_id(self) -> Optional[int]:
        """The log id as the generated code will see it.

        The log id belongs to logging, so it exists only while ``Tag Loggable``
        is TRUE.  A number left behind on a value that is not logged means
        nothing - it must not reserve an id, must not clash with anything, and
        must not appear in the generated table.
        """
        from .tags import LOGGABLE_TAG

        if not self.has_active_tag(LOGGABLE_TAG):
            return None
        return self.log_id

    def has_active_tag(self, tag_id: str) -> bool:
        """Whether this value *carries* the tag.

        This is what decides whether it takes up room in that tag's offset
        area.

        A boolean tag is carried when it is TRUE.  Any other tag is carried
        whenever a value is written, **including zero**: 0 is a perfectly good
        enumerator, and treating it as "no tag" would leave the value out of
        that tag's offset area and shift every offset after it.
        """
        value = self.effective_tag(tag_id)
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return True
        return str(value).strip() != ""

    # -- tree helpers ------------------------------------------------------
    def walk(self) -> Iterator["Parameter"]:
        """Yield this node and every node below it."""
        yield self
        for child in self.children:
            yield from child.walk()

    def enabled_children(self) -> List["Parameter"]:
        return [child for child in self.children if child.enable]

    def copy_as_leaf(self, dotted_name: str, c_object: str,
                     tags: Dict[str, TagValue]) -> "Parameter":
        """A flat copy of this leaf, as the code generator wants to see it.

        ``log_id`` is deliberately dropped: unlike the tags it is not inherited
        but *handed out*, one id per value, by
        :func:`~.parameter_list._distribute_log_ids` right after this.  Keeping
        the field's own number here would let a value that the editor never
        showed a log id for smuggle a stale one into the generated table.
        """
        return replace(self, name=dotted_name, c_object=c_object, tags=dict(tags),
                       log_id=None, children=[], element_descriptions={},
                       element_user_names={})

    def description_at(self, indices: Sequence[int]) -> Optional[str]:
        """The description of ONE value: its own if it has one, else this node's.

        *indices* is the element path of the value, outermost array first:
        ``Wheels[1].Samples[5]`` asks with ``(1, 5)`` and a scalar asks with
        ``()``.
        """
        return self.element_descriptions.get(element_key(indices), self.description)

    def user_name_at(self, indices: Sequence[int]) -> Optional[str]:
        """The User Name of ONE value: its own if it has one, else this node's.

        The same element path as :meth:`description_at`.  ``None`` when neither
        says anything - the structure this node is in may still name it.
        """
        own = self.element_user_names.get(element_key(indices))
        if own:
            return own
        return self.user_name if (self.user_name or "").strip() else None

    def user_name_over(self, indices: Sequence[int]) -> Optional[str]:
        """The User Name this node gives the value or row at *indices*.

        The nearest of its rows that has one - see :func:`nearest_text` - else
        the declaration's.  ``None`` when this node says nothing there: the
        rows above it, in the structures it is in, may still name it.
        """
        return nearest_text(self.element_user_names, self.user_name, indices)

    def description_over(self, indices: Sequence[int]) -> Optional[str]:
        """The description this node gives the value or row at *indices*.

        Read exactly like :meth:`user_name_over`.
        """
        return nearest_text(self.element_descriptions, self.description, indices)

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        if self.is_struct:
            return f"Parameter({self.name}, struct, {len(self.children)} field(s))"
        return f"Parameter({self.name}, {self.value_type_name}, x{self.array_size})"


def _is_zero_or_empty(value: NumericValue) -> bool:
    """An empty cell and a zero mean the same thing for a limit."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return float(value) == 0.0
