"""Rules about default value, minimum, maximum and resolution."""

from __future__ import annotations

from ...errors import DiagnosticCollector
from ...model.parameter_list import ParameterList
from .rule_base import ValidationRule, enabled_leaves


class NativeRangeRule(ValidationRule):
    """Values must fit into the C type of the parameter."""

    rule_id = "RANGE_NATIVE"
    description = "Default/minimum/maximum must fit into the declared C type."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            value_type = parameter.value_type
            if value_type is None or value_type.is_bool:
                continue
            for label, value in (("DefaultValue", parameter.default_value),
                                 ("Minimum", parameter.minimum),
                                 ("Maximum", parameter.maximum),
                                 ("Resolution", parameter.resolution)):
                if value is None:
                    continue
                low, high = value_type.native_min, value_type.native_max
                if low is None or high is None:
                    continue
                if float(value) < float(low) or float(value) > float(high):
                    diagnostics.error(
                        "RNG001",
                        f"'{label}' = {value} does not fit into '{value_type.c_name}' "
                        f"(allowed: {low} .. {high}).", parameter.source,
                        hint=f"Write a value between {low} and {high}, or choose a "
                             f"wider value type.")


class MinMaxOrderRule(ValidationRule):
    """The minimum must not be greater than the maximum."""

    rule_id = "RANGE_ORDER"
    description = "Minimum must be smaller than or equal to maximum."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            value_type = parameter.value_type
            if value_type is None or not value_type.has_range:
                continue
            # 'both empty' is the no-range case and is fine; but one cell filled
            # in and the other empty is a real range whose empty end counts as
            # 0, and that can easily be the wrong way round
            if parameter.range_disabled:
                continue
            minimum = parameter.effective_minimum
            maximum = parameter.effective_maximum
            if minimum is None or maximum is None:
                continue
            if float(minimum) > float(maximum):
                written = ("" if parameter.minimum is not None
                           and parameter.maximum is not None
                           else "  (an empty limit cell counts as 0)")
                diagnostics.error(
                    "RNG002",
                    f"Minimum ({minimum}) is greater than maximum ({maximum}).{written} "
                    f"The smart-data constructor would refuse every value.",
                    parameter.source,
                    hint="Swap the two cells, or leave both empty to allow the whole "
                         "range of the type.")


class DefaultInRangeRule(ValidationRule):
    """The default value must be inside the allowed range.

    A minimum *and* a maximum of zero (or both empty) means "no range", and the
    generated code then uses the full native range of the type - so there is
    nothing to check.  In every other case the check uses the *effective*
    limits, which is what the constructor will really be given: an empty cell
    next to a filled one counts as zero.
    """

    rule_id = "RANGE_DEFAULT"
    description = "The default value must lie inside [minimum, maximum]."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            value_type = parameter.value_type
            if value_type is None or not value_type.has_range:
                continue
            if parameter.range_disabled:
                continue

            # An empty DefaultValue cell is generated as 0 - and 0 is outside
            # a range such as [10, 100], so the constructor would refuse it and
            # fParameterList_Init() would fail on the target.  Checking only
            # the cells the user filled in would miss exactly that.
            default = 0 if parameter.default_value is None else parameter.default_value

            minimum = parameter.effective_minimum
            maximum = parameter.effective_maximum
            if minimum is None or maximum is None:
                continue

            value = float(default)
            if value < float(minimum) or value > float(maximum):
                notes = []
                if parameter.default_value is None:
                    notes.append("an empty DefaultValue cell is generated as 0")
                if parameter.minimum is None or parameter.maximum is None:
                    notes.append("an empty limit cell counts as 0")
                written = f"  ({'; '.join(notes)})" if notes else ""
                diagnostics.error(
                    "RNG003",
                    f"Default value {default} is outside the allowed range "
                    f"[{minimum}, {maximum}].{written} "
                    f"The smart-data constructor would refuse it at run time.",
                    parameter.source,
                    hint="Leave Minimum and Maximum both empty (or both 0) to allow the "
                         "whole range of the type.")


class IntegralValueRule(ValidationRule):
    """An integer type may only carry whole numbers.

    A fractional value is not rejected by the model - the XML holds whatever was
    typed - and it is not rejected by C either: an integer literal of 1.2 is
    simply 1.  So the generated firmware quietly used a different number from
    the one on screen, with nothing anywhere to say so.

    This is an error, not a warning.  A warning is for something the author
    might have meant; nobody writes 1.2 and is content with 1.
    """

    rule_id = "INTEGRAL_VALUE"
    description = "Integer parameters must have whole-number limits and resolution."

    #: field on the parameter -> what the editor calls it
    FIELDS = (("minimum", "Minimum"),
              ("maximum", "Maximum"),
              ("default_value", "Default value"),
              ("resolution", "Resolution"))

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            value_type = parameter.value_type
            if value_type is None or value_type.is_float or value_type.is_bool:
                continue

            for attribute, label in self.FIELDS:
                value = getattr(parameter, attribute, None)
                if value is None or isinstance(value, bool):
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue          # a non-number is somebody else's rule
                if number.is_integer():
                    continue

                diagnostics.error(
                    "RNG017",
                    f"'{label}' is {value}, which is not a whole number, and "
                    f"'{value_type.c_name}' cannot hold it: the generated code "
                    f"would use {int(number)} instead.",
                    parameter.source,
                    hint=f"Write a whole number, or change the value type to "
                         f"float32_t / float64_t.")


class RequiredValuesRule(ValidationRule):
    """Non-boolean parameters need a default value and a resolution."""

    rule_id = "RANGE_REQUIRED"
    description = "Default value and resolution must be present for non-boolean parameters."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in enabled_leaves(model):
            value_type = parameter.value_type
            if value_type is None:
                continue
            if value_type.is_bool:
                self._check_boolean(parameter, value_type, diagnostics)
                continue

            if parameter.default_value is None:
                diagnostics.warning(
                    "RNG011", "No default value; 0 is used instead.", parameter.source)

            # Both limits empty or zero is a deliberate "no range" - the full
            # range of the type is used and there is nothing to warn about.
            # Only *one* of them filled in is the ambiguous case.
            if not parameter.range_disabled:
                if parameter.minimum is None:
                    diagnostics.warning(
                        "RNG012",
                        f"'Maximum' is {parameter.maximum} but 'Minimum' is empty; "
                        f"0 is used as the minimum.", parameter.source,
                        hint="Leave both cells empty to allow the whole range of the type.")
                if parameter.maximum is None:
                    diagnostics.warning(
                        "RNG013",
                        f"'Minimum' is {parameter.minimum} but 'Maximum' is empty; "
                        f"0 is used as the maximum.", parameter.source,
                        hint="Leave both cells empty to allow the whole range of the type.")

            if parameter.resolution is None:
                # The fallback depends on the type: 1 quantises a float to whole
                # numbers, which is almost never what the user meant.
                diagnostics.warning(
                    "RNG014",
                    f"No resolution; {value_type.default_resolution:g} is used instead "
                    f"(the default for '{value_type.c_name}').", parameter.source,
                    hint="Write the step you actually want in the 'Resolution' cell.")
            elif float(parameter.resolution) <= 0.0:
                diagnostics.warning(
                    "RNG015",
                    f"Resolution {parameter.resolution} is not positive.", parameter.source)
            elif not parameter.range_disabled:
                # A step bigger than the whole range leaves a single usable
                # value, which is nearly always a mix-up between two columns.
                minimum = parameter.effective_minimum
                maximum = parameter.effective_maximum
                if minimum is not None and maximum is not None:
                    span = float(maximum) - float(minimum)
                    if float(parameter.resolution) > span > 0.0:
                        diagnostics.warning(
                            "RNG016",
                            f"Resolution {parameter.resolution} is larger than the whole "
                            f"range [{minimum}, {maximum}] (span {span:g}); only one value "
                            f"would ever be reachable.", parameter.source,
                            hint="Check that 'Resolution' and the limits are in the "
                                 "right columns.")

    #: Values that are harmless to write in a boolean row: they say exactly
    #: what bool_t already is, so they are accepted without a word.
    BOOLEAN_HARMLESS = {"Minimum": (0,), "Maximum": (1,), "Resolution": (1,)}

    def _check_boolean(self, parameter, value_type, diagnostics: DiagnosticCollector) -> None:
        """One warning for a boolean row, and only when it says something odd.

        ``bool_t`` has no minimum, maximum or resolution.  Writing 0 / 1 / 1
        there is simply restating what a boolean is, so it is accepted in
        silence; anything else is reported once, listing every cell at fault -
        not once per cell.
        """
        odd = []
        for label, value in (("Minimum", parameter.minimum),
                             ("Maximum", parameter.maximum),
                             ("Resolution", parameter.resolution)):
            if value is None:
                continue
            if float(value) in [float(allowed) for allowed in self.BOOLEAN_HARMLESS[label]]:
                continue
            odd.append(f"{label} = {value}")

        if odd:
            diagnostics.warning(
                "RNG010",
                f"{', '.join(odd)}: ignored, because '{value_type.c_name}' has no "
                f"minimum, maximum or resolution.",
                parameter.source,
                hint="Leave these cells empty for a boolean, or write 0 / 1 / 1.")


class MetadataRule(ValidationRule):
    """The optional documentation columns: unit, and nothing else.

    A description is never required and never warned about, written or not,
    on any value - loggable or not.  It is free text for whoever reads the
    list, not something the tool depends on: the log names a loggable value by
    its User Name instead (see 'USER_NAME' in tag_rules.py), so a missing
    description does not leave a value unnamed anywhere.
    """

    rule_id = "META"
    description = "Documentation-column completeness: unit, configurably."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        require_unit = self.config.validation.require_unit
        for parameter in enabled_leaves(model):
            if require_unit and not parameter.unit:
                value_type = parameter.value_type
                if value_type is not None and not value_type.is_bool:
                    diagnostics.error(
                        "META002", "The 'Unit' cell is empty.", parameter.source,
                        hint="The unit is passed to the smart-data constructor and is "
                             "shown next to the value. Turn the requirement off with "
                             "'require_unit' in pl_project.json.")
