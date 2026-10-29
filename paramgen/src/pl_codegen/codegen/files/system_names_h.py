"""Builds ``nsrSystemNames.h`` - the sub-systems, as ``#define``s.  (Asked for.)

The third file of the ``param_table`` format, beside the table and the offsets
note, and it holds one thing only: every name of the machine's ``SYSTEM NAMES``
drop-down list with its number::

    #ifndef SYS_NAV
    #define SYS_NAV              (16)
    #endif

The table needs exactly these: its ``#if DESIRED_SUB_SYSTEM == SYS_NAV`` lines
compare them in the preprocessor, which only understands macros - an enum
constant there would silently count as 0.  The number is the one the Drop-down
lists dialog gives the name (``SYS_NAV = 16``), the same one a smart-data
project writes, and a name without one takes the number after the line above
it.  Each name is written only ``#ifndef``: the firmware may define it itself,
and then its definition is the one used.

Nothing includes it - the firmware does, where it needs the names - so the
table and the offsets note are exactly what they were before it existed.
"""

from __future__ import annotations

from typing import List, Tuple

from ...model.defines import COLUMN_SYSTEM_NAMES
from ..literals import define_number_literal
from .file_builder import FileBuilder
from .param_table_h import FILE_NAME as TABLE_FILE

#: The file this builder produces.
FILE_NAME = "nsrSystemNames.h"


class SystemNamesHeader(FileBuilder):
    """The machine's system names with their numbers, nothing else."""

    @property
    def file_name(self) -> str:
        return FILE_NAME

    def generate(self) -> str:
        text = ""

        # ---- banner and guard --------------------------------------------
        text += self.banner.generate(
            self.file_name,
            "The sub-systems of the Drop-down lists, as #defines.",
            self.generation_notes())
        text += "\n"
        text += self.guard.generate_open(self.guard_name)
        text += "\n"

        # ---- the names ---------------------------------------------------
        text += self.comment.generate_line(
            f"Every SYSTEM NAMES entry, for the #if lines of {TABLE_FILE} "
            f"(kept where already defined)")
        text += self.define.generate_guarded_block(self._entries())
        text += "\n"

        # ---- closing guard -----------------------------------------------
        text += self.guard.generate_close(self.guard_name)
        return text

    def _entries(self) -> List[Tuple[str, str]]:
        """``(name, "(number)")`` for every system name, in the list's order.

        Written the way the table writes its own numbers - ``(16)``, no ``U`` -
        because it is the same hand-written firmware that reads both; a
        negative one is ``(-5)``.
        """
        return [(name, define_number_literal(number, suffix=""))
                for name, number in self.model.defines.numbered(COLUMN_SYSTEM_NAMES)]
