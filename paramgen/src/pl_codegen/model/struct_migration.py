"""Turning structures written the old way into real structure types.

Before types had a file of their own, a structure in a parameter list simply
*was* its fields: a node with children and no type name.  Two parameters that
happened to hold the same fields were two unrelated structures, and the
"structure types" of the day were copies - pressing one duplicated its fields
and the copy then went its own way.

Those files still have to open, and they have to open as something the new
model can work with.  So on the way in:

  * a structure that names a type is left alone - it gets its shape from the
    type, which is the whole point;
  * a structure that names no type has one **made out of the shape it already
    has**, named after the parameter, and is pointed at it.  Nothing about the
    parameter changes: the same fields, the same limits, the same log ids.  It
    simply now has a name for what it is.

The result is written back out the first time the list is saved, so a project
converts itself by being opened and saved once.  Nothing here is destructive:
a file that is only read keeps its old shape on disk.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from ..errors import DiagnosticCollector, SourceLocation
from .parameter import Parameter
from .struct_type import StructField, StructType
from .types import resolve_value_type

if TYPE_CHECKING:                      # pragma: no cover - typing only
    from pathlib import Path
    from .parameter_list import ParameterList


def adopt_types(model: "ParameterList", legacy: List[Parameter],
                path: "Path", diagnostics: Optional[DiagnosticCollector] = None) -> None:
    """Give every structure in *model* a named type, inventing one where needed.

    *legacy* is the old inline library, if the file had one.  Those become
    types outright: they were already meant to be types, they simply had no way
    of saying so.
    """
    for template in legacy:
        struct_type = _type_from_node(template, template.name)
        if struct_type.name not in model.struct_types:
            model.struct_types.put(struct_type)

    made: Dict[str, str] = {}          # parameter path -> type name it was given
    for parameter in model.parameters:
        _adopt(parameter, model, made, path, diagnostics)


def _adopt(node: Parameter, model: "ParameterList", made: Dict[str, str],
           path: "Path", diagnostics: Optional[DiagnosticCollector]) -> None:
    for child in node.children:
        _adopt(child, model, made, path, diagnostics)

    if not node.is_struct or node.value_type_name:
        return

    name = _free_name(node.name, model, node)
    struct_type = _type_from_node(node, name)

    # A type identical to one already known is that type, not a second copy of
    # it: a list with three 'Position' parameters converts to one type used
    # three times, which is what somebody looking at the result expects.
    same = next((item for item in model.struct_types.all()
                 if item.shape == struct_type.shape), None)
    if same is not None:
        node.value_type_name = same.name
        return

    model.struct_types.put(struct_type)
    node.value_type_name = struct_type.name
    made[node.name] = struct_type.name
    if diagnostics is not None:
        diagnostics.info(
            "TYP001",
            f"'{node.name}' had no structure type; one called '{struct_type.name}' "
            f"was made from the fields it already has.",
            SourceLocation(file=str(path), parameter=node.name),
            hint="Saving the sub list writes it into the types file beside it. "
                 "Rename it in 'Structure types' if you want it called "
                 "something else.")


def _type_from_node(node: Parameter, name: str) -> StructType:
    """The type a structure node describes: its fields' shape, and nothing else.

    Not their units or descriptions, and no description of its own: those say
    what this particular parameter means, and they stay on its fields.
    """
    struct_type = StructType(name=name)
    for child in node.children:
        struct_type.fields.append(StructField(
            name=child.name,
            # A nested structure keeps naming whatever it names; it has been
            # given a type of its own by then, because children come first.
            value_type_name=child.value_type_name or "",
            array_size=max(1, int(child.array_size or 1)),
            # a field this structure had switched off stays off in its type
            enable=bool(child.enable)))
    return struct_type


def _free_name(wanted: str, model: "ParameterList", node: Parameter) -> str:
    """A type name not already taken by a *different* structure.

    The parameter's own name is the obvious one and is used whenever it is
    free.  ``Position`` taken by something of another shape becomes
    ``Position_2`` rather than quietly joining it - two structures with one
    name is exactly the confusion types exist to end.
    """
    wanted = wanted or "Struct"
    if resolve_value_type(wanted) is None and wanted not in model.struct_types:
        return wanted

    existing = model.struct_types.get(wanted)
    if existing is not None and existing.shape == _type_from_node(node, wanted).shape:
        return wanted

    index = 2
    while f"{wanted}_{index}" in model.struct_types:
        index += 1
    return f"{wanted}_{index}"
