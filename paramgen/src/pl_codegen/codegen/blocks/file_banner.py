"""The doxygen banner at the top of a generated file."""

from __future__ import annotations

from typing import List, Sequence

from ..c_style import CStyle


class FileBanner:
    """Produces the ``/** ... */`` block that starts every company file.

    The layout comes from ``c.json``; this class only fills it in and inserts
    the "do not edit by hand" note under ``@brief``.
    """

    def __init__(self, style: CStyle) -> None:
        self.style = style

    def generate(self, file_name: str, brief: str, notes: Sequence[str] = ()) -> str:
        """Return the banner of *file_name* as one text block.

        file_name : e.g. ``cg_parameter_list.h``
        brief     : the text placed after ``@brief``
        notes     : extra lines placed under ``@brief`` (generation info)
        """
        lines: List[str] = []
        for line in self.style.banner_lines(file_name, brief):
            lines.append(line)
            if notes and line.strip().startswith("* @brief"):
                lines.append("  *")
                for note in notes:
                    lines.append(f"  * {note}".rstrip())

        return "\n".join(lines) + "\n"
