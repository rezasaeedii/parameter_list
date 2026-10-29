"""Diagnostic (error / warning) infrastructure.

Every problem detected while reading a parameter list or generating code is
reported as a :class:`Diagnostic` instead of raising an exception, so that a
single run can report *all* problems at once.  Only unrecoverable problems
(missing file, unreadable XML, ...) raise :class:`CodeGeneratorError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

from .logging_utils import BRIGHT_RED, CYAN, GREY, YELLOW, paint


class CodeGeneratorError(Exception):
    """Unrecoverable error: the tool cannot continue at all."""


class Severity(IntEnum):
    """Severity of a diagnostic, ordered from least to most severe."""

    INFO = 0
    WARNING = 1
    ERROR = 2

    @property
    def label(self) -> str:
        return {Severity.INFO: "info", Severity.WARNING: "warning", Severity.ERROR: "error"}[self]


#: What each severity looks like on a console.  INFO is left alone: it is the
#: commonest line by far, and colouring it would drown out the two that matter.
_SEVERITY_COLOUR = {
    Severity.INFO: CYAN,
    Severity.WARNING: YELLOW,
    Severity.ERROR: BRIGHT_RED,
}


@dataclass(frozen=True)
class SourceLocation:
    """Where a diagnostic comes from (a parameter, an XML node or a file)."""

    file: Optional[str] = None
    sheet: Optional[str] = None
    row: Optional[int] = None
    column: Optional[str] = None
    #: dotted path of the parameter, e.g. ``Position.Home.Lat`` - this is what
    #: the GUI uses to jump to the offending parameter
    parameter: Optional[str] = None
    #: the structure TYPE a diagnostic is about, when it is about one.  A type
    #: is not a parameter to jump to, so the GUI opens 'Structure types…' on it.
    struct_type: Optional[str] = None

    def __str__(self) -> str:
        parts: List[str] = []
        if self.struct_type:
            parts.append(f"structure type '{self.struct_type}'")
        if self.parameter:
            parts.append(f"parameter '{self.parameter}'")
        if self.file:
            parts.append(str(self.file))
        if self.sheet:
            parts.append(f"[{self.sheet}]")
        if self.row is not None:
            parts.append(f"row {self.row}")
        if self.column:
            parts.append(f"column '{self.column}'")
        return " ".join(parts) if parts else "<unknown location>"

    def to_dict(self) -> Dict[str, object]:
        return {"file": self.file, "sheet": self.sheet, "row": self.row,
                "column": self.column, "parameter": self.parameter,
                "structType": self.struct_type}


@dataclass(frozen=True)
class Diagnostic:
    """A single problem found by the tool."""

    severity: Severity
    code: str
    message: str
    location: SourceLocation = field(default_factory=SourceLocation)
    hint: Optional[str] = None

    def render(self) -> str:
        """One diagnostic as the console shows it.

        The severity word and the code carry the colour, not the whole block:
        the message and the hint are prose the reader is meant to read, and
        prose in colour is harder to read, not easier.  The colour is there to
        make an ERROR findable *without* reading.
        """
        head = f"{self.severity.label.upper():7s} {self.code}:"
        text = (f"{paint(head, _SEVERITY_COLOUR[self.severity])} {self.message}"
                f"\n            at {paint(str(self.location), GREY)}")
        if self.hint:
            text += f"\n            hint: {paint(self.hint, GREY)}"
        return text

    def to_dict(self) -> Dict[str, object]:
        return {
            "severity": self.severity.label,
            "code": self.code,
            "message": self.message,
            "location": self.location.to_dict(),
            "hint": self.hint,
        }


class DiagnosticCollector:
    """Collects diagnostics produced anywhere in the pipeline."""

    def __init__(self) -> None:
        self._items: List[Diagnostic] = []

    # -- adding ----------------------------------------------------------
    def add(self, diagnostic: Diagnostic) -> None:
        self._items.append(diagnostic)

    def error(self, code: str, message: str, location: Optional[SourceLocation] = None,
              hint: Optional[str] = None) -> None:
        self.add(Diagnostic(Severity.ERROR, code, message, location or SourceLocation(), hint))

    def warning(self, code: str, message: str, location: Optional[SourceLocation] = None,
                hint: Optional[str] = None) -> None:
        self.add(Diagnostic(Severity.WARNING, code, message, location or SourceLocation(), hint))

    def info(self, code: str, message: str, location: Optional[SourceLocation] = None,
             hint: Optional[str] = None) -> None:
        self.add(Diagnostic(Severity.INFO, code, message, location or SourceLocation(), hint))

    # -- querying --------------------------------------------------------
    @property
    def items(self) -> List[Diagnostic]:
        return list(self._items)

    def count(self, severity: Severity) -> int:
        return sum(1 for item in self._items if item.severity is severity)

    @property
    def has_errors(self) -> bool:
        return self.count(Severity.ERROR) > 0

    @property
    def has_warnings(self) -> bool:
        return self.count(Severity.WARNING) > 0

    def __len__(self) -> int:
        return len(self._items)

    # -- reporting -------------------------------------------------------
    def render(self, min_severity: Severity = Severity.INFO) -> str:
        selected = [item for item in self._items if item.severity >= min_severity]
        if not selected:
            return "No problems found."
        selected.sort(key=lambda item: (-int(item.severity), item.location.file or "",
                                        item.location.row or 0, item.code))
        return "\n".join(item.render() for item in selected)

    def summary(self) -> str:
        """The tally, with the counts that are not zero picked out."""
        errors = self.count(Severity.ERROR)
        warnings = self.count(Severity.WARNING)
        infos = self.count(Severity.INFO)
        return (f"{paint(f'{errors} error(s)', BRIGHT_RED if errors else '')}, "
                f"{paint(f'{warnings} warning(s)', YELLOW if warnings else '')}, "
                f"{infos} info message(s)")

    def to_list(self) -> List[Dict[str, object]]:
        return [item.to_dict() for item in self._items]
