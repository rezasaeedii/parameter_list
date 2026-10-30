"""Making every structure in a list match the type it names.

This is the half of structure types that people actually feel.  A type says
what fields there are; a parameter of that type has to *have* those fields, and
keep having them when the type changes.  Add ``Alt`` to ``Position`` and every
parameter of type ``Position`` grows an ``Alt`` - in the right place, with the
log ids after it shifted along, exactly as if it had been added by hand.

What the type owns
------------------
The field's name, what it holds, how many of it there are, and whether it is
enabled at all.  Those are re-applied from the type every time - every parameter
of a type has the same fields, which is what lets them share one C typedef.

What the parameter owns
-----------------------
Everything a *value* has: minimum, maximum, default, resolution and its log
id - and what the field MEANS in this use of the type: its
unit and its description.  One ``xyz`` type is a speed in one parameter and an
offset in another, so those two cannot be the type's.  All of it survives a
type change, matched up by field name - so renaming a field in the type is the
one edit that loses what went with it, which is the same thing that happens in
C++ when a member is renamed.
"""

from __future__ import annotations

from typing import List, Optional, Set

from .enum_type import fit_limits
from .parameter import Parameter, ParameterKind
from .types import resolve_value_type
from .struct_type import StructField, StructType, StructTypeLibrary


def apply_types(parameters: List[Parameter], library: StructTypeLibrary) -> None:
    """Reshape every structure in *parameters* to the type it names."""
    for parameter in parameters:
        _reshape(parameter, library, set())


def _reshape(node: Parameter, library: StructTypeLibrary, busy: Set[str]) -> None:
    if not node.is_struct:
        # A primitive has no fields.  One that still carries children is a
        # parameter somebody turned back into a value, and keeping them would
        # leave invisible rows in the generated table.
        node.children = []
        # A value of an enumeration takes its base type and its range from it.
        if node.enum_type_name:
            fit_limits(node, library.get_enum(node.enum_type_name))
        return

    struct_type = library.get(node.value_type_name)
    if struct_type is None:
        # An unknown type is reported by validation, with the name in it.  The
        # fields it already has are left exactly as they are: throwing away a
        # parameter's contents because a file is missing would turn a broken
        # reference into lost work.
        return

    if struct_type.name in busy:
        # A type that contains itself, directly or through another type.  There
        # is no shape to build, and validation says so by name; stopping here
        # is what keeps this from recursing until the stack runs out.
        return
    busy = busy | {struct_type.name}

    kept = {child.name: child for child in node.children}
    rebuilt: List[Parameter] = []
    for member in struct_type.fields:
        child = kept.get(member.name)
        if child is None:
            child = _new_field(member)
        _apply_field(child, member)
        _reshape(child, library, busy)
        rebuilt.append(child)
    node.children = rebuilt


def _new_field(member: StructField) -> Parameter:
    """A field this parameter did not have yet: shape only, no values."""
    return Parameter(name=member.name)


def _apply_field(child: Parameter, member: StructField) -> None:
    """Put the type's half onto *child*, leaving the parameter's half alone."""
    child.name = member.name
    child.value_type_name = member.value_type_name or None
    child.enum_type_name = member.enum_type_name or None
    child.array_size = max(1, int(member.array_size or 1))
    child.enable = bool(member.enable)
    # The unit and the description are left exactly as they are: they say what
    # the field means in THIS parameter, and a type has neither.

    # A field is part of one structure, so it never carries the classification
    # or the tags of its own - it takes the structure's.
    child.param_type = None
    child.tags = {}

    # Whether the field holds a value or more fields is the type's to say.
    child.kind = (ParameterKind.STRUCT if _names_a_struct(member)
                  else ParameterKind.PRIMITIVE)
    if child.is_struct:
        child.default_value = None
        child.minimum = None
        child.maximum = None
        child.resolution = None
        child.unit = None


def _names_a_struct(member: StructField) -> bool:
    """A field whose type is not one of the primitives names a structure."""
    name = member.value_type_name or ""
    return bool(name) and resolve_value_type(name) is None


def type_of(node: Parameter, library: StructTypeLibrary) -> Optional[StructType]:
    """The structure type *node* is an instance of, if it is one."""
    return library.get(node.value_type_name) if node.is_struct else None


def types_used_by(parameters: List[Parameter], library: StructTypeLibrary) -> StructTypeLibrary:
    """The types *parameters* really use, and the types those use, and so on.

    This is what the build's merged types file holds, beside the full
    parameter list: every structure type the project uses, and no more.  A type
    a list declares and nothing uses stays in that list's own types file - it
    is the list's until somebody deletes it - but it is not carried along into
    the project's.  Disabled structures count: they are in the full list too,
    and their type is what gives them a shape there.
    """
    wanted: Set[str] = set()

    def want(name: Optional[str]) -> None:
        struct_type = library.get(name)
        if struct_type is None or struct_type.name in wanted:
            return
        wanted.add(struct_type.name)
        for member in struct_type.fields:
            want(member.value_type_name)

    def walk(node: Parameter) -> None:
        if node.is_struct:
            want(node.value_type_name)
        for child in node.children:
            walk(child)

    for parameter in parameters:
        walk(parameter)
    return StructTypeLibrary([library.get(name).copy() for name in sorted(wanted)])
