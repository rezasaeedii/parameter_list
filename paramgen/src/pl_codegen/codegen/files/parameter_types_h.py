"""Builds ``cg_parameter_list_types.h`` -- the generated structure types.

One C structure per structure TYPE, not per parameter.  A structure type is what
it is in C++: declared once, and every structure parameter of that type is an
instance of it::

    typedef struct {
        sSmartDataI16 collor;
        sSmartDataB8  alive[STEST_ALIVE_ARRAY_SIZE];
    } sCgStruct_Stest;

    sCgStruct_Stest Cg_SmartData_MyStr;       (in cg_smart_data.c)
    sCgStruct_Stest Cg_SmartData_MyStr2;

A field whose type is another structure type is a member of that type, so a type
used inside another is declared first.  A field the type has switched off is not
in the typedef - and since switching a field off is the type's to decide, no
parameter of the type can disagree.

What is deliberately NOT in a typedef: the unit or the description of a field.
They say what the field means in one USE of the type - ``xyz`` is a speed in one
parameter and an offset in another - and a typedef is shared by every use.  Each
use's unit goes to its smart-data constructor, its description to the parameter
table.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from typing import List, Tuple

from ...model.parameter import Parameter
from ...model.parameter_list import PATH_SEPARATOR
from ...model.struct_type import StructType
from ...model.types import resolve_value_type
from .file_builder import FileBuilder

BRIEF = "Structure types generated from the structure types of the parameter list."


class ParameterTypesHeader(FileBuilder):
    """One ``typedef struct`` per structure type in use, inner types first."""

    @property
    def file_name(self) -> str:
        return self.types_header

    def generate(self) -> str:
        text = ""

        # ---- banner and guards -----------------------------------------
        text += self.banner.generate(self.file_name, BRIEF, self.generation_notes())
        text += "\n"
        text += self.guard.generate_open(self.guard_name)
        text += "\n"
        text += self.cpp.generate_open()
        text += "\n"

        # ---- includes ---------------------------------------------------
        text += self.marker.generate("Includes")
        text += self.include.generate("smart_data.h")
        text += self.include.generate(self.defines_header)
        text += "\n"

        text += self.marker.generate("Exported defines")
        text += self.marker.generate("Exported macros")

        # ---- one typedef per structure type, inner types first -----------
        text += self.marker.generate("Exported types")
        types = self.model.struct_types_in_use()
        if not types:
            text += self.comment.generate_line(
                "The parameter list contains no structure.")
            text += "\n"
        else:
            users = self.model.structures_by_type()
            for struct_type in types:
                text += self._generate_struct(struct_type,
                                              users.get(struct_type.name, []))
                text += "\n"

        text += self.marker.generate("Exported functions")
        text += self.marker.generate("Exported variables")
        text += "\n"

        # ---- closing guards and footer ------------------------------------
        text += self.cpp.generate_close()
        text += "\n"
        text += self.guard.generate_close(self.guard_name)
        text += "\n"
        text += self.footer.generate()
        return text

    # -- one structure type ---------------------------------------------------
    def _generate_struct(self, struct_type: StructType,
                         users: List[Tuple[str, Parameter]]) -> str:
        members = self._members(struct_type)
        used_by = ", ".join(path for path, _node in users)

        text = self.comment.generate_doc(
            f"Structure type '{struct_type.name}'.",
            notes=[f"Used by: {used_by}"] if used_by else ())
        text += "typedef struct {\n"
        text += "\n"

        type_width = max((len(member[0]) for member in members), default=0)
        for c_type, name, array_size in members:
            line = f"{self.tab}{c_type.ljust(type_width)} {name}"
            if array_size:
                line += f"[{array_size}]"
            text += line + ";\n"

        text += "\n"
        text += f"}} {self.struct_type_of(struct_type.name)};\n"
        return text

    def _members(self, struct_type: StructType) -> List[Tuple]:
        """``(c type, field name, array size macro or None)`` per enabled field."""
        members: List[Tuple] = []
        for member in struct_type.fields:
            if not member.enable:
                continue
            declaration = f"{struct_type.name}{PATH_SEPARATOR}{member.name}"
            size = (self.array_size_of_name(declaration)
                    if member.array_size > 1 else None)

            value_type = resolve_value_type(member.value_type_name)
            if value_type is not None:
                members.append((value_type.smart_data_struct, member.name, size))
                continue

            nested = self.model.struct_types.get(member.value_type_name)
            if nested is None:
                # validation has already refused an unknown type, by name
                continue
            members.append((self.struct_type_of(nested.name), member.name, size))
        return members
