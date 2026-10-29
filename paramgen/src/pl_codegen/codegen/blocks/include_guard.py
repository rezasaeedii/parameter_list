"""The ``#ifndef`` / ``#define`` / ``#endif`` guard of a header file."""

from __future__ import annotations


class IncludeGuard:
    """Produces the double-inclusion guard of a header."""

    def __init__(self) -> None:
        pass

    def generate_open(self, guard: str) -> str:
        """``guard`` is e.g. ``CG_PARAMETER_LIST_H``."""
        text = "/* Define to prevent recursive inclusion -------------------------------------*/\n"
        text += f"#ifndef {guard}\n"
        text += f"#define {guard}\n"
        return text

    def generate_close(self, guard: str) -> str:
        return f"#endif /* {guard} */\n"
