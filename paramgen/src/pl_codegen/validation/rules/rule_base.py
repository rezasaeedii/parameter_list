"""Base class shared by every validation rule.

A rule is a small, self-contained class with one job.  Adding a new check means
adding one file in this folder and listing the class in ``rules/__init__.py``.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from typing import List

from ...config import Config
from ...errors import DiagnosticCollector
from ...model.parameter import Parameter
from ...model.parameter_list import PATH_SEPARATOR, ParameterList


class ValidationRule(ABC):
    """One check performed on the whole parameter list."""

    #: short, stable identifier used as a diagnostic code prefix
    rule_id: str = "RULE"
    #: one-line description shown by ``run_generate.py --list-rules``
    description: str = ""

    def __init__(self, config: Config) -> None:
        self.config = config

    @abstractmethod
    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        """Inspect *model* and append findings to *diagnostics*."""

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        return f"{self.rule_id}: {self.description}"


def enabled_nodes(model: ParameterList) -> List[Parameter]:
    """Every enabled node of the tree, structs included."""
    found: List[Parameter] = []
    for parameter in model.parameters:
        _walk_enabled(parameter, found)
    return found


def enabled_leaves(model: ParameterList) -> List[Parameter]:
    """Every enabled primitive node (structs excluded)."""
    return [node for node in enabled_nodes(model) if node.is_primitive]


#: ``Wheels[3].Speed`` -> ``Wheels.Speed``: the declaration behind a value.
_ELEMENT_INDEX = re.compile(r"\[\d+\]")


def declared_values(model: ParameterList) -> List[Parameter]:
    """:meth:`~ParameterList.flatten`, but one entry per *declaration*.

    ``flatten()`` is the code generator's view of the list: one entry per
    value, so ``CellVoltage[6]`` is six entries and a field of ``Motor[2]``
    appears twice.  That is right for a table with a row per value, and wrong
    for a rule: a missing tag on ``CellVoltage`` is **one** mistake, and
    reporting it once per element turned a single empty cell into six
    identical errors - a 70000-element array into 350000 of them, which is
    not a Problems panel any more.

    Rules that check a property of the *value* (its log id, its offset) keep
    using ``flatten()``.  Everything that checks a property of the
    declaration - its tags, its type, its name - uses this.

    The inherited tags and type that ``flatten()`` hands down are kept, since
    that is exactly what the tag rules need to see.
    """
    seen = set()
    unique: List[Parameter] = []
    for leaf in model.flatten():
        key = (leaf.source.file, _ELEMENT_INDEX.sub("", leaf.name))
        if key in seen:
            continue
        seen.add(key)
        unique.append(leaf)
    return unique


def enabled_structs(model: ParameterList) -> List[Parameter]:
    """Every enabled struct node."""
    return [node for node in enabled_nodes(model) if node.is_struct]


def dotted_names(model: ParameterList) -> List[str]:
    """The dotted path of every enabled node, in tree order."""
    found: List[str] = []
    for parameter in model.parameters:
        _walk_paths(parameter, [], found)
    return found


def _walk_enabled(node: Parameter, found: List[Parameter]) -> None:
    if not node.enable:
        return
    found.append(node)
    for child in node.children:
        _walk_enabled(child, found)


def _walk_paths(node: Parameter, path: List[str], found: List[str]) -> None:
    if not node.enable:
        return
    path = path + [node.name]
    found.append(PATH_SEPARATOR.join(path))
    for child in node.children:
        _walk_paths(child, path, found)
