"""Structure types - the ``struct`` declarations of the parameter list.

A structure type is exactly what it is in C++::

    struct Position {
        float64_t Lat;
        float64_t Lon;
        int16_t   Samples[8];
    };

It says **what fields there are, what they are called and what they hold**, and
nothing else.  Deliberately *not* part of a type:

  * minimum, maximum, default value, resolution - these are the range one
    particular value may take, and two parameters of the same type routinely
    want different ones.  A C++ struct declaration carries none of them either;
  * tags, the parameter type, the log id, the user name - all of these
    describe a parameter, and a type is not a parameter;
  * the unit and the description of a field.  They say what one USE of the
    type means: one ``xyz`` is a speed in one parameter and an offset in
    another, and a type that owned them would force both to share one unit.
    The type has no description of its own either - every parameter of it
    already has one.

That split is the whole point.  Before this, a "type" was a copy: pressing it
duplicated a structure's fields into a parameter and the two then had nothing
to do with each other, so adding a field to the type left every parameter
already built from it behind.  Now a parameter *names* its type, and changing
the type changes every parameter that names it.

Where they live
---------------
Next to every parameter list ``foo.xml`` is ``foo_types.xml``, holding the
types that list declares.  That is what makes a list portable: hand the two
files to another project and the structures come with them.

A type belongs to the one list that declares it.  No other list sees it or may
use it, and one name declared by two lists is an error (TYP016): the merged
types file the build writes beside the full parameter list - the union of every
list's types - can hold one of them only, and so can the C typedef made from
it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from .enum_type import EnumType


@dataclass
class StructField:
    """One member of a structure type.

    ``value_type_name`` is a primitive (``float32_t``) or the name of another
    structure type - C++ allows both, and a list that already nests structures
    needs both.
    """

    name: str
    value_type_name: str = ""
    array_size: int = 1
    #: The enumeration the field is, when it is one; ``value_type_name`` is
    #: then its base type.  (Asked for.)
    enum_type_name: str = ""
    #: Whether the field is generated at all.  The type's to say, not a
    #: parameter's: every parameter of a type has the same fields, which is
    #: what lets them share one C typedef.
    enable: bool = True

    def copy(self) -> "StructField":
        return replace(self)


@dataclass
class StructType:
    """A ``struct`` declaration: a name and the fields inside it."""

    name: str
    fields: List[StructField] = field(default_factory=list)

    def copy(self) -> "StructType":
        return StructType(name=self.name,
                          fields=[member.copy() for member in self.fields])

    def field_named(self, name: str) -> Optional[StructField]:
        return next((member for member in self.fields if member.name == name), None)

    @property
    def shape(self) -> tuple:
        """What this type *is*: each field's name, data type, array size and
        whether it is enabled, in order.

        A structure written before types existed is given the type of its list
        whose shape it has, rather than a second copy of it (see
        ``struct_migration``).
        """
        return tuple((member.name, member.value_type_name, member.array_size,
                      member.enable)
                     for member in self.fields)

    def __str__(self) -> str:      # pragma: no cover - debugging helper
        return f"StructType({self.name}, {len(self.fields)} field(s))"


class StructTypeLibrary:
    """The structure types one model knows, by name.

    A name identifies a type, so this is a mapping and not a list: defining
    ``Position`` twice is not two types, it is one type declared twice, and the
    second declaration either agrees with the first or is a mistake somebody
    has to be told about.
    """

    def __init__(self, types: Optional[List[StructType]] = None,
                 enums: Optional[List[EnumType]] = None) -> None:
        self._types: Dict[str, StructType] = {}
        for struct_type in types or []:
            self._types[struct_type.name] = struct_type
        #: The enumerations of the same list - kept here, beside the structure
        #: types, because they live in the same file and travel the same way.
        self._enums: Dict[str, EnumType] = {}
        for enum_type in enums or []:
            self._enums[enum_type.name] = enum_type

    # -- reading -----------------------------------------------------------
    def __len__(self) -> int:
        """Structure types and enumerations: whether the types file has anything in it."""
        return len(self._types) + len(self._enums)

    def __iter__(self):
        return iter(self.all())

    def __contains__(self, name: object) -> bool:
        return str(name) in self._types

    def all(self) -> List[StructType]:
        """Every type, in the order a person would look for one: by name."""
        return [self._types[name] for name in sorted(self._types)]

    def names(self) -> List[str]:
        return sorted(self._types)

    def get(self, name: Optional[str]) -> Optional[StructType]:
        return self._types.get(str(name)) if name else None

    # -- writing -----------------------------------------------------------
    def put(self, struct_type: StructType) -> None:
        """Add or replace one type."""
        self._types[struct_type.name] = struct_type

    def remove(self, name: str) -> bool:
        return self._types.pop(name, None) is not None

    def rename(self, old: str, new: str) -> bool:
        """Rename a type, keeping its place in the library."""
        struct_type = self._types.pop(old, None)
        if struct_type is None:
            return False
        struct_type.name = new
        self._types[new] = struct_type
        return True

    def copy(self) -> "StructTypeLibrary":
        return StructTypeLibrary([item.copy() for item in self.all()],
                                 [item.copy() for item in self.enums()])

    # -- enumerations ------------------------------------------------------
    def enums(self) -> List[EnumType]:
        """Every enumeration, by name."""
        return [self._enums[name] for name in sorted(self._enums)]

    def enum_names(self) -> List[str]:
        return sorted(self._enums)

    def get_enum(self, name: Optional[str]) -> Optional[EnumType]:
        return self._enums.get(str(name)) if name else None

    def put_enum(self, enum_type: EnumType) -> None:
        """Add or replace one enumeration."""
        self._enums[enum_type.name] = enum_type

    def remove_enum(self, name: str) -> bool:
        return self._enums.pop(name, None) is not None

    def rename_enum(self, old: str, new: str) -> bool:
        enum_type = self._enums.pop(old, None)
        if enum_type is None:
            return False
        enum_type.name = new
        self._enums[new] = enum_type
        return True

    # -- merging -----------------------------------------------------------
    def merge(self, other: "StructTypeLibrary") -> List[str]:
        """Take in *other*'s types; return every name this library already had.

        A structure type belongs to the one list that declares it, so a name
        that arrives twice is a clash even when both declarations say the same
        thing - it used to be "one shared type" then, and a list could reshape
        another list's structures without either of them being open.  The first
        declaration is kept, and the clash is returned to be reported rather
        than resolved: only a person can say which list should rename theirs.
        """
        clashes: List[str] = []
        for struct_type in other.all():
            if struct_type.name in self._types:
                clashes.append(struct_type.name)
            else:
                self._types[struct_type.name] = struct_type.copy()
        # an enumeration belongs to one list just the same
        for enum_type in other.enums():
            if enum_type.name in self._enums:
                clashes.append(enum_type.name)
            else:
                self._enums[enum_type.name] = enum_type.copy()
        return clashes

    def uses_of(self, name: str) -> List[str]:
        """Which types have a field of type *name* - what a rename must follow."""
        return [item.name for item in self.all()
                if any(member.value_type_name == name for member in item.fields)]
