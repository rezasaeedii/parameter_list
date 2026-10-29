"""The ``extern "C"`` guard that makes a header usable from C++."""

from __future__ import annotations


class CppGuard:
    """Produces the ``#ifdef __cplusplus`` wrapper of a header."""

    def __init__(self) -> None:
        pass

    def generate_open(self) -> str:
        text = "#ifdef __cplusplus\n"
        text += 'extern "C" {\n'
        text += "#endif\n"
        return text

    def generate_close(self) -> str:
        text = "#ifdef __cplusplus\n"
        text += "}\n"
        text += "#endif\n"
        return text
