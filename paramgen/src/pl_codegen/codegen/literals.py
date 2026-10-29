"""Formatting of C literals.

Getting these right is what keeps the generated code warning-free, so all of it
lives in one place.
"""

from __future__ import annotations

import math
import struct
from typing import Optional

from ..model.parameter import NumericValue, Parameter
from ..model.types import CValueType

#: Significant digits that round-trip a value of each floating point type.
#: 9 for binary32 and 17 for binary64 are the standard "shortest exact" counts.
FLOAT32_DIGITS = 9
FLOAT64_DIGITS = 17


def escape_string(text: Optional[str]) -> str:
    """Return a C string literal for *text* (``NULL`` when it is empty)."""
    if text is None:
        return "NULL"
    escaped = (text.replace("\\", "\\\\")
                   .replace('"', '\\"')
                   .replace("\r", "\\r")
                   .replace("\n", "\\n")
                   .replace("\t", "\\t")
                   # '??' starts a trigraph in C99: "??/" would become a
                   # backslash and swallow the next character.  Escaping every
                   # '?' costs nothing and makes any description safe.
                   .replace("?", "\\?"))
    return f'"{escaped}"'


def safe_comment(text: Optional[str]) -> str:
    """Make *text* safe to paste inside a ``/* ... */`` comment.

    A description is ordinary prose written by a person, and prose contains
    things like ``0..100 /* see spec */``.  Left alone, that closes the comment
    early and the generated file stops compiling, so the two sequences that
    delimit a comment are broken up here.  Newlines would end a ``//`` comment
    and split a ``/*`` one across lines, so they collapse to spaces.
    """
    if not text:
        return ""
    cleaned = str(text).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return cleaned.replace("*/", "* /").replace("/*", "/ *")


def bool_literal(value: object) -> str:
    return "TRUE" if bool(value) else "FALSE"


def unsigned_literal(value: int) -> str:
    return f"{int(value)}U"


def define_number_literal(number: int, suffix: str = "U") -> str:
    """A system name's or a parameter mode's number, as its ``#define`` says it.

    ``(16U)``, and a negative one as a plain int, ``(-5)``: the firmware's
    ``tag == SYS_TEST`` turns it into the tag's uint32_t, so the two still
    match.  The smallest int32_t is ``(-2147483647 - 1)``: ``2147483648`` alone
    is no int, and a long ``-2147483648`` would not match the tag on a 64-bit
    build.  *suffix* is what a number that is not negative ends in.
    """
    if number >= 0:
        return f"({number}{suffix})"
    if number == -0x80000000:
        return "(-2147483647 - 1)"
    return f"({number})"


def float_literal(value: float, value_type: CValueType) -> str:
    """Format a floating point literal for ``float32_t`` / ``float64_t``.

    The digit count is *significant digits*, formatted with ``%g``.  Rounding to
    a number of decimal places instead - ``round(value, 9)`` - destroys small
    magnitudes: 1.602176634e-19 becomes 0.0 and 2.5e-9 becomes 3.0e-9, silently,
    with no diagnostic anywhere.  A resolution or a limit written in scientific
    notation is completely ordinary in this project, so that has to be right.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"'{value}' cannot be written as a C floating point literal.")

    text = _shortest_exact(float(value), value_type)

    if "e" in text or "E" in text:
        mantissa, _, exponent = text.replace("E", "e").partition("e")
        if "." not in mantissa:
            mantissa += ".0"
        text = f"{mantissa}e{exponent}"
    elif "." not in text:
        text += ".0"
    return text + value_type.literal_suffix


def _as_float32(value: float) -> float:
    """*value* rounded to the nearest ``float`` a C ``float32_t`` can hold."""
    return struct.unpack("f", struct.pack("f", value))[0]


def _shortest_exact(value: float, value_type: CValueType) -> str:
    """The shortest decimal text that reads back as exactly *value*.

    Writing the maximum number of digits is always correct but hard to read:
    ``1e-7`` would come out as ``9.9999999999999995e-08``.  So the smallest
    digit count that still round-trips is used, which gives back the number the
    user actually typed whenever that number is representable.
    """
    is_float32 = value_type.suffix == "F32"
    limit = FLOAT32_DIGITS if is_float32 else FLOAT64_DIGITS
    target = _as_float32(value) if is_float32 else value

    def reads_back_exactly(text: str) -> bool:
        parsed = float(text)
        return (_as_float32(parsed) if is_float32 else parsed) == target

    # repr() is Python's own shortest round-tripping form and usually gives
    # back exactly what the user typed ("10.0", "0.1", "1e-07").
    candidates = [repr(value)] + [f"{value:.{digits}g}" for digits in range(1, limit + 1)]
    exact = [text for text in candidates if reads_back_exactly(text)]
    if not exact:
        return f"{value:.{limit}g}"

    # shortest wins; between equals, the one without an exponent reads better
    return min(exact, key=lambda text: (len(text), "e" in text.lower()))


def integer_literal(value: int, value_type: CValueType) -> str:
    """Format an integer literal, keeping the sign outside the suffix.

    The most negative value of a signed type needs care.  ``-9223372036854775808LL``
    is not one literal but a unary minus applied to ``9223372036854775808LL``,
    which does not fit into ``long long`` - so a pedantic compiler warns or
    refuses it.  The portable spelling is ``(-9223372036854775807LL - 1)``, and
    that is what is emitted for any type's most negative value.
    """
    number = int(value)
    if number < 0:
        if value_type.native_min is not None and number == int(value_type.native_min):
            return f"({number + 1}{value_type.literal_suffix} - 1)"
        return f"({number}{value_type.literal_suffix})"
    return f"{number}{value_type.literal_suffix}"


def numeric_literal(value: NumericValue, value_type: CValueType,
                    fallback: NumericValue = 0) -> str:
    """Render *value* as a literal of *value_type*, using *fallback* when empty."""
    effective = fallback if value is None else value
    if value_type.is_bool:
        return bool_literal(effective)
    if value_type.is_float:
        return float_literal(float(effective), value_type)
    return integer_literal(int(effective), value_type)


def constructor_arguments(parameter: Parameter, value_type: CValueType,
                          with_unit: bool = True) -> str:
    """Arguments of ``fSmartData_XX_Ctor`` for *parameter* (without ``me``).

    ``Minimum`` and ``Maximum`` both zero (or both empty) means "no range", and
    the constructor has no way of expressing that - it always compares the
    default value against the two limits it is given.  So "no range" is emitted
    as the full range of the C type, written with the **standard macros**
    (``INT32_MIN``, ``UINT16_MAX``, ``-DBL_MAX`` ...) rather than with the
    numbers spelled out.  The generated line then says what it means, and it
    stays right on any conforming compiler instead of depending on the numbers
    this tool happened to compute.

    An empty ``Resolution`` falls back to the type's own default: 1 for an
    integer, but a small fraction for a float, where 1 would quietly quantise
    every value to whole numbers.

    The unit is the last argument, because it is part of what the object *is*
    rather than something assigned to it afterwards - and it is a real string
    in the firmware, so ``with_unit=False`` (``codegen.emit_unit``) leaves it
    empty.  The setting used to reach only the *comments*, which meant somebody
    who switched it off to keep unit strings out of a small flash still got
    every one of them.

    ``bool_t`` is the exception on every count: it has no range, no resolution
    and no unit, so ``fSmartData_B8_Ctor`` takes the default value and nothing
    else.  Its object has no ``pUnit`` field to put one in.
    """
    if value_type.is_bool:
        return numeric_literal(parameter.default_value, value_type, fallback=False)

    unit = escape_string((parameter.unit or "") if with_unit else "")

    if parameter.range_disabled and value_type.has_limit_macros:
        minimum, maximum = value_type.limit_min_macro, value_type.limit_max_macro
    else:
        minimum = numeric_literal(parameter.effective_minimum, value_type, fallback=0)
        maximum = numeric_literal(parameter.effective_maximum, value_type, fallback=0)

    default = numeric_literal(parameter.default_value, value_type, fallback=0)
    resolution = numeric_literal(parameter.resolution, value_type,
                                 fallback=value_type.default_resolution)
    return f"{minimum}, {maximum}, {default}, {resolution}, {unit}"


def limit_headers(parameters) -> list:
    """Standard headers needed by the limit macros of *parameters*.

    Only the headers actually used are returned, so a project with no float
    parameter does not get ``<float.h>`` it never needs.
    """
    headers = []
    for parameter in parameters:
        value_type = parameter.value_type
        if value_type is None or not parameter.range_disabled:
            continue
        if value_type.has_limit_macros and value_type.limit_header not in headers:
            headers.append(value_type.limit_header)
    return headers


def tag_value_literal(value: object) -> str:
    """Render a tag value for the ``uint32_t Value`` field of the descriptor."""
    if value is None:
        return "0U"
    if isinstance(value, bool):
        return f"(uint32_t){bool_literal(value)}"
    if isinstance(value, int):
        return unsigned_literal(value)
    text = str(value).strip()
    if not text:
        return "0U"
    return f"(uint32_t){text}"
