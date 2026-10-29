"""The section separator lines of a company C file."""

from __future__ import annotations

from ..c_style import CStyle


class SectionMarker:
    """Produces one section line, e.g.::

        /* Includes ----------------------------------------------------------------- */

    The exact text comes from ``c.json`` so the generated files match the
    company template character for character.
    """

    def __init__(self, style: CStyle) -> None:
        self.style = style

    def generate(self, name: str) -> str:
        """``name`` is e.g. ``Includes`` or ``Exported defines``."""
        return self.style.marker(name) + "\n"
