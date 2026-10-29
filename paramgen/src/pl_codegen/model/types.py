"""Registry of the C data types supported by the parameter list.

Adding a new supported data type is a one-entry change in :data:`VALUE_TYPES`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class CValueType:
    """Everything the generator needs to know about one supported C type."""

    c_name: str            #: name as the user picks it, e.g. ``uint8_t``
    suffix: str            #: smart-data suffix, e.g. ``U8``
    kind: str              #: ``"bool"`` | ``"int"`` | ``"float"``
    signed: bool
    bits: int
    literal_suffix: str    #: appended to numeric literals in generated C code
    native_min: Optional[float]
    native_max: Optional[float]
    #: Names of the standard macros that spell the two limits in C.  A parameter
    #: with no range of its own is generated with these rather than with the
    #: numbers written out, so the code says *why* the limit is what it is and
    #: stays correct on any conforming compiler.
    limit_min_macro: Optional[str] = None
    limit_max_macro: Optional[str] = None
    #: Header that declares those macros.
    limit_header: Optional[str] = None
    #: Step used when the user leaves 'Resolution' empty.  1 is right for an
    #: integer and meaningless for a float, where it would quantise the value to
    #: whole numbers.
    default_resolution: float = 1

    @property
    def smart_data_struct(self) -> str:
        return f"sSmartData{self.suffix}"

    @property
    def constructor(self) -> str:
        return f"fSmartData_{self.suffix}_Ctor"

    @property
    def enum_name(self) -> str:
        return f"eSMART_DATA_TYPE_{self.suffix}"

    @property
    def value_size(self) -> int:
        """Size in bytes of the *value* of this type.

        This is what the tag offsets advance by: a ``uint16_t``
        parameter occupies 2 bytes, a ``uint64_t`` one occupies 8.  The sizes
        are fixed by the C standard, so the generated offsets are the same on
        every compiler.
        """
        return 1 if self.kind == "bool" else self.bits // 8

    @property
    def has_range(self) -> bool:
        """``bool_t`` smart data has no min/max/resolution."""
        return self.kind != "bool"

    @property
    def is_float(self) -> bool:
        return self.kind == "float"

    @property
    def is_bool(self) -> bool:
        return self.kind == "bool"

    @property
    def has_limit_macros(self) -> bool:
        return bool(self.limit_min_macro and self.limit_max_macro)


def _int(c_name: str, suffix: str, bits: int, signed: bool, literal_suffix: str) -> CValueType:
    """One fixed-width integer type, with the <stdint.h> macros for its limits.

    ``uint16_t`` -> UINT16_MAX / 0, ``int16_t`` -> INT16_MIN / INT16_MAX.  These
    are exactly the names <stdint.h> guarantees, so the generated code needs no
    magic numbers for "the whole range of this type".
    """
    stem = c_name.replace("_t", "").upper()          # uint16_t -> UINT16
    if signed:
        native_min, native_max = -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
        minimum_macro = f"{stem}_MIN"
    else:
        native_min, native_max = 0, 2 ** bits - 1
        minimum_macro = f"0{literal_suffix}"          # <stdint.h> has no UINTn_MIN
    return CValueType(c_name, suffix, "int", signed, bits, literal_suffix,
                     native_min, native_max,
                     limit_min_macro=minimum_macro, limit_max_macro=f"{stem}_MAX",
                     limit_header="stdint.h", default_resolution=1)


#: Every data type the generator can emit.  Structs and enums are intentionally
#: **not** supported and are rejected by the validator.
VALUE_TYPES: Dict[str, CValueType] = {
    "bool_t": CValueType("bool_t", "B8", "bool", False, 8, "", None, None),
    "uint8_t": _int("uint8_t", "U8", 8, False, "U"),
    "int8_t": _int("int8_t", "I8", 8, True, ""),
    "uint16_t": _int("uint16_t", "U16", 16, False, "U"),
    "int16_t": _int("int16_t", "I16", 16, True, ""),
    "uint32_t": _int("uint32_t", "U32", 32, False, "UL"),
    "int32_t": _int("int32_t", "I32", 32, True, "L"),
    "uint64_t": _int("uint64_t", "U64", 64, False, "ULL"),
    "int64_t": _int("int64_t", "I64", 64, True, "LL"),
    # For a float, "the whole range" is -FLT_MAX .. FLT_MAX: FLT_MIN is the
    # smallest *positive* normal value, not the lowest one, and using it here
    # would be a classic and silent mistake.
    "float32_t": CValueType("float32_t", "F32", "float", True, 32, "f",
                           -3.4028235e38, 3.4028235e38,
                           limit_min_macro="-FLT_MAX", limit_max_macro="FLT_MAX",
                           limit_header="float.h", default_resolution=0.001),
    "float64_t": CValueType("float64_t", "F64", "float", True, 64, "",
                           -1.7976931348623157e308, 1.7976931348623157e308,
                           limit_min_macro="-DBL_MAX", limit_max_macro="DBL_MAX",
                           limit_header="float.h", default_resolution=0.000001),
}

#: Spellings accepted as input that map onto a canonical type.
TYPE_ALIASES: Dict[str, str] = {
    "bool": "bool_t",
    "boolean": "bool_t",
    "b8": "bool_t",
    "float": "float32_t",
    "double": "float64_t",
    "float_t": "float32_t",
    "u8": "uint8_t", "i8": "int8_t", "s8": "int8_t",
    "u16": "uint16_t", "i16": "int16_t", "s16": "int16_t",
    "u32": "uint32_t", "i32": "int32_t", "s32": "int32_t",
    "u64": "uint64_t", "i64": "int64_t", "s64": "int64_t",
    "f32": "float32_t", "f64": "float64_t",
}


def resolve_value_type(name: Optional[str]) -> Optional[CValueType]:
    """Return the :class:`CValueType` for *name*, or ``None`` when unsupported."""
    if not name:
        return None
    key = str(name).strip()
    if key in VALUE_TYPES:
        return VALUE_TYPES[key]
    return VALUE_TYPES.get(TYPE_ALIASES.get(key.lower(), ""), None)


def supported_type_names() -> str:
    """Comma separated list of supported type names (used in error messages)."""
    return ", ".join(sorted(VALUE_TYPES))
