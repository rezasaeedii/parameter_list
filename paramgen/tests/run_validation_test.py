"""Checks that a faulty parameter list is rejected with the right diagnostics.

Each case builds a small model in memory, runs the validator on it and asserts
which diagnostic code comes back.  No compiler needed.

Run it with::

    python tests/run_validation_test.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen.app_home import SNIPPET_FILE  # noqa: E402
from pl_codegen.codegen.files import apply_fixed_tags  # noqa: E402
from pl_codegen.config import Config  # noqa: E402
from pl_codegen.errors import DiagnosticCollector, Severity  # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,  # noqa: E402
                                            colour_supported, paint, setup_logging)
import pl_codegen.logging_utils as _logging_utils  # noqa: E402
from pl_codegen.model.defines import (COLUMN_TYPES, COLUMN_PARAM_MODES,  # noqa: E402
                                      COLUMN_SYSTEM_NAMES, COLUMN_VALUE_TYPES, Defines)
from pl_codegen.model.parameter import Parameter, ParameterKind  # noqa: E402
from pl_codegen.model.parameter_list import ParameterList, merge_lists
from pl_codegen.model.struct_migration import adopt_types
from pl_codegen.model.struct_sync import apply_types  # noqa: E402
from pl_codegen.model.types import VALUE_TYPES  # noqa: E402
from pl_codegen.validation.validator import Validator  # noqa: E402
from pl_codegen.xml_model.xml_reader import read_xml  # noqa: E402
from pl_codegen.xml_model.xml_writer import write_xml  # noqa: E402

_logging_utils._colour_enabled = colour_supported()

SYSTEM_NAMES = ["SYS_UNKNOWN", "SYS_NAV"]
PARAM_MODES = ["PARAM_MODE_USER", "PARAM_MODE_READ_ONLY"]
PARAMETER_TYPES = ["MONITORING", "SETTING", "COMMAND"]


# ---------------------------------------------------------------- builders
def tags(**overrides: Any) -> Dict[str, Any]:
    base = {"SystemName": "SYS_NAV", "ResetProof": False, "Loggable": False,
            "LogEncryption": False, "ParamMode": "PARAM_MODE_USER"}
    base.update(overrides)
    return base


def value(name: str = "GoodParam", **overrides: Any) -> Parameter:
    node = Parameter(name=name, param_type="MONITORING", value_type_name="uint8_t",
                     default_value=5, minimum=0, maximum=10, resolution=1,
                     unit="mm", user_name=name, description="A valid parameter.")
    node.tags = tags()
    for key, item in overrides.items():
        if key == "tags":
            node.tags.update(item)
        else:
            setattr(node, key, item)
    return node


def struct(name: str, *children: Parameter, **overrides: Any) -> Parameter:
    node = Parameter(name=name, kind=ParameterKind.STRUCT, param_type="MONITORING",
                     description="A structure.")
    node.tags = tags()
    node.children = list(children)
    for key, item in overrides.items():
        if key == "tags":
            node.tags.update(item)
        else:
            setattr(node, key, item)
    return node


def field(name: str, **overrides: Any) -> Parameter:
    """A field of a structure: no tags and no type of its own."""
    node = Parameter(name=name, value_type_name="uint8_t", default_value=0,
                     minimum=0, maximum=10, resolution=1, user_name=name,
                     description="A field.")
    for key, item in overrides.items():
        if key == "tags":
            node.tags.update(item)
        else:
            setattr(node, key, item)
    return node


def inner(name: str, *children: Parameter, **overrides: Any) -> Parameter:
    """A sub-structure: like a field, it carries no tags and no type."""
    node = Parameter(name=name, kind=ParameterKind.STRUCT, description="A structure.")
    node.children = list(children)
    for key, item in overrides.items():
        if key == "tags":
            node.tags.update(item)
        else:
            setattr(node, key, item)
    return node


def model(*parameters: Parameter) -> ParameterList:
    result = ParameterList(parameters=list(parameters))
    defines = Defines()
    for name in VALUE_TYPES:
        defines.add(COLUMN_VALUE_TYPES, name)
    for name in PARAMETER_TYPES:
        defines.add(COLUMN_TYPES, name)
    for name in SYSTEM_NAMES:
        defines.add(COLUMN_SYSTEM_NAMES, name)
    for name in PARAM_MODES:
        defines.add(COLUMN_PARAM_MODES, name)
    result.defines = defines

    # Every structure is of a structure type, so a model built here gets the
    # same treatment one read from a file does: a type made out of the shape
    # each structure already has.  Without it every fixture with a struct in it
    # would report "no structure type" and say nothing about the rule it is
    # really testing.
    adopt_types(result, [], Path("<test>"))
    apply_types(result.parameters, result.struct_types)
    return result


def _typeless_struct() -> ParameterList:
    """A structure whose type name was never set - a file edited by hand."""
    result = model(struct("S", field("A")))
    result.parameters[0].value_type_name = None
    return result


def _parameter_of_struct_type() -> ParameterList:
    """A plain parameter given a structure type: two different things."""
    result = model(struct("S", field("A")), value(name="Loose"))
    result.parameters[1].value_type_name = result.parameters[0].value_type_name
    return result


def _struct_of_value_type() -> ParameterList:
    """A structure given float32_t, which holds no fields."""
    result = model(struct("S", field("A")))
    result.parameters[0].value_type_name = "float32_t"
    return result


def _self_containing_type() -> ParameterList:
    """A struct with a field of its own type: it would have no size."""
    result = model(struct("S", field("A")))
    name = result.parameters[0].value_type_name
    result.struct_types.get(name).fields[0].value_type_name = name
    return result


def _one_type_in_two_lists() -> ParameterList:
    """Two lists both declaring 'S' - the same shape, and still two declarations."""
    first = model(struct("S", field("A")))
    second = model(struct("T", field("A")))
    second.struct_types.rename("T", "S")
    second.parameters[0].value_type_name = "S"
    return merge_lists([(Path("first.xml"), first), (Path("second.xml"), second)])


def _another_lists_type() -> ParameterList:
    """A list whose structure is of a type only the other list declares."""
    first = model(struct("S", field("A")))
    second = model(struct("T", field("A")))
    second.struct_types.remove("T")
    second.parameters[0].value_type_name = "S"
    return merge_lists([(Path("first.xml"), first), (Path("second.xml"), second)])


# ---------------------------------------------------------------- the cases
CASES: List[Dict[str, Any]] = [
    # ---- names -----------------------------------------------------------
    {"name": "invalid_name", "expect": "NAME001",
     "model": lambda: model(value("2Bad Name"))},
    {"name": "reserved_name", "expect": "NAME002",
     "model": lambda: model(value("struct"))},
    {"name": "duplicate_top_level", "expect": "NAME003",
     "model": lambda: model(value("Same"), value("Same"))},
    {"name": "duplicate_field", "expect": "NAME003",
     "model": lambda: model(struct("S", field("A"), field("A")))},
    {"name": "macro_collision", "expect": "NAME004",
     "model": lambda: model(value("TestVar"), value("Test_Var"))},

    # ---- structures ------------------------------------------------------
    {"name": "empty_struct", "expect": "STR001",
     "model": lambda: model(struct("Empty"))},
    {"name": "struct_array_size_zero", "expect": "STR002",
     "model": lambda: model(struct("S", field("A"), array_size=0))},
    {"name": "array_of_struct", "expect": None,
     "model": lambda: model(struct("S", field("A"), array_size=4))},
    {"name": "array_of_struct_with_array_field", "expect": None,
     "model": lambda: model(struct("S", field("A", array_size=3), array_size=4))},
    {"name": "array_of_nested_struct", "expect": None,
     "model": lambda: model(struct("S", inner("Inner", field("A")), array_size=2))},

    # ---- types and ranges -------------------------------------------------
    {"name": "unsupported_type", "expect": "TYPE002",
     "model": lambda: model(value(value_type_name="sMyStruct"))},
    # NAME005 had no case at all, so nothing would have noticed if the rule
    # stopped firing.  '_' is a legal C identifier and derives an EMPTY macro,
    # which is exactly the gap between NAME001 and NAME005.
    {"name": "name_derives_a_bad_macro", "expect": "NAME005",
     "model": lambda: model(value("_"))},
    {"name": "unknown_parameter_type", "expect": "GRP002",
     "model": lambda: model(value(param_type="TELEMETRY"))},
    {"name": "struct_without_parameter_type", "expect": "GRP001",
     "model": lambda: model(struct("S", field("A"), param_type=None))},
    # A field carrying tags or a parameter type of its own cannot exist any
    # more: a structure type owns the shape of its fields, and applying one
    # clears both.  The reader still tells anybody who writes such a file by
    # hand (XML013 / XML014) - see check_messages below.
    {"name": "struct_without_a_type", "expect": "TYP002",
     "model": lambda: _typeless_struct()},
    {"name": "parameter_typed_as_a_struct", "expect": "TYP004",
     "model": lambda: _parameter_of_struct_type()},
    {"name": "struct_typed_as_a_value", "expect": "TYP005",
     "model": lambda: _struct_of_value_type()},
    {"name": "struct_type_containing_itself", "expect": "TYP015",
     "model": lambda: _self_containing_type()},
    {"name": "one_type_name_in_two_lists", "expect": "TYP016",
     "model": lambda: _one_type_in_two_lists()},
    {"name": "a_list_using_another_lists_type", "expect": "TYP017",
     "model": lambda: _another_lists_type()},
    {"name": "bad_array_size", "expect": "ARR001",
     "model": lambda: model(value(array_size=0))},
    {"name": "value_out_of_c_type", "expect": "RNG001",
     "model": lambda: model(value(maximum=5000))},
    {"name": "min_greater_than_max", "expect": "RNG002",
     "model": lambda: model(value(minimum=10, maximum=1, default_value=5))},
    {"name": "default_out_of_range", "expect": "RNG003",
     "model": lambda: model(value(default_value=99))},

    # ---- tags -------------------------------------------------------------
    {"name": "missing_mandatory_tag", "expect": "TAG001",
     "model": lambda: model(value(tags={"SystemName": None}))},
    {"name": "unknown_system_name", "expect": "TAG003",
     "model": lambda: model(value(tags={"SystemName": "SYS_NOPE"}))},
    {"name": "loggable_without_log_id", "expect": "TAG010",
     "model": lambda: model(value(tags={"Loggable": True}))},
    {"name": "loggable_without_user_name", "expect": "TAG011",
     "model": lambda: model(value(tags={"Loggable": True}, log_id=500, user_name=None))},
    {"name": "loggable_without_description_is_fine", "expect": None,
     "model": lambda: model(value(tags={"Loggable": True}, log_id=501, description=None))},
    {"name": "duplicate_log_id", "expect": "TAG012",
     "model": lambda: model(value("A", tags={"Loggable": True}, log_id=500),
                            value("B", tags={"Loggable": True}, log_id=500))},
    # float64_t x2 reserves 16 ids: 400..415, so 410 must be refused
    # A log id reserves ONE id per array element and does not depend on the
    # type: float64_t[10] at 400 hands 400..409 to its ten elements, so the
    # element that got 405 and 'Next' are two values holding the same id.
    {"name": "log_id_inside_an_array", "expect": "TAG012",
     "model": lambda: model(
         value("Wide", value_type_name="float64_t", array_size=10, minimum=0, maximum=0,
               default_value=0, tags={"Loggable": True}, log_id=400),
         value("Next", tags={"Loggable": True}, log_id=405))},

    # The descriptor stores the log id in a uint16_t, and an array reserves one
    # id per element - so it is the END of the range that has to fit.  65530
    # itself is legal; 65530 plus ten elements is not.
    {"name": "log_id_over_uint16", "expect": "TAG015",
     "model": lambda: model(value("Late", array_size=10,
                                  tags={"Loggable": True}, log_id=65530))},
    # every element of an array is a value with an id of its own, so an array
    # of 10 really does占 ten of them
    {"name": "log_id_one_per_element", "expect": None,
     "model": lambda: model(
         value("Block", array_size=4, tags={"Loggable": True}, log_id=800),
         value("After", tags={"Loggable": True}, log_id=804))},
    {"name": "log_id_last_that_fits", "expect": None,
     "model": lambda: model(value("Last", array_size=6,
                                  tags={"Loggable": True}, log_id=65530))},

    # ---- the good cases ---------------------------------------------------
    {"name": "log_id_range_ok", "expect": None,
     "model": lambda: model(
         value("Wide", value_type_name="float64_t", array_size=2, minimum=0, maximum=0,
               default_value=0, tags={"Loggable": True}, log_id=400),
         value("Next", tags={"Loggable": True}, log_id=416))},
    {"name": "empty_list", "expect": "VAL001", "model": lambda: model()},
    {"name": "all_disabled", "expect": "VAL001",
     "model": lambda: model(value(enable=False))},
    {"name": "flat_ok", "expect": None,
     "model": lambda: model(value("First"), value("Second"))},
    # every field takes the mandatory tags and the type of its structure
    {"name": "struct_inherits_ok", "expect": None,
     "model": lambda: model(struct("Position",
                                   inner("Home", field("Lat"), field("Lon")),
                                   field("Alt")))},
    # one log id on the structure covers all of its fields
    {"name": "struct_log_id_ok", "expect": None,
     "model": lambda: model(struct("S", field("A"), field("B"), field("C"),
                                   tags={"Loggable": True}, log_id=700))},
    # an exact clash with one of the fields is the clearer TAG012
    {"name": "struct_log_id_hits_field", "expect": "TAG012",
     "model": lambda: model(
         struct("S", field("A"), field("B"), field("C"),
                tags={"Loggable": True}, log_id=700),
         value("After", tags={"Loggable": True}, log_id=702))},
    # A struct hands one id per leaf value: three fields at 700 take 700, 701
    # and 702.  An array of 2 starting at 701 wants 701 and 702 as well, so both
    # of its elements collide with a field.
    {"name": "struct_log_id_block_collides", "expect": "TAG012",
     "model": lambda: model(
         struct("S", field("A"), field("B"), field("C"),
                tags={"Loggable": True}, log_id=700),
         value("After", array_size=2, tags={"Loggable": True}, log_id=701))},
    # the block of S is 700..702, so 703 is the first free id
    {"name": "struct_log_id_block_ok", "expect": None,
     "model": lambda: model(
         struct("S", field("A"), field("B"), field("C"),
                tags={"Loggable": True}, log_id=700),
         value("After", tags={"Loggable": True}, log_id=703))},

    # ---- names the generator invents, which the user never sees -----------
    # An array field belongs to its structure TYPE: type 'A' with a field 'B' of
    # two elements is A_B_ARRAY_SIZE - exactly the macro a top level array
    # called 'A_B' asks for.  Nothing else catches it, and the defines header
    # would hold one macro twice.
    {"name": "type_array_macro_collision", "expect": "NAME004",
     "model": lambda: model(struct("A", field("B", array_size=2)),
                            value("A_B", array_size=2))},
    {"name": "type_array_macros_distinct", "expect": None,
     "model": lambda: model(struct("A", field("B", array_size=2)),
                            value("A_C", array_size=2))},
    # Two structures of one shape are two instances of ONE type: one typedef
    # and one set of field macros between them, and no collision.
    {"name": "two_structures_share_one_type", "expect": None,
     "model": lambda: model(struct("P1", field("S", array_size=2)),
                            struct("P2", field("S", array_size=2)))},
    # The elements of a struct array share one declaration, so they must share
    # one array size macro rather than collide over it.
    {"name": "struct_array_shares_one_size_macro", "expect": None,
     "model": lambda: model(struct("Wheels", field("Samples", array_size=4),
                                   array_size=3))},
]


def run_case(config: Config, build: Callable[[], ParameterList]) -> Set[str]:
    diagnostics = DiagnosticCollector()
    Validator(config).validate(build(), diagnostics)
    return {item.code for item in diagnostics.items if item.severity is Severity.ERROR}


# ------------------------------------------------- what a message must say
#
# The cases above ask "is the mistake found?".  These ask the other half of
# the question: is what comes back usable?  A diagnostic that does not say
# WHERE cannot be clicked and cannot be found in a list of four hundred
# values, one that does not say WHAT TO DO leaves the reader staring at a red
# line - and one that says it four hundred times buries every other problem
# in the panel.


def broken_model() -> ParameterList:
    """One model that trips a rule of every family, for the message checks."""
    return model(
        value("NoTags", tags={"SystemName": None, "ResetProof": None,
                              "Loggable": None, "LogEncryption": None,
                              "ParamMode": None}),
        value("Backwards", minimum=100, maximum=10),
        value("Fractional", value_type_name="int8_t", resolution=1.5),
        value("2bad"),
        value("Unknown", value_type_name="int24_t"),
        value("NoParamType", param_type=""),
        struct("Empty"),
    )


def check_messages(config: Config, work_dir: Path) -> int:
    """Returns the number of failed checks; prints one line each."""
    failed = 0

    def verdict(name: str, ok: bool, detail: str) -> None:
        nonlocal failed
        mark = paint("PASS", GREEN) if ok else paint("FAIL", BOLD + BRIGHT_RED)
        print(f"  [{mark}] {name:<32} {detail}")
        if not ok:
            failed += 1

    # -- every error says where it is, and what to do about it -------------
    diagnostics = DiagnosticCollector()
    Validator(config).validate(broken_model(), diagnostics)
    # ... and the problems only a build of several lists can have
    for several in (_one_type_in_two_lists, _another_lists_type):
        Validator(config).validate(several(), diagnostics)
    errors = [item for item in diagnostics.items if item.severity is Severity.ERROR]

    homeless = [item.code for item in errors
                if not (item.location.parameter or item.location.file)]
    verdict("every error says where", not homeless,
            f"{len(errors)} error(s) checked; "
            f"{', '.join(sorted(set(homeless))) or 'all located'}")

    silent = [item.code for item in errors if not item.hint]
    verdict("every error says what to do", not silent,
            f"{', '.join(sorted(set(silent))) or 'all have a hint'}")

    # -- one report per declaration, not one per element -------------------
    #
    # flatten() is the generator's view - one entry per value - so a rule that
    # walked it reported a missing tag once per element.  A 70000 element
    # array turned five empty cells into 350000 errors.
    untagged = value("Big", array_size=64,
                     tags={"SystemName": None, "ResetProof": None, "Loggable": None,
                           "LogEncryption": None, "ParamMode": None})
    array_diagnostics = DiagnosticCollector()
    Validator(config).validate(model(untagged), array_diagnostics)
    per_array = [item for item in array_diagnostics.items if item.code == "TAG001"]
    verdict("one report per declaration", len(per_array) == 1,
            f"a 64 element array with no tags gave {len(per_array)} TAG001")

    # -- an empty description is never a problem, loggable or not ----------
    #
    # Description is free text with no validation of its own: a loggable
    # value is named in the log by its User Name (below), not by its
    # description, so nothing checks description at all any more.
    def coded(code: str, *parameters: Parameter) -> List[Any]:
        found = DiagnosticCollector()
        Validator(config).validate(model(*parameters), found)
        return [item for item in found.items if item.code == code]

    quiet = coded("META001", value("Quiet", description=None))
    verdict("an empty description is quiet", not quiet,
            f"not loggable, and it said: {[item.message for item in quiet]}")

    still_quiet = coded("META001", value("Logged", description=None,
                                         tags={"Loggable": True}, log_id=7))
    verdict("even when the value is loggable", not still_quiet,
            f"loggable, and it still said: {[item.message for item in still_quiet]}")

    # -- an empty user name matters only for a loggable value --------------
    #
    # The log names a value by its User Name - there is no separate "log
    # name" field - so a loggable one without it is an error.  Every other
    # empty user name is nobody's business.
    quiet_name = coded("TAG011", value("Quiet", user_name=None))
    verdict("an empty user name is quiet", not quiet_name,
            f"not loggable, and it said: {[item.message for item in quiet_name]}")

    loud_name = coded("TAG011", value("Logged", user_name=None,
                                      tags={"Loggable": True}, log_id=7))
    verdict("unless the value is loggable", len(loud_name) == 1
            and loud_name[0].severity is Severity.ERROR and "log" in loud_name[0].message,
            f"{[(item.severity.label, item.message) for item in loud_name]}")

    # -- a fractional value on an integer type survives the round trip -----
    #
    # The reader used to drop it, which left the editor showing an empty cell
    # for a value the file plainly held: nothing to correct on screen, and
    # saving erased what had been typed.
    path = work_dir / "fractional.xml"
    write_xml(model(value("Step", value_type_name="int8_t", resolution=1.5)),
              path, emit_timestamp=False)
    read_back = DiagnosticCollector()
    reloaded = read_xml(path, read_back)
    kept = reloaded.parameters[0].resolution
    verdict("a fractional value is kept", float(kept or 0) == 1.5,
            f"resolution came back as {kept!r}")

    rule_diagnostics = DiagnosticCollector()
    Validator(config).validate(reloaded, rule_diagnostics)
    codes = {item.code for item in rule_diagnostics.items}
    verdict("and is reported as RNG017", "RNG017" in codes,
            f"reported: {', '.join(sorted(codes)) or '-'}")

    # -- the parameter is named, not just the file -------------------------
    located = [item for item in rule_diagnostics.items if item.code == "RNG017"]
    named = bool(located) and located[0].location.parameter == "Step"
    verdict("and names the parameter", named,
            f"location: {located[0].location if located else 'missing'}")

    # -- one description per VALUE -----------------------------------------
    #
    # An array is one declaration and many values, and a value may say what IT
    # means instead of what the array does.  flatten() is where that is
    # resolved, because it is the pass the generated table is written from.
    speed = value("Speed", array_size=4, description="Every wheel.")
    speed.element_descriptions["2"] = "The third one, which is different."
    # [0] is an element like any other: it may carry its own text, and the
    # declaration's is what the ones with nothing of their own read.
    speed.element_descriptions["0"] = "The first one."
    wheels = struct("Wheels", field("Rpm", description="How fast it turns."),
                    array_size=2)
    wheels.children[0].element_descriptions["1"] = "The rear wheel."
    described = model(speed, wheels)
    # The structure's fields are re-applied from its type, which must not take
    # a field's own descriptions with it - they belong to this parameter.
    apply_types(described.parameters, described.struct_types)
    said = {leaf.name: leaf.description for leaf in described.flatten()}
    verdict("one description per value",
            said.get("Speed[2]") == "The third one, which is different."
            and said.get("Speed[0]") == "The first one."
            and said.get("Speed[3]") == "Every wheel.",
            f"Speed[2]: {said.get('Speed[2]')!r}, Speed[0]: {said.get('Speed[0]')!r}")
    verdict("a field of a struct array too",
            said.get("Wheels[1].Rpm") == "The rear wheel."
            and said.get("Wheels[0].Rpm") == "How fast it turns.",
            f"Wheels[1].Rpm: {said.get('Wheels[1].Rpm')!r}")

    plain = model(value("Plain", array_size=3, description="All three."))
    verdict("a list nobody touched is unchanged",
            {leaf.description for leaf in plain.flatten()} == {"All three."},
            "every element still reads the declaration's description")

    # -- and it survives the file ------------------------------------------
    path = work_dir / "elements.xml"
    write_xml(described, path, emit_timestamp=False)
    reloaded = read_xml(path, DiagnosticCollector())
    back = {leaf.name: leaf.description for leaf in reloaded.flatten()}
    verdict("the file keeps them", back == said,
            f"{len(reloaded.parameters[0].element_descriptions)} on Speed, "
            f"{len(reloaded.parameters[1].children[0].element_descriptions)} on Rpm")

    # -- an element path that is not one is ignored, and says so ------------
    hand_edited = path.read_text(encoding="utf-8").replace(
        '<Element at="2">', '<Element at="the third">')
    (work_dir / "bad_at.xml").write_text(hand_edited, encoding="utf-8")
    bad = DiagnosticCollector()
    read_xml(work_dir / "bad_at.xml", bad)
    verdict("a bad element path is warned about",
            "XML018" in {item.code for item in bad.items},
            f"reported: {', '.join(sorted({item.code for item in bad.items})) or '-'}")

    # -- the mode smart data fixes is one missing list entry, not three -----
    #
    # A smart-data project writes PARAM_MODE_NONE into every parameter.  On a
    # machine whose PARAM MODES list does not have it, that is said once, on
    # the first parameter, with where to add it.
    fixed = apply_fixed_tags(model(value("First"), value("Second"), value("Third")), config)
    found = DiagnosticCollector()
    Validator(config).validate(fixed, found)
    missing = [item for item in found.items if item.code == "TAG003"]
    verdict("a fixed mode not in the list",
            len(missing) == 1 and "Drop-down lists" in (missing[0].hint or "")
            and bool(missing[0].location.parameter or missing[0].location.file),
            f"{len(missing)} TAG003 for three parameters")
    fixed.defines.add(COLUMN_PARAM_MODES, "PARAM_MODE_NONE")
    found = DiagnosticCollector()
    Validator(config).validate(fixed, found)
    verdict("and none once it is listed",
            not [item for item in found.items if item.severity is Severity.ERROR],
            f"reported: {', '.join(sorted({item.code for item in found.items})) or '-'}")

    return failed


def main() -> int:
    setup_logging(quiet=True)
    failures = 0

    with tempfile.TemporaryDirectory(prefix="pl_codegen_validation_") as raw_dir:
        work_dir = Path(raw_dir)
        config_path = work_dir / "config.json"
        config_path.write_text(json.dumps({
            "inputs": {"model_file": str(work_dir / "model.xml")},
            "output": {"code_directory": str(work_dir / "gen")},
            "style": {"snippet_file": str(SNIPPET_FILE)},
        }), encoding="utf-8")
        config = Config.load(config_path)

        for case in CASES:
            codes = run_case(config, case["model"])
            expected: Optional[str] = case["expect"]

            if expected is None:
                ok = not codes
                detail = "no error expected"
            else:
                ok = expected in codes
                detail = f"expected {expected}"

            mark = paint("PASS", GREEN) if ok else paint("FAIL", BOLD + BRIGHT_RED)
            print(f"  [{mark}] {case['name']:<24} {detail}; "
                  f"reported: {', '.join(sorted(codes)) or '-'}")
            if not ok:
                failures += 1

        print()
        failures += check_messages(config, work_dir)

    print()
    if failures:
        print(paint(f"{failures} validation check(s) FAILED.", BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} validation cases and every message check passed.",
                GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
