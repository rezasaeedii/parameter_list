"""Rules about parameter names and the C identifiers derived from them."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ...errors import DiagnosticCollector
from ...model.parameter import Parameter
from ...model.parameter_list import ParameterList
from ...model.tags import TAG_REGISTRY
from ...model.parameter_list import PATH_SEPARATOR
from ...naming import (array_size_macro, index_macro, is_reserved_keyword,
                       is_valid_c_identifier, offset_total_macro,
                       smart_data_symbol, strip_array_indices, struct_type_name)
from .rule_base import ValidationRule, enabled_nodes

#: Macros smart_data.h already defines; a parameter may not shadow them.
RESERVED_MACROS = {"TRUE", "FALSE", "NULL"}


class NameSyntaxRule(ValidationRule):
    """Every name must be usable as a C identifier."""

    rule_id = "NAME"
    description = "Parameter and field names must be valid, non-reserved C identifiers."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in _all_nodes(model):
            if not is_valid_c_identifier(parameter.name):
                diagnostics.error(
                    "NAME001",
                    f"Name '{parameter.name}' is not a valid C identifier.",
                    parameter.source,
                    hint="Use letters, digits and '_' only, and do not start with a digit.")
            elif is_reserved_keyword(parameter.name):
                diagnostics.error(
                    "NAME002",
                    f"Name '{parameter.name}' is a reserved C/C++ keyword.",
                    parameter.source,
                    hint="The name becomes a C identifier and a macro name, so it "
                         "cannot be a word the language already uses. Rename it.")


class NameUniquenessRule(ValidationRule):
    """Names must be unique among the siblings that share a parent.

    A project is usually several parameter lists merged into one, so the two
    parameters that collide are often in *different files* - and the name alone
    then tells the reader nothing about where to go.  Every diagnostic here
    therefore names the file each duplicate came from.
    """

    rule_id = "NAME_UNIQUE"
    description = "Names must be unique inside their parent (and at the top level)."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        self._check_level(model.parameters, "the parameter list", diagnostics)
        for parameter in _all_nodes(model):
            if parameter.is_struct:
                self._check_level(parameter.children, f"struct '{parameter.name}'",
                                  diagnostics)

    @staticmethod
    def _check_level(nodes: List[Parameter], where: str,
                     diagnostics: DiagnosticCollector) -> None:
        seen: Dict[str, List[Parameter]] = {}
        for node in nodes:
            seen.setdefault(node.name, []).append(node)
        for name, duplicates in seen.items():
            if len(duplicates) < 2:
                continue

            # One diagnostic per duplicate, each naming *the other* places the
            # name is used.  Repeating the same sentence once per copy - which
            # is what a single message would do - tells the reader how many
            # there are but not where any of them is.
            files = [_file_of(node) for node in duplicates]
            for index, node in enumerate(duplicates):
                others = [text for position, text in enumerate(files) if position != index]
                diagnostics.error(
                    "NAME003",
                    f"Name '{name}' is used {len(duplicates)} times in {where}; "
                    f"this one is in {files[index]}.",
                    node.source,
                    hint=f"The other one(s) are in {', '.join(others)}. "
                         f"Rename one of them - the name becomes a C identifier, "
                         f"and the sublists are merged into a single table.")


class IndexMacroCollisionRule(ValidationRule):
    """Every identifier the generator invents must be unique and legal.

    Two different problems live here, and both produce code that *compiles*:

    * Two parameters can map onto the same macro.  ``TestVar`` and
      ``Test_Var`` both become ``TEST_VAR``, and the second ``#define`` silently
      wins.
    * A parameter can collide with a macro the generator makes for another
      reason - the array size of a different parameter, a tag offset, the
      quantity define - or with ``TRUE`` / ``FALSE`` / ``NULL`` from
      ``smart_data.h``.  A row named ``ParameterListQty`` redefines
      ``PARAMETER_LIST_QTY``, and the descriptor table is then declared with the
      wrong length.

    So every generated name is collected into one table with the reason it
    exists, and any name claimed twice is an error.
    """

    rule_id = "NAME_MACRO"
    description = "Generated macros and symbols must be unique and valid C identifiers."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        index_prefix = self.config.codegen.index_define_prefix
        offset_prefix = self.config.codegen.offset_define_prefix
        smart_prefix = self.config.codegen.smart_data_prefix

        #: name -> list of (what it is, the parameter it belongs to or None,
        #: what to call that parameter in the message)
        claimed: Dict[str, List] = {}

        def claim(name: str, reason: str, parameter=None, shown: str = "") -> None:
            claimed.setdefault(name, []).append(
                (reason, parameter, shown or (parameter.name if parameter else "")))

        # ---- what the generator makes regardless of the parameters --------
        claim(self.config.codegen.quantity_define, "the number of parameters")
        for macro in RESERVED_MACROS:
            claim(macro, "defined by smart_data.h")
        for spec in TAG_REGISTRY:
            claim(offset_total_macro(spec.tag_id, offset_prefix),
                  f"the size of the '{spec.tag_id}' tag area")

        # ---- one array size macro per array *declaration* -------------------
        # Not per leaf and not per parameter: an array field belongs to its
        # structure type, so 'MyStr.alive' and 'MyStr2.alive' of type 'Stest' are
        # one macro, STEST_ALIVE_ARRAY_SIZE, and not a collision.
        for declaration, _size, node in model.array_declarations():
            claim(array_size_macro(declaration, index_prefix),
                  "an array size macro", node, declaration)

        # ---- one C typedef per structure TYPE -------------------------------
        # Every parameter of a type is an instance of the one typedef, so its
        # name is claimed once per type, reported on the first structure that
        # uses it.  Type names are unique among themselves; what this still
        # catches is a prefix that makes a typedef name something else the
        # generator writes.
        users = model.structures_by_type()
        for struct_type in model.struct_types_in_use():
            _path, node = users.get(struct_type.name, [("", None)])[0]
            claim(struct_type_name(struct_type.name,
                                   self.config.codegen.struct_type_prefix),
                  "a structure type", node, struct_type.name)

        # ---- and what it makes for each parameter --------------------------
        for parameter in model.flatten():
            claim(index_macro(parameter.name, index_prefix), "an index macro", parameter)
            claim(smart_data_symbol(parameter.name, smart_prefix),
                  "a smart-data object", parameter)

        # ---- report -------------------------------------------------------
        for name, owners in claimed.items():
            reported = [item for item in owners if item[1] is not None]
            if len(owners) < 2 or not reported:
                continue
            described = "; ".join(
                reason + (f" of '{shown}'" if shown else "")
                for reason, _item, shown in owners)
            for _reason, parameter, _shown in reported:
                diagnostics.error(
                    "NAME004",
                    f"'{name}' is used for more than one thing: {described}.",
                    parameter.source,
                    hint="Rename one of them, or change 'codegen.index_define_prefix', "
                         "'codegen.offset_define_prefix' or 'codegen.struct_type_prefix' "
                         "in the configuration.")


class GeneratedIdentifierRule(ValidationRule):
    """A name that is a legal C identifier can still make an illegal macro.

    ``to_macro_case`` strips the underscores at the ends, so a parameter called
    ``_1`` - perfectly legal in C - becomes the macro ``1``, and the generated
    header does not compile.  The names the generator derives are therefore
    checked as well, not only the name the user wrote.
    """

    rule_id = "NAME_DERIVED"
    description = "Macros and symbols derived from a name must be valid C identifiers."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        index_prefix = self.config.codegen.index_define_prefix
        smart_prefix = self.config.codegen.smart_data_prefix

        # the array size macros, which belong to a declaration and not to a leaf
        for dotted_name, _size, node in model.array_declarations():
            if node is None or any(not is_valid_c_identifier(segment)
                                   for segment in _name_segments(dotted_name)):
                continue                      # NAME001 already named the cause
            macro = array_size_macro(dotted_name, index_prefix)
            if not is_valid_c_identifier(macro) or is_reserved_keyword(macro):
                diagnostics.error(
                    "NAME005",
                    f"The array size macro derived from '{dotted_name}' is "
                    f"'{macro}', which is not a usable C identifier.",
                    node.source,
                    hint="Give the parameter a name that starts with a letter and "
                         "holds letters, digits and inner underscores.")

        # One report per DECLARATION, not per value: an array of sixteen shares
        # one name, so a name that derives a bad macro is one mistake and not
        # sixteen.
        reported = set()
        for parameter in model.flatten():
            # A leaf whose own path already contains a name NAME001 rejected
            # needs nothing said here: the cause is that one name, and it has
            # been reported once, against the node that owns it.  Repeating it
            # per leaf turned a single bad structure name into seventy-seven
            # identical errors, which buries every other diagnostic in the
            # Problems panel.
            if any(not is_valid_c_identifier(segment)
                   for segment in _name_segments(parameter.name)):
                continue

            derived = [
                ("index macro", index_macro(parameter.name, index_prefix)),
            ]
            # A struct field is reached through its parent object, so its
            # 'c_object' is a member expression such as
            # 'Cg_SmartData_Position.Home.Lat' - deliberately not an identifier.
            # Only the object at the root of that expression is one, and only a
            # top level value owns its object outright.
            object_expression = smart_data_symbol(
                parameter.c_object or parameter.name, smart_prefix)
            derived.append(("smart-data object", _root_identifier(object_expression)))

            # One message per parameter, listing everything the name breaks -
            # not one per derived identifier.  A name with a character C cannot
            # use breaks the index macro and the object alike (and once broke
            # one offset macro per active tag as well), so a single bad name
            # used to fill the Problems panel with identical lines and bury
            # every other diagnostic.
            # (The boolean range rule reports the same way, for the same
            # reason.)
            broken = [(what, name) for what, name in derived
                      if not is_valid_c_identifier(name) or is_reserved_keyword(name)]
            if not broken:
                continue

            declaration = strip_array_indices(parameter.name)
            if declaration in reported:
                continue
            reported.add(declaration)

            first_what, first_name = broken[0]
            others = "" if len(broken) == 1 else \
                f" The same name also breaks the {', the '.join(w for w, _ in broken[1:])}."
            diagnostics.error(
                "NAME005",
                f"The {first_what} derived from '{parameter.name}' is "
                f"'{first_name}', which is not a usable C identifier.{others}",
                parameter.source,
                hint="Give the parameter a name that starts with a letter and "
                     "holds letters, digits and inner underscores.")


def _name_segments(dotted_name: str) -> List[str]:
    """The individual names inside a path: 'Wheels[1].Speed' -> Wheels, Speed.

    The element index is not part of any name - it is how the path addresses one
    element - so it is stripped before the segments are checked.
    """
    return [segment.split("[", 1)[0]
            for segment in strip_array_indices(dotted_name).split(PATH_SEPARATOR)
            if segment]


class StructRule(ValidationRule):
    """Structures must have fields, and a sane array size."""

    rule_id = "STRUCT"
    description = "Structures must contain at least one field and have a valid array size."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_nodes(model):
            if not parameter.is_struct:
                continue

            if not parameter.enabled_children():
                diagnostics.error(
                    "STR001",
                    f"Structure '{parameter.name}' has no enabled field.",
                    parameter.source,
                    hint="Add a field, or disable the whole structure.")

            if parameter.array_size < 1:
                diagnostics.error(
                    "STR002",
                    f"Structure '{parameter.name}' has array size "
                    f"{parameter.array_size}; it must be 1 or more.",
                    parameter.source,
                    hint="Leave the 'Array size' cell empty for a single structure.")

            # STR003 used to warn that a structure carried a data type.  It is
            # the other way round now: a structure IS of a type - that is what
            # a struct declaration is - and StructTypeRule checks the type it
            # names really exists and really is a structure.


# StructFieldRule (STR004 / STR005) lived here.  It is gone because the model
# can no longer hold what it looked for: a field's shape comes from the
# structure type, and applying a type clears the tags and the parameter type of
# every field as a matter of course.  A hand-edited file that sets them is
# still told about it - by the reader, which drops them on the way in and says
# so (XML013 and XML014).


def _root_identifier(expression: str) -> str:
    """The object at the root of a generated member expression.

    ``Cg_SmartData_Position.Home.Lat`` -> ``Cg_SmartData_Position`` and
    ``Cg_SmartData_Wheels[0].Speed`` -> ``Cg_SmartData_Wheels``.  Only that root
    is an identifier the compiler ever sees *declared*; the ``.field`` part and
    the ``[index]`` are how the value inside it is reached, and neither is
    allowed to make the check fail.
    """
    return expression.split(".", 1)[0].split("[", 1)[0]


def _fields_of(root: Parameter) -> List[Parameter]:
    """Every node below *root*, structures and values alike."""
    return [node for node in root.walk() if node is not root]


def _file_of(node: Parameter) -> str:
    """The parameter list a node came from, as short as it can be said.

    Only the file name is shown: the lists of a project all live in one folder,
    so the folder is the same on every line and repeating it would push the
    part that differs off the edge of the message.
    """
    path = node.source.file
    if not path:
        return "this sublist"
    return Path(path).name


def _all_nodes(model: ParameterList) -> List[Parameter]:
    """Every node of the tree, disabled ones included (names still matter)."""
    return list(model.walk())
