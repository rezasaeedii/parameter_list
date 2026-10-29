"""Builds ``cg_parameter_list.c``.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from ...model.defines import type_enum_member
from ...model.parameter import Parameter
from ...model.tags import TAG_REGISTRY, TagKind
from ...model.types import VALUE_TYPES, CValueType
from ..descriptor_layout import (FIELD_DESCRIPTION, FIELD_TYPE,
                                 FIELD_LOG_ID, FIELD_NAME, FIELD_SMART_DATA,
                                 FIELD_USER_NAME)
from ..literals import escape_string, tag_value_literal
from .file_builder import FileBuilder
from .parameter_list_h import (DESCRIPTOR_TYPE, GET_BY_INDEX_FUNCTION, GET_BY_NAME_FUNCTION,
                               GET_QUANTITY_FUNCTION, INIT_CALLBACK, INIT_FUNCTION,
                               READ_BY_INDEX_FUNCTION, WEAK_MACRO, WRITE_BY_INDEX_FUNCTION)
from .smart_data_h import INIT_FUNCTION as SMART_DATA_INIT

BRIEF = "Generated parameter list and its access functions."


class ParameterListSource(FileBuilder):
    """The constant descriptor table plus the exported access functions."""

    @property
    def file_name(self) -> str:
        return self.list_source

    def generate(self) -> str:
        text = ""

        # ---- banner ------------------------------------------------------
        text += self.banner.generate(self.file_name, BRIEF, self.generation_notes())
        text += "\n"

        # ---- includes ----------------------------------------------------
        text += self.marker.generate("Includes")
        text += self.include.generate(self.list_header)
        text += "\n"
        text += self.include.generate("stddef.h", standard=True)
        text += self.include.generate("string.h", standard=True)
        text += "\n"
        text += self.include.generate("smart_data.h")
        text += self.include.generate(self.smart_data_header)
        text += "\n"
        text += self._generate_extra_includes()

        text += self.marker.generate("Private defines")
        text += self.marker.generate("Private macros")
        text += self.marker.generate("Private types")
        text += self.marker.generate("Private variables")
        text += self.marker.generate("Private functions")

        # ---- the descriptor table ------------------------------------------
        text += self.marker.generate("Exported variables")
        text += self._generate_table()
        text += "\n"

        # ---- the exported functions ----------------------------------------
        text += self.comment.generate_separator("Exported Functions")
        text += "\n"
        text += self._generate_init()
        text += self._generate_init_callback()
        text += self._generate_get_quantity()
        text += self._generate_get_by_index()
        text += self._generate_get_by_name()
        text += self._generate_by_index()
        text += self._generate_tag_sizes()

        text += self.comment.generate_separator("Private Functions")
        text += "\n"
        text += self.footer.generate()
        return text

    # -- extra includes ----------------------------------------------------
    def _generate_extra_includes(self) -> str:
        """The headers listed under ``codegen.extra_includes``.

        A free tag (*Tag1* .. *Tag4*) may hold a word instead of a number, and
        that word is written into the table as ``(uint32_t)APP_FLAG_X``.  The
        compiler has to know what ``APP_FLAG_X`` is, and only the application
        knows which header declares it - hence the list in the configuration
        file.  Without it the generated file simply does not compile, which is
        confusing because nothing in the tool complains.
        """
        entries = [str(entry).strip() for entry in self.config.codegen.extra_includes]
        entries = [entry for entry in entries if entry]
        if not entries:
            return ""

        text = self.comment.generate_line(
            "Application headers listed under 'codegen.extra_includes'.")
        for entry in entries:
            #: '<stdbool.h>' and '"app.h"' are both accepted, and so is a plain
            #: name - the usual case for a project header.
            if entry.startswith("<") and entry.endswith(">"):
                text += self.include.generate(entry[1:-1], standard=True)
            else:
                text += self.include.generate(entry.strip('"'))
        return text + "\n"

    # -- the descriptor table ---------------------------------------------
    def _generate_table(self) -> str:
        text = self.comment.generate_doc(
            "Descriptor of every parameter of the merged parameter list.\n"
            f"The order of the entries matches the index macros of '{self.defines_header}'.")
        text += f"const sParameterDescriptor {self.descriptor_symbol}[{self.quantity}] = {{\n"

        last = len(self.parameters) - 1
        for index, parameter in enumerate(self.parameters):
            text += f"{self.tab}/* [{index}] {self.index_of(parameter)} */\n"
            text += f"{self.tab}{{\n"
            for line in self._table_entry(parameter):
                text += f"{self.tab}{self.tab}{line}\n"
            text += f"{self.tab}}}" + (",\n\n" if index < last else "\n")

        text += "};\n"
        return text

    def _table_entry(self, parameter: Parameter):
        """The designated initialisers of one row, in declaration order.

        Declaration order matters: this form is valid in C99 *and* in C++20 only
        as long as the fields appear in the same order as in
        ``parameter_descriptor.h`` (see ``codegen/descriptor_layout.py``).
        """
        value_type = parameter.value_type
        assert value_type is not None  # guaranteed by the validator

        # One row is one value.  The leaf's name already *is* the C expression
        # that reaches it - 'PosDrone[2]', 'Wheels[1].Speed' - so an element of
        # an array declaration points straight at its own element of the C
        # object, which is still a real array, and the table needs no count to
        # describe it.
        smart_data = f"(void *)&{self.smart_data_of(parameter)}"

        lines = [
            f".{FIELD_NAME} = {escape_string(parameter.name)},",
            # This value's own User Name - flatten() has already worked out
            # which one that is - and "" for none, never NULL, like the
            # description.
            f".{FIELD_USER_NAME} = {escape_string(parameter.user_name or '')},",
            f".{FIELD_TYPE} = {type_enum_member(parameter.param_type or 'MONITORING')},",
            f".{FIELD_SMART_DATA} = {smart_data},",
            # effective_log_id, not log_id: a number left on a value that is
            # not logged has no meaning, and 0 is what the table stores for it.
            f".{FIELD_LOG_ID} = {parameter.effective_log_id or 0}U,",
        ]

        for spec in TAG_REGISTRY:
            value = parameter.effective_tag(spec.tag_id)
            if spec.kind is TagKind.BOOLEAN and value is None:
                value = False
            # A tag field is a bare uint32_t now: its offset moved out of the
            # descriptor entirely, and lives only in cg_parameter_list_table.h.
            lines.append(f".{spec.descriptor_field} = {tag_value_literal(value)},")

        lines.append(f".{FIELD_DESCRIPTION} = {escape_string(self.description_of(parameter))}")
        return lines

    # -- one size getter per used tag ---------------------------------------
    def _generate_tag_sizes(self) -> str:
        """``fParameterList_GetResetProofSize()`` and friends.

        Each one simply returns the matching total macro, so the number can
        never drift away from the offsets it belongs to.
        """
        text = ""
        for spec in self.sized_tags():
            total = self.offset_total_of(spec.tag_id)
            text += self.comment.generate_doc(
                f"Total number of bytes reserved by the '{spec.tag_id}' tag.",
                notes=[f"This is the sum over every parameter that carries the tag, "
                       f"each one taking sizeof(value) x array size bytes."],
                returns=f"uint32_t Always {total}.")
            text += self.function.generate_begin(
                "uint32_t", self.tag_size_function_of(spec.tag_id))
            text += self.function.generate_body(f"return (uint32_t){total};")
            text += self.function.generate_end()
            text += "\n"
        return text

    # -- the five functions -------------------------------------------------
    def _generate_init(self) -> str:
        tab = self.tab
        body = "uint8_t result = 0U;\n"
        body += "\n"
        body += f"result = {SMART_DATA_INIT}();\n"
        body += "if (result != 0U) {\n"
        body += f"{tab}return result;\n"
        body += "}\n"
        body += "\n"
        body += f"result = {INIT_CALLBACK}();\n"
        body += "if (result != 0U) {\n"
        body += f"{tab}return result;\n"
        body += "}\n"
        body += "\n"
        body += "return result;"

        text = self.comment.generate_doc(
            "Initialises the parameter list and every smart-data object.",
            returns="uint8_t 0 on success, otherwise a non-zero error code.")
        text += self.function.generate_begin("uint8_t", INIT_FUNCTION)
        text += self.function.generate_body(body)
        text += self.function.generate_end()
        return text + "\n"

    def _generate_init_callback(self) -> str:
        text = self.comment.generate_doc(
            "Called once the parameter list has been initialised.",
            notes=["Implement this function in the application layer without the weak\n"
                   "specifier to hook into the initialisation."],
            returns="uint8_t 0 on success, otherwise a non-zero error code.")
        text += self.function.generate_begin("uint8_t", INIT_CALLBACK, qualifier=WEAK_MACRO)
        text += self.function.generate_body("return 0U;")
        text += self.function.generate_end()
        return text + "\n"

    def _generate_get_quantity(self) -> str:
        text = self.comment.generate_doc(
            "Returns the number of parameters in the list.",
            returns=f"uint16_t Always {self.quantity}.")
        text += self.function.generate_begin("uint16_t", GET_QUANTITY_FUNCTION)
        text += self.function.generate_body(f"return (uint16_t){self.quantity};")
        text += self.function.generate_end()
        return text + "\n"

    def _generate_get_by_index(self) -> str:
        tab = self.tab
        body = f"if (index >= (uint16_t){self.quantity}) {{\n"
        body += f"{tab}return NULL;\n"
        body += "}\n"
        body += "\n"
        body += f"return &{self.descriptor_symbol}[index];"

        text = self.comment.generate_doc(
            "Returns the descriptor of the parameter at *index*.",
            params=[f"index Index of the parameter, see '{self.defines_header}'."],
            returns="const sParameterDescriptor* NULL when the index is out of range.")
        text += self.function.generate_begin(DESCRIPTOR_TYPE, GET_BY_INDEX_FUNCTION,
                                             "uint16_t index")
        text += self.function.generate_body(body)
        text += self.function.generate_end()
        return text + "\n"

    def _generate_get_by_name(self) -> str:
        tab = self.tab
        symbol = self.descriptor_symbol
        body = "uint16_t index = 0U;\n"
        body += "\n"
        body += "if (pName == NULL) {\n"
        body += f"{tab}return NULL;\n"
        body += "}\n"
        body += "\n"
        body += f"for (index = 0U; index < (uint16_t){self.quantity}; index++) {{\n"
        body += f"{tab}if (strcmp({symbol}[index].pName, pName) == 0) {{\n"
        body += f"{tab}{tab}return &{symbol}[index];\n"
        body += f"{tab}}}\n"
        body += "}\n"
        body += "\n"
        body += "return NULL;"

        text = self.comment.generate_doc(
            "Returns the descriptor of the parameter called *pName*.",
            params=["pName Name of the parameter; a field of a structure is\n *              listed under its dotted name, e.g. \"Position.Home.Lat\"."],
            returns="const sParameterDescriptor* NULL when no such parameter exists.")
        text += self.function.generate_begin(DESCRIPTOR_TYPE, GET_BY_NAME_FUNCTION,
                                             "const char *pName")
        text += self.function.generate_body(body)
        text += self.function.generate_end()
        return text + "\n"

    # -- read and write by index ---------------------------------------------
    def _generate_by_index(self) -> str:
        """``fParameterList_U8_ReadByIndex`` and ``..._WriteByIndex`` for every data type.  (Asked for.)

        The smart-data functions take the object - fSmartData_U8_Read(&obj,
        &value) - which a caller holding only an index cannot name.  These take
        the index, and have the same shape otherwise: the same value pointer,
        the same eSmartDataStatus.

        Each checks the index, and that the object at it really is of that type
        before casting it: its core says so, the constructor wrote it.  A wrong
        index must be refused, not write a uint8_t over a float.  The write is
        the plain smart-data write: no change event, like fSmartData_U8_Write.
        """
        text = ""
        for value_type in VALUE_TYPES.values():
            text += self._by_index(value_type, read=True)
            text += self._by_index(value_type, read=False)
        return text

    def _by_index(self, value_type: CValueType, read: bool) -> str:
        """One of the two functions for one data type."""
        tab = self.tab
        c_name = value_type.c_name
        pointer = "pOutValue" if read else "pValue"
        name = (READ_BY_INDEX_FUNCTION if read else WRITE_BY_INDEX_FUNCTION).format(
            suffix=value_type.suffix)
        call = f"fSmartData_{value_type.suffix}_{'Read' if read else 'Write'}"

        body = f"const sParameterDescriptor *pDescriptor = {GET_BY_INDEX_FUNCTION}(index);\n"
        body += "\n"
        body += "if (pDescriptor == NULL) {\n"
        body += f"{tab}return eSMART_DATA_ERROR_NULL_POINTER;\n"
        body += "}\n"
        body += "\n"
        body += (f"if (((const sSmartDataCore *)pDescriptor->{FIELD_SMART_DATA})->TypeInfo.Type"
                 f" != {value_type.enum_name}) {{\n")
        body += f"{tab}return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;\n"
        body += "}\n"
        body += "\n"
        body += (f"return {call}(({value_type.smart_data_struct} *)"
                 f"pDescriptor->{FIELD_SMART_DATA}, {pointer});")

        if read:
            brief = f"Reads the value of the {c_name} parameter at *index*."
            param = "pOutValue Where the value is written."
            returns = ["eSmartDataStatus eSMART_DATA_OK when the value came back,"]
        else:
            brief = f"Writes the value of the {c_name} parameter at *index*."
            param = "pValue The value to write."
            returns = ["eSmartDataStatus eSMART_DATA_OK when the value was stored,"]
            # a bool_t has no range to be outside of
            if value_type.kind != "bool":
                returns.append("eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,")
        returns += [f"eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or {pointer} is NULL,",
                    f"eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a {c_name}."]

        text = self.comment.generate_doc(
            brief,
            params=[f"index Index of the parameter, see '{self.defines_header}'.", param],
            returns=returns)
        text += self.function.generate_begin("eSmartDataStatus", name,
                                             f"uint16_t index, {c_name} *{pointer}")
        text += self.function.generate_body(body)
        text += self.function.generate_end()
        return text + "\n"
