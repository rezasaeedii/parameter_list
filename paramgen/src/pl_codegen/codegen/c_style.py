"""Reads the company file style out of the VS Code snippet file ``c.json``.

The generated files must look exactly like the files a developer gets when he
presses ``h-file`` / ``c-file`` in VS Code.  Instead of hard-coding that layout
in Python, this module pulls three things out of ``c.json``:

    banner_lines()     the doxygen block at the top of every file
    marker(name)       one section line, e.g.
                       ``/* Includes ------------------------------------ */``
    footer_line()      the ``/* === Copyright (c) 2026 FAS === EOF === */`` line

If ``c.json`` cannot be read, a built-in copy of the same layout is used, so the
generator always works.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_jsonc

_SNIPPET_HEADER = "Create new header file"
_SNIPPET_SOURCE = "Create new source file"

#: ``/* Includes ------------ */``  ->  name = "Includes"
_MARKER = re.compile(r"^\s*/\*\s*(?P<name>[A-Za-z][A-Za-z ]*?)\s*-{2,}\s*\*/\s*$")

#: width of a section marker line, taken from ``c.json``
_DEFAULT_MARKER_WIDTH = 78

_FALLBACK_BANNER = [
    "/**",
    "  ******************************************************************************",
    "  * @file    $TM_FILENAME",
    "  * @brief   ",
    "  ******************************************************************************",
    "  * @attention",
    "  *",
    "  * Copyright (c) $CURRENT_YEAR FAS.",
    "  * All rights reserved.",
    "  *",
    "  * This software is licensed under terms that can be found in the LICENSE file",
    "  * in the root directory of this software component.",
    "  * If no LICENSE file comes with this software, it is provided AS-IS.",
    "  *",
    "  ******************************************************************************",
    "  */",
]

_FALLBACK_FOOTER = "/* === Copyright (c) $CURRENT_YEAR FAS === EOF === */"


class CStyle:
    """The company layout, ready to be used by the block classes."""

    def __init__(self, banner: List[str], markers: Dict[str, str], footer: str,
                 company: str = "FAS", indent: str = "    ") -> None:
        self.banner = banner
        self.markers = markers
        self.footer = footer
        self.company = company
        self.indent = indent

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls, snippet_file: Optional[Path], company: str = "FAS",
             indent: str = "    ") -> "CStyle":
        banner = list(_FALLBACK_BANNER)
        footer = _FALLBACK_FOOTER
        markers: Dict[str, str] = {}

        if snippet_file is not None and snippet_file.is_file():
            data = load_jsonc(snippet_file)
            header_body = _snippet_body(data, _SNIPPET_HEADER)
            source_body = _snippet_body(data, _SNIPPET_SOURCE)

            found_banner = _extract_banner(header_body)
            if found_banner:
                banner = found_banner
            for line in header_body + source_body:
                match = _MARKER.match(line)
                if match:
                    markers.setdefault(match.group("name"), line.rstrip())
                elif "EOF ===" in line:
                    footer = line.rstrip()

        return cls(banner, markers, footer, company, indent)

    # -- the three things the blocks need --------------------------------
    def banner_lines(self, file_name: str, brief: str) -> List[str]:
        """The doxygen banner of *file_name*, with the placeholders filled in."""
        year = str(datetime.now().year)
        lines: List[str] = []
        for raw in self.banner:
            line = (raw.replace("$TM_FILENAME_BASE", file_name.rsplit(".", 1)[0])
                       .replace("$TM_FILENAME", file_name)
                       .replace("$CURRENT_YEAR", year))
            if self.company != "FAS":
                line = line.replace("FAS", self.company)
            if line.strip().startswith("* @brief"):
                line = f"  * @brief   {brief}".rstrip()
            lines.append(line.rstrip())
        return lines

    def marker(self, name: str) -> str:
        """One section line, e.g. ``/* Includes ------------------ */``."""
        known = self.markers.get(name)
        if known:
            return known
        dashes = max(3, _DEFAULT_MARKER_WIDTH - len(name) - 8)
        return f"/* {name} {'-' * dashes} */"

    def footer_line(self) -> str:
        year = str(datetime.now().year)
        line = self.footer.replace("$CURRENT_YEAR", year)
        return line.replace("FAS", self.company) if self.company != "FAS" else line


def _snippet_body(data: Dict[str, object], snippet_name: str) -> List[str]:
    snippet = data.get(snippet_name)
    if not isinstance(snippet, dict):
        return []
    body = snippet.get("body")
    return [str(line) for line in body] if isinstance(body, list) else []


def _extract_banner(body: List[str]) -> List[str]:
    """The first ``/** ... */`` block of a snippet body."""
    if not body or not body[0].strip().startswith("/**"):
        return []
    lines: List[str] = []
    for line in body:
        lines.append(line)
        if line.strip() == "*/":
            return lines
    return []
