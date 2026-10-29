"""Builds ``nsrParamOffsets.h`` - the note that says where each value sits.

The ``param_table`` format generates one table of ``ADD_PARAM(...)`` lines and
nothing else.  What that table does not say is **where in memory** a parameter
ends up: the firmware lays the values of a sub-system out one after another, so
the third parameter's offset is the sum of the sizes of the two above it.  That
sum is easy to get wrong by hand and impossible to see in the table.

So this file is written beside it, and it is **entirely comments** - every line
of it starts inside a ``/* ... */``.  Including it compiles to nothing; the
point is to be able to look something up, and to have that answer regenerated
whenever the list changes instead of kept in somebody's head.

One thing worth saying out loud, because it is the reason the numbers move:
**a disabled parameter is not in here at all.**  It takes no index and no
offset, so switching one off shifts the index *and* the offset of everything
after it in its sub-system - which is exactly what the two files agree on,
because both are built from the same enabled leaves in the same order.
"""

from __future__ import annotations

from typing import List, Tuple

from ...model.parameter import Parameter
from .file_builder import FileBuilder
from .param_table_h import FILE_NAME as TABLE_FILE
from .param_table_h import blocks_by_system, c_type_of

#: The file this builder produces, named after the table it explains.
FILE_NAME = "nsrParamOffsets.h"

#: The column headings of the table inside the comment.
HEADINGS = ("index", "offset", "size", "type", "parameter")


class ParamOffsetsHeader(FileBuilder):
    """The memory map of a parameter table, as a comment."""

    @property
    def file_name(self) -> str:
        return FILE_NAME

    def generate(self) -> str:
        text = ""

        # ---- banner ------------------------------------------------------
        text += self.banner.generate(
            self.file_name,
            "Where each parameter sits in memory - a note, not code.",
            self.generation_notes())
        text += "\n"

        text += ("/*\n"
                 "  Every line of this file is a comment: including it compiles to\n"
                 "  nothing.  It is here to be read.\n"
                 "\n"
                 "  The values of one sub-system are laid out one after another, so a\n"
                 "  parameter's offset is the sum of the sizes of the ones above it in\n"
                 "  its own sub-system.  Each sub-system starts again at 0, the same way\n"
                 f"  the index column of {TABLE_FILE} does.\n"
                 "\n"
                 "  A DISABLED parameter is not here and is not in the table either: it\n"
                 "  takes no index and no byte, so switching one off moves the index and\n"
                 "  the offset of everything after it in its sub-system.\n"
                 "\n"
                 "  No padding is added between values: the offsets are a plain running\n"
                 "  total of the sizes.\n"
                 "*/\n\n")

        for system, rows in self._blocks():
            text += self._block(system, rows)

        return text

    # -- the blocks --------------------------------------------------------
    def _blocks(self) -> List[Tuple[str, List[Parameter]]]:
        """The same grouping the table itself uses - literally the same code.

        The two files have to put the same parameters in the same sub-system in
        the same order, or the index printed here would not be the index over
        there, and a note that disagrees with the thing it explains is worse
        than no note.
        """
        return blocks_by_system(self.parameters, self.config.inputs.model_files)

    def _block(self, system: str, parameters: List[Parameter]) -> str:
        """One sub-system's table, offsets running from zero."""
        rows: List[Tuple[str, ...]] = []
        offset = 0
        for index, parameter in enumerate(parameters):
            value_type = parameter.value_type
            if value_type is None:
                # validation has already refused this by name; leaving the row
                # out keeps the rest of the map readable while it is fixed
                continue
            size = value_type.value_size * max(1, parameter.array_size)
            rows.append((str(index), str(offset), str(size),
                         c_type_of(value_type), parameter.name))
            offset += size

        widths = [max([len(heading)] + [len(row[column]) for row in rows])
                  for column, heading in enumerate(HEADINGS)]

        def line(cells) -> str:
            # the last column is the name, so it is not padded
            padded = "  ".join(f"{cell:>{widths[column]}}"
                               for column, cell in enumerate(cells[:-1]))
            return f"     {padded}  {cells[-1]}".rstrip()

        text = f"/* ---- {system} "
        text += "-" * max(3, 72 - len(text)) + "\n"
        text += line(HEADINGS) + "\n"
        for row in rows:
            text += line(row) + "\n"
        text += f"\n     {len(rows)} parameter(s), {offset} byte(s) in total\n"
        text += "*/\n\n"
        return text
