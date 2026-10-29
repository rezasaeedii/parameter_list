"""Function prototypes and function bodies."""

from __future__ import annotations


class Function:
    """Produces the pieces of a C function.

    A header file uses :meth:`generate_prototype`; a source file writes
    :meth:`generate_begin`, then its body lines, then :meth:`generate_end`.
    """

    def __init__(self, indent: str = "    ") -> None:
        self.indent = indent

    def generate_prototype(self, return_type: str, name: str,
                           arguments: str = "void", qualifier: str = "") -> str:
        return self._signature(return_type, name, arguments, qualifier) + ";\n"

    def generate_begin(self, return_type: str, name: str,
                       arguments: str = "void", qualifier: str = "") -> str:
        text = self._signature(return_type, name, arguments, qualifier) + " {\n"
        text += "\n"
        return text

    def generate_end(self) -> str:
        return "\n}\n"

    def generate_body(self, text: str, level: int = 1) -> str:
        """Indent one or more body lines by *level* tabs."""
        out = ""
        for line in text.splitlines():
            out += (self.indent * level + line).rstrip() + "\n" if line.strip() else "\n"
        return out

    @staticmethod
    def _signature(return_type: str, name: str, arguments: str, qualifier: str) -> str:
        prefix = f"{qualifier} " if qualifier else ""
        return f"{prefix}{return_type} {name}({arguments})"
