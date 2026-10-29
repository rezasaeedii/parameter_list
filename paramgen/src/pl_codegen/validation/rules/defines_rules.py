"""Rules about the drop-down lists ("Choices..." in the editor).

Those lists are not just a set of allowed words: two of them are written
straight into the generated header as C ``#define``s, each with a number.
Whatever is typed there ends up in the firmware, so it has to be a legal C
identifier - nothing else in the tool checks that - and two names of one list
must not share a number, or the firmware could not tell them apart.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ...config import FORMAT_PARAM_TABLE
from ...errors import DiagnosticCollector, SourceLocation
from ...model.defines import (COLUMN_SYSTEM_NAMES, DEFINE_NUMBER_MAX, DEFINE_NUMBER_MIN,
                              GENERATED_DEFINES, define_tag_value)
from ...model.parameter_list import ParameterList
from ...naming import is_reserved_keyword, is_valid_c_identifier
from .rule_base import ValidationRule


class DefinesSheetRule(ValidationRule):
    """Every value that becomes a define must be a usable C identifier.

    Without this, a *SYSTEM NAMES* entry written as ``GS / PC`` produces::

        #ifndef GS / PC
        #define GS / PC  (1U)      /* does not compile */
        #endif

    and the tool reports nothing at all.
    """

    rule_id = "DEFINES"
    description = ("Values that become C defines must be unique, valid identifiers "
                   "with numbers of their own.")

    def check(self, model: ParameterList, diagnostics: DiagnosticCollector) -> None:
        location = SourceLocation(file=", ".join(model.source_files) or None)

        #: define name -> the column it came from, across every list
        everywhere: Dict[str, str] = {}

        for column in GENERATED_DEFINES:
            values: List[str] = model.defines.get(column)

            if not values:
                diagnostics.error(
                    "DEF001",
                    f"The '{column}' list is empty, so none of its defines can be "
                    f"generated.",
                    location,
                    hint=f"Every value a tag uses has to be listed under '{column}' "
                         f"(⚙ › Drop-down lists…), or the generated code will not "
                         f"compile.")
                continue

            for value in values:
                text = str(value).strip()

                if not is_valid_c_identifier(text):
                    diagnostics.error(
                        "DEF002",
                        f"'{text}' in the '{column}' column is not a valid C identifier, "
                        f"and it becomes a #define in the generated header.",
                        location,
                        hint="Use letters, digits and '_' only, and do not start with "
                             "a digit.")
                elif is_reserved_keyword(text):
                    diagnostics.error(
                        "DEF002",
                        f"'{text}' in the '{column}' column is a reserved C/C++ keyword.",
                        location,
                        hint="Every value of the list becomes a #define in the "
                             "generated header, so it has to be a name C can use. "
                             "Rename it.")

                # a value repeated inside one column cannot reach here: the
                # reader keeps the first occurrence only
                other = everywhere.get(text)
                if other is not None and other != column:
                    diagnostics.error(
                        "DEF004",
                        f"'{text}' is listed both under '{other}' and under '{column}'; "
                        f"the two defines would collide.", location,
                        hint=f"Both lists become defines in the same header, so a "
                             f"name can belong to only one of them: remove it from "
                             f"'{other}' or from '{column}'.")
                everywhere.setdefault(text, column)

            # A smart-data header writes both lists with their numbers; a
            # parameter table writes its modes numbered by their place in the
            # list, as it always has, and its system names - nsrSystemNames.h -
            # with their numbers.
            if (self.config.output.format != FORMAT_PARAM_TABLE
                    or column == COLUMN_SYSTEM_NAMES):
                self._check_numbers(model, column, location, diagnostics)

    @staticmethod
    def _check_numbers(model: ParameterList, column: str, location: SourceLocation,
                       diagnostics: DiagnosticCollector) -> None:
        """Every name of the list a number of its own, that fits the tag.

        Two numbers clash when the tag holds the same 32 bits for both: -1 and
        0xFFFFFFFF are one value to the firmware.
        """
        taken: Dict[int, Tuple[str, int]] = {}
        clashes: List[Tuple[str, int, str, int]] = []
        for name, number in model.defines.numbered(column):
            if number < DEFINE_NUMBER_MIN or number > DEFINE_NUMBER_MAX:
                diagnostics.error(
                    "DEF006",
                    f"{name} in the '{column}' list is {number}, which does not fit "
                    f"the 32-bit tag it is stored in ({DEFINE_NUMBER_MIN} to "
                    f"{DEFINE_NUMBER_MAX}).",
                    location,
                    hint=f"Give {name} a number from {DEFINE_NUMBER_MIN} to "
                         f"{DEFINE_NUMBER_MAX} in ⚙ › Drop-down lists… - a name without "
                         f"one takes the number after the line above it.")
                continue
            stored = define_tag_value(number)
            if stored in taken:
                clashes.append((*taken[stored], name, number))
            else:
                taken[stored] = (name, number)

        for first, first_number, second, number in clashes:
            same = (f"both {number}" if number == first_number else
                    f"{first_number} and {number}, which the 32-bit tag stores as the "
                    f"same value (0x{define_tag_value(number):08X})")
            diagnostics.error(
                "DEF005",
                f"{first} and {second} in the '{column}' list are {same}, so the "
                f"firmware cannot tell them apart.",
                location,
                hint=f"Give one of them another number in ⚙ › Drop-down lists… "
                     f"({second} = ...). A name without a number takes the one after "
                     f"the line above it, which is how two lines can end up the same.")
