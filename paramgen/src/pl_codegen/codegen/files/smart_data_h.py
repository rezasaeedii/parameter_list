"""Builds ``cg_smart_data.h``.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from .file_builder import FileBuilder

BRIEF = "Smart-data objects that hold the value of every parameter."

INIT_FUNCTION = "fCgSmartData_Init"
INIT_RETURN = "uint8_t"
INIT_DOC_RETURN = "uint8_t 0 on success, otherwise the failing eSmartDataStatus value."
INIT_BRIEF = "Constructs every generated smart-data object."


class SmartDataHeader(FileBuilder):
    """Declares one smart-data object per enabled parameter."""

    @property
    def file_name(self) -> str:
        return self.smart_data_header

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
        text += self.include.generate(self.types_header)
        text += "\n"

        text += self.marker.generate("Exported defines")
        text += self.marker.generate("Exported macros")
        text += self.marker.generate("Exported types")

        # ---- exported functions -----------------------------------------
        text += self.marker.generate("Exported functions")
        text += self.function.generate_prototype(INIT_RETURN, INIT_FUNCTION)
        text += "\n"

        # ---- one object per top level parameter ---------------------------
        # A struct parameter is ONE object of the generated structure type; its
        # fields live inside it.
        text += self.marker.generate("Exported variables")
        for c_type, name, array_size, comment in self.top_level_objects():
            text += self.variable.generate_declaration(
                c_type=c_type, name=name, array_size=array_size, comment=comment)
        text += "\n"

        # ---- closing guards and footer ------------------------------------
        text += self.cpp.generate_close()
        text += "\n"
        text += self.guard.generate_close(self.guard_name)
        text += "\n"
        text += self.footer.generate()
        return text
