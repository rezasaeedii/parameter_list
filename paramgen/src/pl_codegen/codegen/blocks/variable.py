"""Variable declarations and definitions."""

from __future__ import annotations

from ..literals import safe_comment

from typing import Optional


class Variable:
    """Produces one variable line.

    ``generate_declaration`` writes the ``extern`` line for a header,
    ``generate_definition`` writes the real definition for a ``.c`` file.
    """

    def __init__(self) -> None:
        pass

    def generate_declaration(self, c_type: str, name: str,
                             array_size: Optional[str] = None,
                             qualifier: str = "",
                             comment: Optional[str] = None) -> str:
        return self._line("extern ", c_type, name, array_size, qualifier, comment)

    def generate_definition(self, c_type: str, name: str,
                            array_size: Optional[str] = None,
                            qualifier: str = "",
                            comment: Optional[str] = None) -> str:
        return self._line("", c_type, name, array_size, qualifier, comment)

    @staticmethod
    def _line(prefix: str, c_type: str, name: str, array_size: Optional[str],
              qualifier: str, comment: Optional[str]) -> str:
        text = prefix
        if qualifier:
            text += f"{qualifier} "
        text += f"{c_type} {name}"
        if array_size:
            text += f"[{array_size}]"
        text += ";"
        if comment:
            text += f"  /*!< {safe_comment(comment)} */"
        return text + "\n"
