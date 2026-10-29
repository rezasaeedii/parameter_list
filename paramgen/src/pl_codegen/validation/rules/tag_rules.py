"""Rules about tags.

Tags themselves are interpreted by the application layer, not by the code
generator.  The generator only checks that the *values and the drop-down
lists* are consistent, so that the generated C file always compiles.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ...codegen.files import fixed_tags
from ...config import FORMAT_PARAM_TABLE
from ...errors import DiagnosticCollector
from ...model.parameter import Parameter
from ...model.parameter_list import ParameterList
from ...model.tags import LOGGABLE_TAG, TAG_REGISTRY, TAGS_BY_ID, TagKind
from ...naming import is_valid_c_identifier, strip_array_indices
from .rule_base import ValidationRule, declared_values

#: Maximum value that fits into a ``TagXxx`` field of ``sParameterDescriptor``
#: (a uint32_t).
TAG_VALUE_MAX = 0xFFFFFFFF

def _how_to_fill(missing, model: ParameterList) -> str:
    """What to write into the empty mandatory tags of one parameter.

    Grouped by what the cell accepts, because that is how the answer is
    shaped: the three boolean tags all take the same two words, and repeating
    "set it to TRUE or FALSE" three times is not three pieces of advice.
    """
    parts = []
    booleans = [spec.label for spec in missing if spec.kind is TagKind.BOOLEAN]
    if booleans:
        parts.append(f"{_listed(booleans)} take TRUE or FALSE")
    for spec in missing:
        if spec.kind is TagKind.BOOLEAN:
            continue
        allowed = model.defines.get(spec.defines_column) if spec.defines_column else None
        if allowed:
            parts.append(f"'{spec.label}' takes one of {', '.join(allowed)}")
        else:
            parts.append(f"'{spec.label}' must be filled in")
    return "; ".join(parts) + "."


def _listed(labels) -> str:
    """``['a', 'b', 'c']`` -> ``'a', 'b' and 'c'``."""
    quoted = [f"'{label}'" for label in labels]
    if len(quoted) == 1:
        return quoted[0]
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"


#: Maximum value that fits into ``sParameterDescriptor.LogId`` (uint16_t).
#: The log id is not a tag and its field is half as wide, so it has a limit of
#: its own.  Every element of an array gets its own id, so a block that starts
#: near the top can still run past it.
LOG_ID_MAX = 0xFFFF


class MandatoryTagRule(ValidationRule):
    """Mandatory tags must carry a value for every enabled parameter.

    One message per parameter, listing every tag it is missing - not one per
    tag.  A parameter that was just added has all five of them empty, and five
    rows saying the same thing about the same parameter is five times the
    noise for the same single fix: open it and fill the tags in.
    """

    rule_id = "TAG_MANDATORY"
    description = "Mandatory tags must be filled in for every enabled parameter."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in declared_values(model):
            missing = [spec for spec in TAG_REGISTRY
                       if spec.mandatory and parameter.tags.get(spec.tag_id) is None]
            if not missing:
                continue

            labels = ", ".join(f"'{spec.label}'" for spec in missing)
            verb = "is" if len(missing) == 1 else "are"
            diagnostics.error(
                "TAG001",
                f"Mandatory tag{'' if len(missing) == 1 else 's'} {labels} {verb} empty.",
                parameter.source,
                hint=_how_to_fill(missing, model))


class TagEnumValueRule(ValidationRule):
    """Enum tags must use a value from the matching drop-down list."""

    rule_id = "TAG_ENUM"
    description = "Enum tag values must come from the matching drop-down list."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        fixed = fixed_tags(self.config)
        for spec in TAG_REGISTRY:
            if spec.kind is not TagKind.ENUM or not spec.defines_column:
                continue
            allowed = model.defines.get(spec.defines_column)
            # A value the FORMAT writes into every parameter is one missing
            # entry in the drop-down list, not one mistake per parameter: it is
            # said once, on the first, with where to add it.
            forced = fixed.get(spec.tag_id)
            forced_reported = False
            for parameter in declared_values(model):
                value = parameter.tags.get(spec.tag_id)
                if value is None:
                    continue
                text = str(value)
                if not is_valid_c_identifier(text):
                    diagnostics.error(
                        "TAG002",
                        f"Tag '{spec.tag_id}' value '{text}' is not a valid C identifier.",
                        parameter.source,
                        hint=f"The value is written into the generated code as it "
                             f"stands, so pick one of the names in the "
                             f"'{spec.defines_column}' list.")
                elif allowed and text not in allowed and text == forced:
                    if forced_reported:
                        continue
                    forced_reported = True
                    diagnostics.error(
                        "TAG003",
                        f"Tag '{spec.tag_id}' value '{text}' is not listed in the "
                        f"'{spec.defines_column}' list.",
                        parameter.source,
                        hint=f"This project generates smart data, which writes "
                             f"{text} into the '{spec.label}' of every parameter, so "
                             f"the list has to have it: add {text} to 'Parameter "
                             f"modes' (⚙ › Drop-down lists…). Allowed now: "
                             f"{', '.join(allowed)}.")
                elif allowed and text not in allowed:
                    diagnostics.error(
                        "TAG003",
                        f"Tag '{spec.tag_id}' value '{text}' is not listed in the "
                        f"'{spec.defines_column}' list.",
                        parameter.source,
                        hint=f"Allowed values: {', '.join(allowed)}.")


class TagValueRangeRule(ValidationRule):
    """Numeric tag values must fit into ``uint32_t``."""

    rule_id = "TAG_RANGE"
    description = "Numeric tag values must fit into the uint32_t descriptor field."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for parameter in declared_values(model):
            for tag_id, value in parameter.tags.items():
                if not isinstance(value, int) or isinstance(value, bool):
                    continue
                if value < 0 or value > TAG_VALUE_MAX:
                    spec = TAGS_BY_ID.get(tag_id)
                    shown = spec.label if spec else tag_id
                    diagnostics.error(
                        "TAG004",
                        f"Tag '{tag_id}' ('{shown}') value {value} does not fit into "
                        f"uint32_t (0 .. {TAG_VALUE_MAX}).", parameter.source,
                        hint=f"Every tag is one uint32_t in the descriptor; write a "
                             f"value between 0 and {TAG_VALUE_MAX}.")


class FreeTagSyntaxRule(ValidationRule):
    """Free tags must be either a number or a C identifier."""

    rule_id = "TAG_FREE"
    description = "Free tags (Tag1..Tag4) must hold a number or a C identifier."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        for spec in TAG_REGISTRY:
            if spec.kind is not TagKind.FREE:
                continue
            for parameter in declared_values(model):
                value = parameter.tags.get(spec.tag_id)
                if value is None or isinstance(value, (int, bool)):
                    continue
                if not is_valid_c_identifier(str(value)):
                    diagnostics.error(
                        "TAG005",
                        f"Tag '{spec.tag_id}' value '{value}' is neither a number nor a "
                        f"valid C identifier.", parameter.source,
                        hint="A free tag is copied into the generated code unchanged, "
                             "so it has to be a number or the name of a constant.")


class UserNameRule(ValidationRule):
    """A loggable parameter must carry a user name.

    The user name is the label a person reads - in the ground station, in an
    agreement document, and, for a loggable value, as the name the log itself
    uses: there is no separate "log name" field, so an empty user name here
    leaves that value unnamed in the log.  A parameter that is never logged is
    free to leave it empty - nothing downstream needs it - so the check does
    not apply.  A parameter table logs nothing at all ('Tag Loggable' is one of
    the tags that format ignores), so it is exempt in full.
    """

    rule_id = "USER_NAME"
    description = "A loggable parameter must have a 'User Name': the log names it by that."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        if self.config.output.format == FORMAT_PARAM_TABLE:
            return
        # Judged per VALUE, because a value's name is its own: an element of
        # an array or a field of a structure may carry one of its own, and
        # reads the nearest row above it that has one - Wheels[1].Samples,
        # Wheels[1], Wheels - only when it has none.
        # Reported once per declaration all the same: one empty cell is one
        # mistake, however many values read it.
        unnamed: Dict[Tuple[object, str], List[Parameter]] = {}
        for value in model.flatten():
            if value.has_active_tag(LOGGABLE_TAG) and not (value.user_name or "").strip():
                key = (value.source.file, strip_array_indices(value.name))
                unnamed.setdefault(key, []).append(value)

        for (_file, declaration), values in unnamed.items():
            some = (f" {len(values)} of its values have none - the first is "
                    f"'{values[0].name}'." if values[0].name != declaration else "")
            diagnostics.error(
                "TAG011",
                f"'{declaration}' has no User Name. '{declaration}' is loggable, and "
                f"the log names a value by its User Name, so the cell has to be "
                f"filled in.{some}",
                values[0].source,
                hint="Write a User Name on the parameter - every value of it, and every "
                     "field of a structure, takes it - or one on each value. It is also "
                     "the value's name in the log. Or, if it is not meant to be logged, "
                     "set 'Tag Loggable' to FALSE.")


class LogIdRule(ValidationRule):
    """Loggable values need a log id, and no two of them may share one.

    A log id numbers a *value*.  Every element of an array declaration is its
    own value with its own row in the table, so a ``float64_t[10]`` written as
    log id 410 hands 410..419 to its ten elements one at a time, and the next
    parameter may not start before 420.  The type plays no part: a
    ``uint8_t[10]`` does exactly the same.

    Note that this is deliberately **not** the rule used for ``MemoryOffset``:
    an offset is a byte address and grows by ``sizeof(value) * array size``,
    while a log id numbers a value and does not depend on the type at all.
    That is also why the log id is not a tag: it owns no offset area, and it is
    a ``uint16_t`` field of its own in the descriptor rather than one of the
    ``TagXxx`` fields.

    **Only a loggable parameter has a log id at all.**  A number left on a
    parameter whose 'Tag Loggable' is FALSE means nothing: it reserves no
    range, it cannot clash with anything, and the generated table stores 0 for
    it.  Otherwise a stale number in an unused row would block an id that is in
    fact free.
    """

    rule_id = "TAG_LOG_ID"
    description = "A loggable value needs a log id, and no two values may share one."

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        claimed: Dict[int, object] = {}   # log id -> the value that took it

        for parameter in model.flatten():
            loggable = parameter.has_active_tag(LOGGABLE_TAG)
            log_id = parameter.log_id

            if not loggable:
                if log_id is not None:
                    diagnostics.info(
                        "TAG014",
                        f"The log id is {log_id} but 'Tag Loggable' is FALSE; the id is "
                        f"ignored and 0 is written into the table.",
                        parameter.source,
                        hint="Another parameter may use this id freely.")
                continue

            if log_id is None:
                diagnostics.error(
                    "TAG010", "The parameter is loggable but has no log id.",
                    parameter.source,
                    hint="A loggable parameter needs a log id so that the log file can be "
                         "decoded. Use 'Use next free id' in the editor to get one.")

            if not isinstance(log_id, int) or isinstance(log_id, bool):
                continue

            # The descriptor stores the id in a uint16_t.  Every element of an
            # array is its own value with its own id, so the numbers that have
            # to fit are the ones already handed out - checking them one at a
            # time catches the element that ran off the end, and names it.
            if log_id < 0 or log_id > LOG_ID_MAX:
                diagnostics.error(
                    "TAG015",
                    f"Log id {log_id} of '{parameter.name}' does not fit into the "
                    f"uint16_t 'LogId' field (0..{LOG_ID_MAX}).",
                    parameter.source,
                    hint="An array reserves one id per element, so a block that starts "
                         "close to the top of the range can run past it.")
                continue

            # One value, one id: two values either share an id or they do not.
            # There is deliberately no "these two ranges overlap" case any more
            # - a range belonged to the old table, where one row could stand
            # for a whole array.
            other = claimed.get(log_id)
            if other is not None:
                # Naming the other file only when it *is* another file: a
                # project is often several lists merged, and "also in
                # power.xml" is the whole answer there - while repeating the
                # open file's own path says nothing.
                elsewhere = ""
                if other.source.file and other.source.file != parameter.source.file:
                    elsewhere = f" '{other.name}' comes from {other.source.file}."
                diagnostics.error(
                    "TAG012",
                    f"Log id {log_id} is already used by '{other.name}'.",
                    parameter.source,
                    hint=f"Every value needs an id of its own, so change one of the "
                         f"two. 'Use next free id' in the editor gives a free "
                         f"one.{elsewhere}")
            else:
                claimed[log_id] = parameter
