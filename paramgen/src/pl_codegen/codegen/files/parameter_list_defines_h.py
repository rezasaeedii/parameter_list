"""Builds ``cg_parameter_list_defines.h``.

Read ``generate()`` from top to bottom: it is the generated file, in order.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...model.defines import GENERATED_DEFINES
from ...model.tags import TAG_REGISTRY
from ..literals import define_number_literal
from .file_builder import FileBuilder

BRIEF = "Quantities, parameter indices, tag sizes, system names and parameter modes."


class ParameterListDefinesHeader(FileBuilder):
    """``PARAMETER_LIST_QTY``, the indices, the tag sizes and the list defines."""

    @property
    def file_name(self) -> str:
        return self.defines_header

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
        text += self.include.generate("stdint.h", standard=True)
        text += "\n"

        # ---- exported defines -------------------------------------------
        text += self.marker.generate("Exported defines")

        text += self.comment.generate_line("Number of parameters in the parameter list")
        text += self.define.generate(self.quantity, f"({len(self.parameters)}U)",
                                     "Number of enabled parameters")
        text += "\n"

        text += self.comment.generate_line("Index of every parameter inside the parameter list")
        text += self.define.generate_aligned_block(self._index_entries())
        text += "\n"

        array_entries = self._array_size_entries()
        if array_entries:
            text += self.comment.generate_line("Array size of every array parameter")
            text += self.define.generate_aligned_block(array_entries)
            text += "\n"

        text += self.comment.generate_line("Total size used by every tag")
        text += self.define.generate_aligned_block(self._tag_total_entries())
        text += "\n"

        # The sub-systems and the access modes the tags name.  Defines, not
        # enums, so each can have any number the drop-down list gives it, and
        # each only #ifndef: the firmware may define SYS_NAV itself, and then
        # its definition is the one used.
        text += self._list_defines()

        # A tag's MemoryOffset used to be a macro here as well - one per
        # (tag, parameter) pair - so it could be poured into the descriptor
        # table.  A tag field is a bare value now, nothing in the descriptor
        # needs the offset any more, and the offset itself did not go anywhere:
        # it is still worked out exactly as before and drawn, per parameter,
        # in cg_parameter_list_table.h - a file of comments meant for a human
        # to read, which is the only place that still needs it.

        # ---- exported macros / types ------------------------------------
        text += self.marker.generate("Exported macros")
        text += self.marker.generate("Exported types")

        # ---- the remaining empty sections -------------------------------
        text += self.marker.generate("Exported functions")
        text += self.marker.generate("Exported variables")
        text += "\n"

        # ---- closing guards and footer ----------------------------------
        text += self.cpp.generate_close()
        text += "\n"
        text += self.guard.generate_close(self.guard_name)
        text += "\n"
        text += self.footer.generate()
        return text

    # -- the define blocks -----------------------------------------------
    def _index_entries(self) -> List[Tuple[str, str, Optional[str]]]:
        entries: List[Tuple[str, str, Optional[str]]] = []
        for index, parameter in enumerate(self.parameters):
            comment = parameter.value_type_name or ""
            # Each element is its own index now, so the comment says which
            # element of which declaration it is rather than a count.
            if parameter.declared_array_size > 1:
                comment += f" (element {parameter.element_index}"                            f" of {parameter.declared_array_size})"
            unit = self.unit_of(parameter)
            if unit:
                comment += f" [{unit}]"
            entries.append((self.index_of(parameter), f"({index}U)", comment.strip() or None))
        return entries

    def _array_size_entries(self) -> List[Tuple[str, str, Optional[str]]]:
        # One macro per array DECLARATION: a top level parameter's own array, or
        # an array field of a structure TYPE - which every parameter of that type
        # shares, so 'Stest.alive' is declared once however many parameters use
        # 'Stest'.
        return [(self.array_size_of_name(declaration), f"({size}U)",
                 f"Number of elements of '{declaration}'")
                for declaration, size, _node in self.model.array_declarations()]

    def _tag_total_entries(self) -> List[Tuple[str, str, Optional[str]]]:
        entries: List[Tuple[str, str, Optional[str]]] = []
        for spec in TAG_REGISTRY:
            area = self.offsets.area(spec.tag_id)
            if area is None or not area.entries:
                continue
            entries.append((self.offset_total_of(spec.tag_id), f"({area.total}U)",
                            f"Bytes used by tag '{spec.tag_id}' "
                            f"({len(area.entries)} parameter(s))"))
        return entries

    # -- the system names and the parameter modes -------------------------
    def _list_defines(self) -> str:
        text = ""
        for column in GENERATED_DEFINES:
            entries = [(name, define_number_literal(number))
                       for name, number in self.model.defines.numbered(column)]
            if not entries:
                continue
            text += self.comment.generate_line(
                f"Values of the '{column}' drop-down list (kept where already defined)")
            text += self.define.generate_guarded_block(entries)
            text += "\n"
        return text
