"""``typedef enum`` blocks."""

from __future__ import annotations

from typing import Sequence, Tuple


class Enum:
    """Produces a ``typedef enum { ... } eName;`` block."""

    def __init__(self, indent: str = "    ") -> None:
        self.indent = indent

    def generate(self, type_name: str, members: Sequence[Tuple[str, int]]) -> str:
        """``members`` is a sequence of ``(name, value)`` pairs."""
        if not members:
            return ""

        width = max(len(name) for name, _value in members)

        text = "typedef enum {\n"
        text += "\n"
        for index, (name, value) in enumerate(members):
            comma = "," if index < len(members) - 1 else ""
            text += f"{self.indent}{name.ljust(width)} = {value}{comma}\n"
        text += "\n"
        text += f"}} {type_name};\n"
        return text
