"""The last line of every generated file."""

from __future__ import annotations

from ..c_style import CStyle


class FileFooter:
    """Produces ``/* === Copyright (c) 2026 FAS === EOF === */``."""

    def __init__(self, style: CStyle) -> None:
        self.style = style

    def generate(self) -> str:
        return self.style.footer_line() + "\n"
