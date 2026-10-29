"""Rules that turn parameter names into C identifiers.

Keeping every naming decision in one module means that a change of naming
convention is a one-file change.
"""

from __future__ import annotations

import re

# ``TestVarU16`` -> ``TEST_VAR_U16``  /  ``PosDrone`` -> ``POS_DRONE``
_BOUNDARY_LOWER_UPPER = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_BOUNDARY_ACRONYM = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")

_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Keywords that must never be used as a parameter name (C99 + C++ subset that
#: matters for the generated headers).
C_RESERVED_KEYWORDS = frozenset({
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else",
    "enum", "extern", "float", "for", "goto", "if", "inline", "int", "long", "register",
    "restrict", "return", "short", "signed", "sizeof", "static", "struct", "switch", "typedef",
    "union", "unsigned", "void", "volatile", "while", "_Bool", "_Complex", "_Imaginary",
    "_Alignas", "_Alignof", "_Atomic", "_Generic", "_Noreturn", "_Static_assert", "_Thread_local",
    # C++ keywords -- the generated headers must be includable from C++
    "asm", "bool", "catch", "class", "const_cast", "delete", "dynamic_cast", "explicit",
    "export", "false", "friend", "mutable", "namespace", "new", "operator", "private",
    "protected", "public", "reinterpret_cast", "static_cast", "template", "this", "throw",
    "true", "try", "typeid", "typename", "using", "virtual", "wchar_t", "nullptr",
    "constexpr", "decltype", "noexcept", "alignas", "alignof", "char16_t", "char32_t",
    "static_assert", "thread_local",
})


def is_valid_c_identifier(name: str) -> bool:
    """Return ``True`` when *name* can be used as a C identifier."""
    return bool(name) and _C_IDENTIFIER.match(name) is not None


def is_reserved_keyword(name: str) -> bool:
    """Return ``True`` when *name* collides with a C/C++ keyword."""
    return name in C_RESERVED_KEYWORDS


def to_macro_case(name: str) -> str:
    """Convert a CamelCase / dotted name into ``UPPER_SNAKE_CASE``.

    ``TestVarU16`` -> ``TEST_VAR_U16``, ``PosDrone`` -> ``POS_DRONE``,
    ``Position.Home.Lat`` -> ``POSITION_HOME_LAT``, and
    ``Wheels[2].Speed`` -> ``WHEELS_2_SPEED``.
    """
    # 'Wheels[2].Speed' -> 'WHEELS_2_SPEED': an array element of a structure is
    # written the way C writes it, and the macro keeps the index as a word.
    text = (name.strip().replace("-", "_").replace(" ", "_").replace(".", "_")
                .replace("[", "_").replace("]", ""))
    text = _BOUNDARY_ACRONYM.sub("_", text)
    text = _BOUNDARY_LOWER_UPPER.sub("_", text)
    text = re.sub(r"_+", "_", text)
    return text.upper().strip("_")


def index_macro(name: str, prefix: str = "") -> str:
    """Name of the ``#define`` that holds the index of a parameter."""
    return f"{prefix}{to_macro_case(name)}"


_ARRAY_INDEX = re.compile(r"\[\d+\]")


def strip_array_indices(name: str) -> str:
    """``Wheels[2].Samples`` -> ``Wheels.Samples``.

    The elements of a struct array are separate *values* - each has its own
    index, its own offsets and its own log id - but they are not separate
    *declarations*: ``Samples`` is written once, inside the structure type that
    every element shares.  Anything that describes the declaration rather than
    the value therefore drops the element index, so that all three elements name
    the one macro the typedef was written with.
    """
    return _ARRAY_INDEX.sub("", name)


def array_size_macro(name: str, prefix: str = "") -> str:
    """Name of the ``#define`` that holds the array size of a parameter.

    The array size belongs to the declaration, so ``Wheels[0].Samples`` and
    ``Wheels[1].Samples`` share ``WHEELS_SAMPLES_ARRAY_SIZE``.
    """
    return f"{prefix}{to_macro_case(strip_array_indices(name))}_ARRAY_SIZE"


def smart_data_symbol(name: str, prefix: str = "Cg_SmartData_") -> str:
    """Name of the generated smart-data object of a top level parameter."""
    return f"{prefix}{name}"


def struct_type_name(dotted_name: str, prefix: str = "sCgStruct_") -> str:
    """C type name of a generated structure, e.g. ``sCgStruct_Position_Home``."""
    return prefix + dotted_name.replace(".", "_")


def offset_total_macro(tag_id: str, prefix: str = "") -> str:
    """Name of the ``#define`` holding the total bytes used by a tag.

    ``PARAMETER_LIST_TAG_SYSTEM_NAME_SIZE``.  Its prefix is still the setting
    called ``codegen.offset_define_prefix``: it named the per-parameter
    offset macros too, before those moved to the Table file, and renaming
    the key would break every project file that sets it.
    """
    return f"{prefix}TAG_{to_macro_case(tag_id)}_SIZE"


def tag_size_function(tag_id: str, prefix: str = "fParameterList_Get") -> str:
    """Name of the generated getter for a tag's total size.

    ``"ResetProof"`` -> ``fParameterList_GetResetProofSize``.  The tag id is
    already CamelCase, so it is used as it is - the result reads like the rest
    of the hand written API rather than like a macro.
    """
    return f"{prefix}{tag_id}Size"


def include_guard(file_name: str) -> str:
    """Include guard derived from a file name, matching the company snippet."""
    stem = file_name.rsplit(".", 1)[0]
    return f"{stem.upper()}_H"
