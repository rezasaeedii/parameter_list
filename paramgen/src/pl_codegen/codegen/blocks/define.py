"""``#define`` directives."""

from __future__ import annotations

from ..literals import safe_comment

from typing import List, Optional, Sequence, Tuple


class Define:
    """Produces ``#define`` lines.

    Use :meth:`generate` for a single define and :meth:`generate_aligned_block`
    for a group of defines whose names and values should line up.
    """

    def __init__(self) -> None:
        pass

    def generate(self, name: str, value: str = "", comment: Optional[str] = None) -> str:
        """One ``#define NAME VALUE  /*!< comment */`` line."""
        text = f"#define {name}"
        if value:
            text += f"  {value}"
        if comment:
            text += f"  /*!< {safe_comment(comment)} */"
        return text + "\n"

    def generate_aligned_block(
            self, entries: Sequence[Tuple[str, str, Optional[str]]]) -> str:
        """A block of ``(name, value, comment)`` defines with aligned columns."""
        if not entries:
            return ""

        name_width = max(len(name) for name, _value, _comment in entries)
        value_width = max(len(value) for _name, value, _comment in entries)

        lines: List[str] = []
        for name, value, comment in entries:
            text = f"#define {name.ljust(name_width)}"
            if value:
                text += f"  {value.ljust(value_width) if comment else value}"
            if comment:
                text += f"  /*!< {safe_comment(comment)} */"
            lines.append(text.rstrip())
        return "\n".join(lines) + "\n"

    def generate_guarded_block(self, entries: Sequence[Tuple[str, str]]) -> str:
        """``(name, value)`` defines, each written only if it is not defined yet::

            #ifndef SYS_NAV
            #define SYS_NAV      (16U)
            #endif

        For a name the firmware may define itself: its own definition wins, and
        neither file warns about a redefinition.  The values line up.
        """
        if not entries:
            return ""
        width = max(len(name) for name, _value in entries)
        text = ""
        for name, value in entries:
            text += f"#ifndef {name}\n"
            text += f"#define {name.ljust(width)}  {value}\n"
            text += "#endif\n"
        return text
