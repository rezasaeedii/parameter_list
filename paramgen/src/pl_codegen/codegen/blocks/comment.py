"""C comments: one-liners, doxygen blocks and the big function separators."""

from __future__ import annotations

from ..literals import safe_comment

from typing import List, Optional, Sequence


class Comment:
    """Produces every kind of comment used in the generated files."""

    def __init__(self) -> None:
        pass

    def generate_line(self, text: str) -> str:
        """``/* text */``"""
        return f"/* {safe_comment(text)} */\n"

    def generate_doc(self, brief: str, params: Sequence[str] = (),
                     notes: Sequence[str] = (), returns: Optional[str] = None) -> str:
        """A doxygen block::

            /**
             * @brief ...
             *
             * @param ...
             * @note  ...
             * @return ...
             */
        """
        lines: List[str] = ["/**"]
        brief = safe_comment(brief)
        params = [safe_comment(param) for param in params]
        for index, line in enumerate(str(brief).splitlines() or [""]):
            lines.append(f" * @brief {line}".rstrip() if index == 0
                         else f" *        {line}".rstrip())
        lines.append(" *")
        for param in params:
            lines.append(f" * @param {param}")
        for note in notes:
            for index, line in enumerate(str(safe_comment(note)).splitlines()):
                lines.append(f" * @note  {line}".rstrip() if index == 0
                             else f" *        {line}".rstrip())
        if returns:
            lines.append(f" * @return {safe_comment(returns)}")
        lines.append(" */")
        return "\n".join(lines) + "\n"

    def generate_separator(self, title: str) -> str:
        """The big separator used before the function bodies of a ``.c`` file::

            /*
              ==============================================================================
                                    ##### Exported Functions #####
              ==============================================================================
            */
        """
        rule = "  " + "=" * 78
        text = "/*\n"
        text += rule + "\n"
        text += f"                        ##### {title} #####\n"
        text += rule + "\n"
        text += "*/\n"
        return text

    def generate_block(self, lines: Sequence[str], title: Optional[str] = None) -> str:
        """A plain ``/* ... */`` block holding arbitrary text (used for tables)."""
        text = "/*\n"
        if title:
            text += f"  {title}\n\n"
        for line in lines:
            text += f"  {safe_comment(line)}".rstrip() + "\n"
        text += "*/\n"
        return text
