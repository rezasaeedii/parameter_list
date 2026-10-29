"""Builds ``cg_parameter_list.h``.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from .file_builder import FileBuilder

BRIEF = "Generated parameter list and its access functions."

WEAK_MACRO = "PARAMETER_LIST_WEAK"

INIT_FUNCTION = "fParameterList_Init"
INIT_CALLBACK = "fParameterList_InitCompletedCallback"
GET_QUANTITY_FUNCTION = "fParameterList_GetQuantity"
GET_BY_INDEX_FUNCTION = "fParameterList_GetByIndex"
GET_BY_NAME_FUNCTION = "fParameterList_GetByName"

DESCRIPTOR_TYPE = "const sParameterDescriptor *"


class ParameterListHeader(FileBuilder):
    """Public header: the weak macro, the access functions and the table."""

    @property
    def file_name(self) -> str:
        return self.list_header

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
        text += self.include.generate("parameter_descriptor.h")
        text += self.include.generate(self.defines_header)
        text += self.include.generate(self.smart_data_header)
        text += self.include.generate(self.types_header)
        text += "\n"

        text += self.marker.generate("Exported defines")

        # ---- the compiler independent 'weak' macro -----------------------
        text += self.marker.generate("Exported macros")
        text += self.comment.generate_doc("Compiler independent 'weak' attribute.")
        text += f"#ifndef {WEAK_MACRO}\n"
        text += "  #if defined(__GNUC__) || defined(__clang__) || defined(__ARMCC_VERSION)\n"
        text += f"    #define {WEAK_MACRO}  __attribute__((weak))\n"
        text += "  #elif defined(__ICCARM__)\n"
        text += f"    #define {WEAK_MACRO}  __weak\n"
        text += "  #else\n"
        text += f"    #define {WEAK_MACRO}\n"
        text += "  #endif\n"
        text += f"#endif  /* {WEAK_MACRO} */\n"
        text += "\n"

        text += self.marker.generate("Exported types")

        # ---- exported functions ------------------------------------------
        text += self.marker.generate("Exported functions")
        text += self.function.generate_prototype("uint8_t", INIT_FUNCTION)
        text += self.function.generate_prototype("uint8_t", INIT_CALLBACK,
                                                 qualifier=WEAK_MACRO)
        text += self.function.generate_prototype("uint16_t", GET_QUANTITY_FUNCTION)
        text += self.function.generate_prototype(DESCRIPTOR_TYPE, GET_BY_INDEX_FUNCTION,
                                                 "uint16_t index")
        text += self.function.generate_prototype(DESCRIPTOR_TYPE, GET_BY_NAME_FUNCTION,
                                                 "const char *pName")
        text += "\n"

        # ---- one size getter per tag that is actually used -----------------
        # The totals are already available as macros in the defines header, but
        # a macro cannot be called from another translation unit that does not
        # include it, cannot be passed around, and gives the caller no place to
        # put a breakpoint.  These functions make the memory map part of the
        # normal API.
        sized = self.sized_tags()
        if sized:
            text += self.comment.generate_line(
                f"Total number of bytes reserved by each tag (each parameter's offset "
                f"inside it: {self.table_header}).")
            for spec in sized:
                text += self.function.generate_prototype(
                    "uint32_t", self.tag_size_function_of(spec.tag_id))
            text += "\n"

        # ---- the descriptor table ------------------------------------------
        text += self.marker.generate("Exported variables")
        text += self.variable.generate_declaration(
            c_type="sParameterDescriptor",
            name=self.descriptor_symbol,
            array_size=self.quantity,
            qualifier="const",
            comment=f"Descriptor of every parameter, indexed by '{self.defines_header}'")
        text += "\n"

        # ---- closing guards and footer --------------------------------------
        text += self.cpp.generate_close()
        text += "\n"
        text += self.guard.generate_close(self.guard_name)
        text += "\n"
        text += self.footer.generate()
        return text
