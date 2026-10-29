"""The whole parameter list: a tree of parameters plus the allowed values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, NamedTuple, Optional, Sequence, Tuple

from dataclasses import replace

from .defines import Defines
from .parameter import Parameter, ParameterKind, TagValue
from .struct_type import StructType, StructTypeLibrary
from .types import resolve_value_type

#: separator between a struct and its field in a flattened name
PATH_SEPARATOR = "."


class ForeignType(NamedTuple):
    """A structure type one list uses without declaring it itself.

    Each list owns its structure types, so this is always a mistake - a list
    edited by hand, or one whose ``_types.xml`` did not come along.
    """

    list_file: str      #: the list that uses it
    where: str          #: the structure, or ``Type.field`` for a field of a type
    type_name: str      #: the structure type it names
    in_type: str = ""   #: the list's own type the field belongs to; "" for a structure

# The log id is not a tag and is not copied to the leaves: it is spread over
# them, one id per value.  See _distribute_log_ids.


@dataclass
class ParameterList:
    """All parameters of the project, as a tree."""

    parameters: List[Parameter] = field(default_factory=list)
    defines: Defines = field(default_factory=Defines)
    source_files: List[str] = field(default_factory=list)
    generator_version: str = ""
    generated_at: str = ""

    #: The structure types this list declares - its ``struct`` declarations.  A
    #: structure parameter *names* one of these, and changing the type changes
    #: every parameter that names it.  They are stored in ``foo_types.xml``
    #: next to the list, so a list carries its structures with it.
    struct_types: StructTypeLibrary = field(default_factory=StructTypeLibrary)

    #: Type names more than one of the merged lists declares.  Filled in by
    #: :meth:`extend`; validation turns them into errors (TYP016), because a
    #: type belongs to one list and only a person can say which one.
    type_clashes: List[str] = field(default_factory=list)

    #: For a merged list: which list files declare each type name, in build
    #: order - what a clash message names.  Filled in by :func:`merge_lists`.
    type_owners: Dict[str, List[str]] = field(default_factory=dict)

    #: For a merged list: structures and fields that name a structure type
    #: their own list does not declare (TYP017).  Filled in by
    #: :func:`merge_lists`, while each list can still be told apart.
    foreign_types: List[ForeignType] = field(default_factory=list)

    # -- collection behaviour -------------------------------------------
    def __iter__(self) -> Iterator[Parameter]:
        return iter(self.parameters)

    def __len__(self) -> int:
        return len(self.parameters)

    def add(self, parameter: Parameter) -> None:
        self.parameters.append(parameter)

    def extend(self, other: "ParameterList") -> None:
        """Append another parameter sub list to this one.

        The result is exactly what one big list would have been: the order of
        the sub lists decides the order of the indices, and the drop-down lists
        are merged.  Duplicate names or overlapping log ids across sub lists are
        found by the normal validation afterwards, which names the file each
        parameter came from.
        """
        self.parameters.extend(other.parameters)
        self.defines.merge(other.defines)
        for name in other.source_files:
            if name not in self.source_files:
                self.source_files.append(name)
        # A type belongs to the list that declares it, so a name both lists
        # declare is a clash whatever the two say - kept to be reported, not
        # resolved here.  The first declaration is the one the merge keeps.
        for name in self.struct_types.merge(other.struct_types):
            if name not in self.type_clashes:
                self.type_clashes.append(name)

    # -- the tree ---------------------------------------------------------
    def walk(self) -> Iterator[Parameter]:
        """Every node of the tree, parents before children."""
        for parameter in self.parameters:
            yield from parameter.walk()

    @property
    def enabled(self) -> List[Parameter]:
        """Top level parameters that take part in code generation."""
        return [parameter for parameter in self.parameters if parameter.enable]

    @property
    def disabled(self) -> List[Parameter]:
        return [parameter for parameter in self.parameters if not parameter.enable]

    def find(self, dotted_name: str) -> Optional[Parameter]:
        """Look a node up by its dotted path, e.g. ``Position.Home.Lat``."""
        nodes = self.parameters
        found: Optional[Parameter] = None
        for part in dotted_name.split(PATH_SEPARATOR):
            found = next((node for node in nodes if node.name == part), None)
            if found is None:
                return None
            nodes = found.children
        return found

    def assign_paths(self) -> None:
        """Write the dotted path of every node into its ``source.parameter``.

        Diagnostics then always tell the user *which* parameter they are about,
        and the GUI can jump straight to it.
        """
        for parameter in self.parameters:
            _stamp(parameter, [])

    # -- flattening --------------------------------------------------------
    def flatten(self) -> List[Parameter]:
        """Every enabled *leaf*, with a dotted name and a C access expression.

        A struct contributes no entry of its own; only its fields do.  Every
        leaf of a top level entry gets **that entry's** tags and type - a
        structure is classified as one thing, and its fields inherit the
        classification without being able to contradict it.

        The log id is not copied, because it identifies a single value and is
        not a tag at all.  A structure's log id is the *first* id of a block,
        and the leaves take consecutive ids out of it, one per value - so an
        array takes one id per element and the data type plays no part at all
        (see :func:`_distribute_log_ids`).
        """
        self.assign_paths()
        leaves: List[Parameter] = []
        for parameter in self.enabled:
            first = len(leaves)
            _collect(parameter, [], dict(parameter.tags), parameter.param_type, leaves)
            _distribute_log_ids(leaves[first:], parameter)
        return leaves

    def struct_parameters(self) -> List[Tuple[str, Parameter]]:
        """Every enabled struct as ``(dotted path, node)``, deepest first.

        Deepest first is the order the C typedefs have to be emitted in: an
        inner structure must be declared before the structure that uses it.
        """
        found: List[Tuple[str, Parameter]] = []
        for parameter in self.enabled:
            _collect_structs(parameter, [], found)
        return found

    def array_nodes(self) -> List[Tuple[str, Parameter]]:
        """Every enabled node that is an array, as ``(dotted path, node)``.

        This is the list the ``..._ARRAY_SIZE`` macros are made from, and it is
        deliberately built from the *tree* rather than from the leaves: an array
        size describes a declaration.  ``Wheels[0].Samples`` and
        ``Wheels[1].Samples`` are two values of one declaration, so the tree
        holds ``Wheels.Samples`` once and one macro is emitted for it.
        Structures are included, because a struct array is a real C array.
        """
        found: List[Tuple[str, Parameter]] = []
        for parameter in self.enabled:
            _collect_arrays(parameter, [], found)
        return found

    def struct_types_in_use(self) -> List[StructType]:
        """The structure types the enabled structures use - each once, inner first.

        One C ``typedef`` per TYPE, not per parameter: ``MyStr`` and ``MyStr2``
        of type ``Stest`` are two instances of ``sCgStruct_Stest``, the way two
        variables of one C++ type are.  Inner first, because a type used as a
        field of another has to be declared before the type that uses it.  A
        field the type has switched off does not count - it is not in the
        typedef either.
        """
        ordered: List[StructType] = []
        seen: set = set()

        def visit(name: Optional[str]) -> None:
            struct_type = self.struct_types.get(name)
            if struct_type is None or struct_type.name in seen:
                return
            seen.add(struct_type.name)          # before the fields: no loops
            for member in struct_type.fields:
                if member.enable:
                    visit(member.value_type_name)
            ordered.append(struct_type)

        for _path, node in self.struct_parameters():
            visit(node.value_type_name)
        return ordered

    def structures_by_type(self) -> Dict[str, List[Tuple[str, Parameter]]]:
        """Type name -> the enabled structures of that type, as ``(path, node)``."""
        found: Dict[str, List[Tuple[str, Parameter]]] = {}
        for path, node in self.struct_parameters():
            found.setdefault(node.value_type_name or "", []).append((path, node))
        return found

    def array_declarations(self) -> List[Tuple[str, int, Optional[Parameter]]]:
        """Every array DECLARATION - what an ``..._ARRAY_SIZE`` macro is named after.

        ``(declaration name, element count, node a problem is reported on)``.
        An array size belongs to whoever declares the array:

          * a top level parameter's own array belongs to that parameter -
            ``MyStr`` with three elements is ``MY_STR_ARRAY_SIZE``;
          * an array field belongs to its structure TYPE, because every
            parameter of the type has the same one - ``Stest.alive`` is
            ``STEST_ALIVE_ARRAY_SIZE``, declared once however many parameters
            use ``Stest``.
        """
        found: List[Tuple[str, int, Optional[Parameter]]] = []
        for parameter in self.enabled:
            if parameter.is_array:
                found.append((parameter.name, parameter.array_size, parameter))
        users = self.structures_by_type()
        for struct_type in self.struct_types_in_use():
            reported_on = users.get(struct_type.name, [("", None)])[0][1]
            for member in struct_type.fields:
                if member.enable and member.array_size > 1:
                    found.append((f"{struct_type.name}{PATH_SEPARATOR}{member.name}",
                                  member.array_size, reported_on))
        return found

    # -- views used by the code generator ---------------------------------
    def used_data_type_suffixes(self) -> List[str]:
        suffixes: List[str] = []
        for leaf in self.flatten():
            value_type = leaf.value_type
            if value_type is not None and value_type.suffix not in suffixes:
                suffixes.append(value_type.suffix)
        return suffixes

    def by_name(self) -> Dict[str, Parameter]:
        return {parameter.name: parameter for parameter in self.parameters}


def merge_lists(parts: Sequence[Tuple[object, ParameterList]]) -> ParameterList:
    """The parameter lists of one build, merged in build order, as one list.

    *parts* is ``(list file, the list read from it)`` in the order of
    ``inputs.model_files`` - which is the order of the generated indices, so the
    generator and the editor merge through here and cannot disagree about it.

    Every list owns its structure types: its ``_types.xml`` holds them and no
    other list may use them.  Two things about that can only be seen here,
    while each list is still on its own, and both are recorded on the result
    for validation to report rather than resolved:

      * ``type_owners`` - which lists declare each type name, so that a name
        two of them declare (``type_clashes``, TYP016) names both;
      * ``foreign_types`` - a structure, or a field of one of a list's own
        types, naming a structure type that list does not declare (TYP017).
    """
    merged = ParameterList()
    owners: Dict[str, List[str]] = {}
    foreign: List[ForeignType] = []
    for index, (source, part) in enumerate(parts):
        list_file = str(source)
        for name in part.struct_types.names():
            owners.setdefault(name, []).append(list_file)
        foreign.extend(_undeclared_types(part, list_file))
        if index == 0:
            merged = part
        else:
            merged.extend(part)
    merged.type_owners = owners
    merged.type_clashes = [name for name, files in owners.items() if len(files) > 1]
    merged.foreign_types = foreign
    return merged


def _undeclared_types(part: ParameterList, list_file: str) -> List[ForeignType]:
    """The structure types *part* uses without declaring them itself.

    A structure whose own type is missing is reported once: its fields take
    their shape from that type, so what they name is the same mistake again.
    """
    own = part.struct_types
    found: List[ForeignType] = []

    def walk(node: Parameter, prefix: str) -> None:
        if not node.enable:
            return
        path = f"{prefix}{PATH_SEPARATOR}{node.name}" if prefix else node.name
        if node.is_struct and node.value_type_name and own.get(node.value_type_name) is None:
            found.append(ForeignType(list_file, path, node.value_type_name))
            return
        for child in node.children:
            walk(child, path)

    for parameter in part.parameters:
        walk(parameter, "")
    for struct_type in own.all():
        for member in struct_type.fields:
            wanted = member.value_type_name
            if wanted and resolve_value_type(wanted) is None and own.get(wanted) is None:
                found.append(ForeignType(list_file,
                                         f"{struct_type.name}{PATH_SEPARATOR}{member.name}",
                                         wanted, struct_type.name))
    return found


def _collect(node: Parameter, path: List[str], tags: Dict[str, TagValue],
             param_type: Optional[str], leaves: List[Parameter],
             owner_type: Optional[str] = None,
             indices: Tuple[int, ...] = (),
             inherited_user_name: Optional[str] = None,
             inherited_description: Optional[str] = None) -> None:
    """Walk one node and append its leaves to *leaves*.

    *path* is how the value is reached from the top level entry, written the way
    C writes it - ``['Wheels[1]', 'Speed']``.  *tags* and *param_type* come from
    the top level entry and are handed down unchanged: a field never overrides
    them.  *owner_type* is the structure type that declares *node* - ``None`` at
    the top level - because an array field's size belongs to that type.

    *inherited_user_name* and *inherited_description* are what the rows above
    *node* say for the element it is in: the nearest of Wheels[1], Wheels and
    so on that says anything.  A value reads its own rows first - its own text,
    then the row of its array in this element - and these after that.  So a
    text written on a row reaches every value under it that has none of its
    own, and nothing outside it: Wheels[1].Samples names the samples of wheel 1
    and no other wheel's.  (Asked for, for the User Name and the description
    alike.)
    """
    if not node.enable:
        return

    count = max(1, node.array_size)

    if node.kind is ParameterKind.STRUCT:
        # An array of structures is expanded element by element: the same field
        # of two elements is not adjacent in memory (the elements are strided by
        # sizeof(struct)), so one entry could never describe them all.
        for index in range(count):
            element = path + [node.name if count == 1 else f"{node.name}[{index}]"]
            # Only an ARRAY adds a number to the element path: a scalar
            # structure is one thing, so Wheels.Samples[5] of a single Wheels
            # asks for "5" and of Wheels[1] asks for "1.5".
            inside = indices + ((index,) if count > 1 else ())
            for child in node.children:
                _collect(child, element, tags, param_type, leaves,
                         owner_type=node.value_type_name or node.name,
                         indices=inside,
                         inherited_user_name=(node.user_name_over(inside)
                                              or inherited_user_name),
                         inherited_description=(node.description_over(inside)
                                                or inherited_description))
        return

    # A primitive array is expanded the same way, and for the same reason the
    # descriptor no longer carries an ArraySize: **every row of the table is one
    # value**.  'PosDrone' with an array size of 4 is four rows - PosDrone[0] ..
    # PosDrone[3] - each with its own index, its own offsets and its own log id,
    # so a reader of the table never has to ask "how many values is this row?".
    # The C object stays a real array (Cg_SmartData_PosDrone[4]); it is only the
    # table that gained a row per element.
    for index in range(count):
        # The logical name and the C access expression are the same text on
        # purpose: a value is called what it is written as, so a diagnostic
        # about 'Wheels[1].Speed' names something the reader can paste straight
        # into a debugger.
        leaf_name = node.name if count == 1 else f"{node.name}[{index}]"
        dotted = PATH_SEPARATOR.join(path + [leaf_name])

        leaf = node.copy_as_leaf(dotted, dotted, tags)
        leaf.param_type = param_type
        # Each value may say what IT means and what it is called; the rest read
        # the nearest row above them that does.
        value = indices + ((index,) if count > 1 else ())
        leaf.description = node.description_over(value) or inherited_description
        leaf.user_name = node.user_name_over(value) or inherited_user_name
        # One row is one value.  The array size stays on the *declaration* (it
        # is what sizes the C object and what the size macro reports), but a row
        # that described N values would put the ArraySize field back in through
        # the side door.
        leaf.array_size = 1
        leaf.element_index = index if count > 1 else None
        leaf.declared_array_size = count
        leaf.array_declaration = (f"{owner_type}{PATH_SEPARATOR}{node.name}"
                                  if owner_type else node.name)
        leaves.append(leaf)


def _distribute_log_ids(block: List[Parameter], root: Parameter) -> None:
    """Give every leaf of one top level entry its own log id.

    The entry's ``log_id`` is the first id of the block; each leaf then takes
    one id per value - its array size - in tree order::

        Position          log_id = 400
          Home.Lat        float64_t     -> 400
          Home.Lon        float64_t     -> 401
          Alt             float32_t     -> 402
          Samples         int16_t[8]    -> 403 .. 410

    For a plain value the block holds a single leaf, so it simply keeps the id
    that was entered - exactly as before structures existed.
    """
    first = root.log_id
    if not isinstance(first, int) or isinstance(first, bool):
        return

    cursor = first
    for leaf in block:
        leaf.log_id = cursor
        # one id per value, exactly as for a plain parameter: a log id numbers a
        # value, not a byte, so the type plays no part
        cursor += max(1, leaf.array_size)


def _stamp(node: Parameter, path: List[str]) -> None:
    path = path + [node.name]
    node.source = replace(node.source, parameter=PATH_SEPARATOR.join(path))
    for child in node.children:
        _stamp(child, path)


def _collect_arrays(node: Parameter, path: List[str],
                    found: List[Tuple[str, Parameter]]) -> None:
    """Append every enabled array node below (and including) *node*."""
    if not node.enable:
        return
    path = path + [node.name]
    if node.is_array:
        found.append((PATH_SEPARATOR.join(path), node))
    for child in node.children:
        _collect_arrays(child, path, found)


def _collect_structs(node: Parameter, path: List[str],
                     found: List[Tuple[str, Parameter]]) -> None:
    """Append struct nodes as ``(dotted path, node)``, children before parent."""
    if not node.enable or node.kind is not ParameterKind.STRUCT:
        return
    path = path + [node.name]
    for child in node.children:
        _collect_structs(child, path, found)
    found.append((PATH_SEPARATOR.join(path), node))
