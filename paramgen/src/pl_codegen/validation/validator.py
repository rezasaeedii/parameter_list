"""Runs every validation rule over the model."""

from __future__ import annotations

from typing import List

from ..config import Config
from ..errors import DiagnosticCollector, SourceLocation
from ..model.parameter_list import ParameterList
from .rules import ALL_RULES, ValidationRule


class Validator:
    """Applies :data:`~pl_codegen.validation.rules.ALL_RULES` to a model."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._rules: List[ValidationRule] = [rule(config) for rule in ALL_RULES]

    @property
    def rules(self) -> List[ValidationRule]:
        return list(self._rules)

    def validate(self, model: ParameterList, diagnostics: DiagnosticCollector) -> bool:
        """Run all rules; return ``True`` when code generation may continue."""
        model.assign_paths()
        for rule in self._rules:
            rule.check(model, diagnostics)

        if not model.flatten() and not self._config.inputs.model_files \
                and not model.source_files:
            # Not "the list is empty": there is no list.  A new project starts
            # like this, and "add a parameter" would be the wrong advice - a
            # parameter lives in a list, so the list has to come first.
            diagnostics.error(
                "VAL002",
                "This project has no parameter sub list, so there is nothing to "
                "generate.",
                SourceLocation(file=str(self._config.path) if self._config.path
                               else None),
                hint="A parameter lives in a parameter sub list. In the editor: "
                     "'Parameter sub lists' (\u2630) > '+ Add parameter sub list'. "
                     "Or name one in inputs.model_files in the project file.")
        elif not model.flatten():
            # Even an empty list has a file behind it, and naming it is the
            # difference between "which one of my six lists?" and an answer.
            files = ", ".join(model.source_files)
            diagnostics.error(
                "VAL001",
                f"The parameter list is empty; nothing would be generated."
                f"{f'  (read from {files})' if files else ''}",
                SourceLocation(file=model.source_files[0] if model.source_files else None),
                hint="Add a parameter, or enable one of the existing ones.")

        if diagnostics.has_errors:
            return False
        if self._config.validation.treat_warnings_as_errors and diagnostics.has_warnings:
            return False
        return True
