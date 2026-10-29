"""Rules about structure types - the ``struct`` declarations of the list.

A structure parameter names a type, the way a C++ variable names one.  These
rules check that the name means something, that it means a *structure*, and
that the declarations themselves make sense.

The two rules people meet most are the pair that keep the two worlds apart: a
parameter holds a value and may not name a structure type, and a structure
holds fields and may not name ``float32_t``.  Both used to be possible, and
both produced a parameter list that looked right and generated nonsense.

A problem in a declaration is an error only for a type the build really
generates; for a type nothing uses it is a warning (see :class:`_TypeProblems`).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

from ...errors import DiagnosticCollector, SourceLocation
from ...model.parameter_list import ParameterList
from ...model.struct_type import StructType, StructTypeLibrary
from ...model.types import resolve_value_type, supported_type_names
from ...naming import is_valid_c_identifier
from .rule_base import ValidationRule, enabled_nodes


class StructTypeRule(ValidationRule):
    """Every structure names a structure type, and every type exists."""

    rule_id = "STRUCT_TYPE"
    description = "A structure must name a structure type that exists."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        library = model.struct_types
        for parameter in enabled_nodes(model):
            name = (parameter.value_type_name or "").strip()

            if parameter.is_struct:
                if not name:
                    diagnostics.error(
                        "TYP002",
                        f"Structure '{parameter.name}' has no structure type.",
                        parameter.source,
                        hint="Pick one in the 'Data type' list, or make one with "
                             "'Structure types…' in the settings menu.")
                    continue
                if resolve_value_type(name) is not None:
                    diagnostics.error(
                        "TYP005",
                        f"Structure '{parameter.name}' is of type '{name}', which is "
                        f"a data type and not a structure.",
                        parameter.source,
                        hint=f"A structure holds fields, not a value. Give '{name}' "
                             f"to a field instead, or make this parameter a plain "
                             f"parameter.")
                    continue
                if library.get(name) is None:
                    known = ", ".join(library.names()) or "none yet"
                    diagnostics.error(
                        "TYP003",
                        f"Structure '{parameter.name}' is of type '{name}', which "
                        f"this project does not have.",
                        parameter.source,
                        hint=f"Known structure types: {known}. The structures of a "
                             f"sub list live in the '_types.xml' file beside it; "
                             f"check that file came along with the sub list.")
            elif name and library.get(name) is not None:
                diagnostics.error(
                    "TYP004",
                    f"'{parameter.name}' is a parameter but its data type "
                    f"'{name}' is a structure type.",
                    parameter.source,
                    hint=f"A parameter holds one value. Pick one of "
                         f"{supported_type_names()}, or add it as a structure "
                         f"instead.")


class _TypeProblems:
    """Reports a problem of a structure TYPE at the severity it really has.

    A type the build generates a typedef for is an error: the generated code
    would be wrong.  A type nothing uses generates nothing, so the same finding
    is a warning.  It used to be an error either way - which blocked Generate
    over a type no structure had, and stayed in the Problems panel after the
    last structure of the type was deleted, looking like that structure's own
    error.  (Reported.)

    Either way the diagnostic names the type (``location.struct_type``), and the
    editor opens 'Structure types…' on it.  A type in use also names the first
    structure that holds it, so the row still jumps somewhere real.
    """

    def __init__(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        self.diagnostics = diagnostics
        self.library = model.struct_types
        self.in_use = {item.name for item in model.struct_types_in_use()}
        self.structures = model.struct_parameters()
        self.owners = model.type_owners

    def report(self, name: str, code: str, message: str, hint: str) -> None:
        # The list that declares the type: types belong to one list each, and
        # the editor opens that list's 'Structure types…' on it - the open
        # list's panel may simply not have it.  (The merge keeps the first
        # declaration, so that is the one a finding is about.)
        declared_in = (self.owners.get(name) or [None])[0]
        if name in self.in_use:
            where = SourceLocation(file=declared_in, parameter=self._holder(name),
                                   struct_type=name)
            self.diagnostics.error(code, message, where, hint=hint)
            return
        self.diagnostics.warning(
            code, f"{message} No structure uses it, so nothing is generated from it.",
            SourceLocation(file=declared_in, struct_type=name),
            hint=f"{hint} Or, since nothing uses it, delete it in 'Structure types…'.")

    def _holder(self, name: str) -> Optional[str]:
        """The first enabled structure that has *name* in it, however deep."""
        for path, node in self.structures:
            if name in _reachable(node.value_type_name, self.library):
                return path
        return None


class StructTypeDeclarationRule(ValidationRule):
    """The declarations themselves: names, fields, and what the fields hold."""

    rule_id = "STRUCT_TYPE_DECL"
    description = "Structure type declarations must be usable as C typedefs."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        library = model.struct_types
        problems = _TypeProblems(model, diagnostics)
        for struct_type in library.all():
            name = struct_type.name

            if not is_valid_c_identifier(name):
                problems.report(
                    name, "TYP006",
                    f"Structure type '{name}' is not a valid C identifier.",
                    hint="It becomes a typedef, so use letters, digits and '_', and "
                         "do not start with a digit.")

            if not struct_type.fields:
                problems.report(
                    name, "TYP007",
                    f"Structure type '{name}' has no fields.",
                    hint="An empty struct generates a typedef nothing can be built "
                         "from. Add a field, or delete the type.")

            seen: Set[str] = set()
            for member in struct_type.fields:
                if member.name in seen:
                    problems.report(
                        name, "TYP008",
                        f"Structure type '{name}' has two fields called "
                        f"'{member.name}'.",
                        hint="Two members of one struct cannot share a name.")
                seen.add(member.name)

                if not member.value_type_name:
                    problems.report(
                        name, "TYP009",
                        f"Field '{name}.{member.name}' has no data type.",
                        hint=f"Pick one of {supported_type_names()}, or another "
                             f"structure type.")
                elif (resolve_value_type(member.value_type_name) is None
                      and library.get(member.value_type_name) is None):
                    problems.report(
                        name, "TYP013",
                        f"Field '{name}.{member.name}' is of type "
                        f"'{member.value_type_name}', which is neither a data type "
                        f"nor a structure type.",
                        hint=f"Known data types: {supported_type_names()}. Known "
                             f"structure types: {', '.join(library.names()) or 'none'}.")

                if member.array_size < 1:
                    problems.report(
                        name, "TYP014",
                        f"Field '{name}.{member.name}' has array size "
                        f"{member.array_size}; it must be 1 or more.",
                        hint="Leave the cell empty for a single value.")


class StructTypeCycleRule(ValidationRule):
    """A structure type may not contain itself, however far around."""

    rule_id = "STRUCT_TYPE_CYCLE"
    description = "Structure types must not contain themselves."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        library = model.struct_types
        problems = _TypeProblems(model, diagnostics)
        for struct_type in library.all():
            path = _cycle_from(struct_type, library)
            if path:
                problems.report(
                    struct_type.name, "TYP015",
                    f"Structure type '{struct_type.name}' contains itself: "
                    f"{' -> '.join(path)}.",
                    hint="A struct cannot hold a copy of itself - it would have no "
                         "size. Break the loop by removing one of those fields.")


class StructTypeClashRule(ValidationRule):
    """One structure type name, declared by more than one parameter list.

    A type belongs to the list that declares it.  Two lists declaring one name
    is an error even when both say the same thing: the merged types file and
    the C typedef made from it can hold one of them only.  It used to be
    accepted then, as "one shared type" - and a list could be reshaped by the
    other list's declaration without either of them being open.
    """

    rule_id = "STRUCT_TYPE_CLASH"
    description = ("A structure type belongs to one parameter sub list; two sub lists "
                   "may not declare one name.")

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for name in model.type_clashes:
            owners = model.type_owners.get(name) or []
            lists = [_list_name(item) for item in owners]
            shown = ", ".join(lists) if lists else "more than one sub list"
            # Reported on the later list: the first one is the declaration the
            # build kept, so the later one is where renaming changes least.
            diagnostics.error(
                "TYP016",
                f"Structure type '{name}' is declared by more than one parameter "
                f"sub list: {shown}. A structure type belongs to one sub list only.",
                SourceLocation(file=owners[-1] if owners else None, struct_type=name),
                hint=f"Rename '{name}' in every sub list but one ('Structure types…' "
                     f"in each sub list) - or, in a sub list where nothing uses it, "
                     f"delete it there.")


class StructTypeOwnerRule(ValidationRule):
    """A list uses only the structure types it declares itself."""

    rule_id = "STRUCT_TYPE_OWNER"
    description = ("A structure, and a field of a structure type, may only name a "
                   "structure type its own parameter sub list declares.")

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        problems = _TypeProblems(model, diagnostics)
        for use in model.foreign_types:
            declared_by = [_list_name(item) for item in model.type_owners.get(use.type_name, [])]
            if not declared_by:
                continue      # declared nowhere at all: TYP003 / TYP013 say so
            here = _list_name(use.list_file)
            owners = " and ".join(declared_by)
            if not use.in_type:
                diagnostics.error(
                    "TYP017",
                    f"Structure '{use.where}' of {here} is of type '{use.type_name}', "
                    f"which {here} does not declare - it is a type of {owners}. A "
                    f"parameter sub list uses only its own structure types.",
                    SourceLocation(file=use.list_file, parameter=use.where),
                    hint=f"Declare a structure type in {here} ('Structure types…') "
                         f"and give it to '{use.where}', or move '{use.where}' to "
                         f"{declared_by[0]}.")
                continue
            problems.report(
                use.in_type, "TYP017",
                f"Field '{use.where}' of {here} is of type '{use.type_name}', which "
                f"{here} does not declare - it is a type of {owners}. A parameter "
                f"sub list uses only its own structure types.",
                hint=f"Give the field a structure type {here} declares itself, or a "
                     f"data type.")


def _list_name(list_file: Optional[str]) -> str:
    """``C:/p/parameter_lists/power.xml`` -> ``power.xml``: what a person calls it."""
    return Path(str(list_file)).name if list_file else "?"


def _reachable(name: Optional[str], library: StructTypeLibrary) -> Set[str]:
    """*name* and every structure type it holds as a field, however deep."""
    found: Set[str] = set()
    queue = [name] if name else []
    while queue:
        current = library.get(queue.pop())
        if current is None or current.name in found:
            continue
        found.add(current.name)
        queue.extend(member.value_type_name for member in current.fields)
    return found


def _cycle_from(struct_type: StructType, library) -> List[str]:
    """The chain of type names that leads back to *struct_type*, if any."""
    target = struct_type.name

    def walk(current: StructType, chain: List[str], seen: Set[str]) -> List[str]:
        for member in current.fields:
            nested = library.get(member.value_type_name)
            if nested is None:
                continue
            if nested.name == target:
                return chain + [nested.name]
            if nested.name in seen:
                continue
            found = walk(nested, chain + [nested.name], seen | {nested.name})
            if found:
                return found
        return []

    return walk(struct_type, [target], {target})
