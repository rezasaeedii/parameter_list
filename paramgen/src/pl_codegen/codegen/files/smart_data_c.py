"""Builds ``cg_smart_data.c``.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

import re

from ..literals import constructor_arguments, limit_headers
from .file_builder import FileBuilder
from .smart_data_h import INIT_BRIEF, INIT_DOC_RETURN, INIT_FUNCTION, INIT_RETURN

BRIEF = "Definition and construction of the generated smart-data objects."

LOOP_INDEX = "index"
STATUS = "status"

#: the trailing "[0]" of the first element of an array declaration
_TRAILING_ELEMENT = re.compile(r"\[\d+\]$")


def _without_element(symbol: str) -> str:
    """``Cg_SmartData_PosDrone[0]`` -> ``Cg_SmartData_PosDrone``.

    A leaf's name is the C expression that reaches it, element index and
    all; the loop that builds the whole declaration needs the array itself.
    """
    return _TRAILING_ELEMENT.sub("", symbol)


class SmartDataSource(FileBuilder):
    """Defines every smart-data object and constructs it in ``fCgSmartData_Init``."""

    @property
    def file_name(self) -> str:
        return self.smart_data_source

    def generate(self) -> str:
        text = ""

        # ---- banner ------------------------------------------------------
        text += self.banner.generate(self.file_name, BRIEF, self.generation_notes())
        text += "\n"

        # ---- includes ----------------------------------------------------
        text += self.marker.generate("Includes")
        text += self.include.generate(self.smart_data_header)
        text += self.include.generate("smart_data.h")
        # The constructors of values with no range of their own are written with
        # INT32_MIN / UINT16_MAX / -DBL_MAX and friends, so the headers that
        # declare those macros have to be here.  Only the ones actually used.
        for header in limit_headers(self.parameters):
            text += self.include.generate(header, standard=True)
        text += "\n"

        text += self.marker.generate("Private defines")
        text += self.marker.generate("Private macros")
        text += self.marker.generate("Private types")
        text += self.marker.generate("Private variables")
        text += self.marker.generate("Private functions")

        # ---- one object per top level parameter ---------------------------
        text += self.marker.generate("Exported variables")
        for c_type, name, array_size, _comment in self.top_level_objects():
            text += self.variable.generate_definition(
                c_type=c_type, name=name, array_size=array_size)
        text += "\n"

        # ---- the init function --------------------------------------------
        text += self.comment.generate_separator("Exported Functions")
        text += "\n"
        text += self.comment.generate_doc(INIT_BRIEF, returns=INIT_DOC_RETURN)
        text += self.function.generate_begin(INIT_RETURN, INIT_FUNCTION)
        text += self.function.generate_body(self._init_body())
        text += self.function.generate_end()
        text += "\n"

        text += self.comment.generate_separator("Private Functions")
        text += "\n"
        text += self.footer.generate()
        return text

    # -- the body of fCgSmartData_Init ------------------------------------
    def _init_body(self) -> str:
        tab = self.tab
        body = ""
        # Whether a loop was really written, rather than whether the model
        # merely *has* an array somewhere.  A struct array is expanded field by
        # field - 'Motor[0].Rpm', 'Motor[1].Rpm' - so it needs no counter, and
        # declaring one anyway left an unused variable behind: a warning, and
        # under the company's -Werror a generated file that does not compile.
        wrote_a_loop = False

        # Every element of an array declaration is its own row of the descriptor
        # table, but they are still one C array and they all take the same
        # constructor arguments - so they are built in one loop rather than in
        # N copied statements.  The elements arrive next to each other from
        # flatten(), which is what makes grouping them a matter of looking at
        # the first one.
        index = 0
        while index < len(self.parameters):
            parameter = self.parameters[index]
            value_type = parameter.value_type
            if value_type is None:
                index += 1
                continue

            count = parameter.declared_array_size
            symbol = self.smart_data_of(parameter)
            arguments = constructor_arguments(
                parameter, value_type, self.config.codegen.emit_unit)

            if count > 1 and parameter.element_index == 0:
                base = _without_element(symbol)
                size = self.array_size_of(parameter)
                element = f"{base}[{LOOP_INDEX}]"
                wrote_a_loop = True
                body += f"for ({LOOP_INDEX} = 0U; {LOOP_INDEX} < {size}; {LOOP_INDEX}++) {{\n"
                body += f"{tab}{STATUS} = {value_type.constructor}"
                body += f"(&{element}, {arguments});\n"
                body += f"{tab}if ({STATUS} != eSMART_DATA_OK) {{\n"
                body += f"{tab}{tab}return ({INIT_RETURN}){STATUS};\n"
                body += f"{tab}}}\n"
                body += "}\n"
                index += count
            else:
                body += f"{STATUS} = {value_type.constructor}(&{symbol}, {arguments});\n"
                body += f"if ({STATUS} != eSMART_DATA_OK) {{\n"
                body += f"{tab}return ({INIT_RETURN}){STATUS};\n"
                body += "}\n"
                index += 1
            body += "\n"

        head = f"eSmartDataStatus {STATUS} = eSMART_DATA_OK;\n"
        if wrote_a_loop:
            head += f"uint16_t {LOOP_INDEX} = 0U;\n"
        return head + "\n" + body + f"return ({INIT_RETURN}){STATUS};"

