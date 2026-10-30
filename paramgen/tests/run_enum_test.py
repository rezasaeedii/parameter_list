# -*- coding: utf-8 -*-
"""Enumerations: a parameter that holds only the values the editor gave it.

An enumeration is declared in the Enum types dialog of a sublist, beside its
structure types.  A parameter of one stays a value of its base type - the
smart data functions take it as they are - and the generator writes a
typedef, a #define for every value and IS_VALID_<name>(), and makes every
write of the parameter refuse any other number.  (Asked for.)

Every case is driven through the API the dialog calls, or through the
validator and the generator the build runs; the last one compiles what is
generated and runs it.

Run it with::

    python tests/run_enum_test.py
"""

import pathlib
import shutil
import subprocess
import sys
import tempfile
import traceback
import json

APP = pathlib.Path(__file__).resolve().parent.parent
ROOT = APP.parent
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP))

import pl_codegen.choices as choices                                 # noqa: E402
from pl_codegen.app_home import SNIPPET_FILE                         # noqa: E402
from pl_codegen.config import Config                                 # noqa: E402
from pl_codegen.errors import DiagnosticCollector, Severity          # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,       # noqa: E402
                                      YELLOW, colour_supported, paint, setup_logging)
import pl_codegen.logging_utils as _logging_utils                    # noqa: E402
from pl_codegen.model.defines import (COLUMN_TYPES, COLUMN_PARAM_MODES,  # noqa: E402
                                      COLUMN_SYSTEM_NAMES, COLUMN_VALUE_TYPES, Defines)
from pl_codegen.model.enum_type import ENUM_BASE_TYPES, EnumType, EnumValue  # noqa: E402
from pl_codegen.model.parameter import Parameter                     # noqa: E402
from pl_codegen.model.parameter_list import ParameterList            # noqa: E402
from pl_codegen.model.types import VALUE_TYPES                       # noqa: E402
from pl_codegen.validation.validator import Validator                # noqa: E402
from pl_codegen.xml_model.types_xml import types_file_for            # noqa: E402
from tests.run_struct_test import _second_list, new_project          # noqa: E402
import tests.run_compile_test as compile_test                        # noqa: E402

_logging_utils._colour_enabled = colour_supported()


class Failure(AssertionError):
    """One case did not hold."""


def equal(got, want, what):
    if got != want:
        raise Failure(f"{what}: expected {want!r}, got {got!r}")


def true(value, what):
    if not value:
        raise Failure(what)


#: the rows as the dialog sends them; STABILIZE and LAND left to be counted
MODES = [{"name": "FLIGHT_MODE_MANUAL", "value": "0"},
         {"name": "FLIGHT_MODE_STABILIZE", "value": ""},
         {"name": "FLIGHT_MODE_HOLD", "value": "5"},
         {"name": "FLIGHT_MODE_LAND", "value": ""}]
COUNTED = [["FLIGHT_MODE_MANUAL", 0], ["FLIGHT_MODE_STABILIZE", 1],
           ["FLIGHT_MODE_HOLD", 5], ["FLIGHT_MODE_LAND", 6]]


def with_modes(work, name="enums"):
    """A project with eFlightMode declared and one parameter of it."""
    document, api, root = new_project(work, name)
    answer = api.new_enum({"name": "eFlightMode", "baseType": "uint8_t", "values": MODES})
    true(answer["ok"], f"declaring eFlightMode: {answer.get('message')}")
    true(api.add({"parent": "", "kind": "primitive"})["ok"], "a parameter is added")
    answer = api.update({"path": "NewParameter", "changes": {
        "name": "FlightMode", "enum_type_name": "eFlightMode", "value_type_name": "uint8_t"}})
    true(answer["ok"], f"FlightMode becomes an eFlightMode: {answer.get('message')}")
    return document, api, root, document.find("FlightMode")


def enum_state(api):
    return {item["name"]: item for item in api.state({})["enumTypes"]}


# ------------------------------------------------------------------ cases
def test_declaring_one(work):
    """Declared from the dialog's rows; an empty number is the next one."""
    document, api, _root = new_project(work)
    answer = api.new_enum({"name": "eFlightMode", "baseType": "uint8_t", "values": MODES})
    true(answer["ok"], f"declared: {answer.get('message')}")
    shown = enum_state(api)["eFlightMode"]
    equal(shown["values"], COUNTED, "an empty number is the one after the value above")
    equal(shown["baseType"], "uint8_t", "its base type")
    equal(shown["usedHere"], [], "nothing uses it yet")

    bases = api.state({})["enumBaseTypes"]
    equal([item["name"] for item in bases], list(ENUM_BASE_TYPES), "the integers offered")
    biggest = next(item for item in bases if item["name"] == "uint64_t")
    equal(biggest["max"], "18446744073709551615", "a uint64_t's range as text, whole")

    true(api.undo({})["ok"], "undo")
    equal(enum_state(api), {}, "undo takes the declaration back")
    true(api.redo({})["ok"], "redo")
    true("eFlightMode" in enum_state(api), "and redo brings it again")
    equal(document.validate_codes("ENUM003"), 0, "it has values")


def test_bad_ones_are_refused(work):
    """Every mistake the dialog can send is refused, saying what it is."""
    _document, api, _root = new_project(work)
    true(api.new_type({"name": "Position"})["ok"], "a structure type Position")
    one = [{"name": "A", "value": "1"}]
    cases = [
        ({"name": "", "values": one}, "needs a name"),
        ({"name": "2fast", "values": one}, "not a C name"),
        ({"name": "int", "values": one}, "not a C name"),
        ({"name": "uint8_t", "values": one}, "is a data type already"),
        ({"name": "Position", "values": one}, "structure type"),
        ({"name": "eX", "baseType": "float32_t", "values": one}, "is an integer"),
        ({"name": "eX", "values": []}, "at least one value"),
        ({"name": "eX", "values": [{"name": "", "value": "3"}]}, "has no name"),
        ({"name": "eX", "values": [{"name": "A-B", "value": ""}]}, "not a C name"),
        ({"name": "eX", "values": [{"name": "A", "value": "x"}]}, "not a whole number"),
        ({"name": "eX", "values": [{"name": "A", "value": "300"}]}, "does not fit a uint8_t"),
        ({"name": "eX", "baseType": "int8_t", "values": [{"name": "A", "value": "-129"}]},
         "does not fit a int8_t"),
        ({"name": "eX", "values": [{"name": "A", "value": ""}, {"name": "A", "value": ""}]},
         "there twice"),
        ({"name": "eX", "values": [{"name": "A", "value": "1"}, {"name": "B", "value": "1"}]},
         "are both 1"),
    ]
    for request, said in cases:
        answer = api.new_enum(request)
        equal(answer["ok"], False, f"{request} is refused")
        true(said in answer["message"], f"{request}: expected '{said}' in {answer['message']!r}")
    true(api.new_enum({"name": "eX", "values": one})["ok"], "a good one after all of that")
    answer = api.new_enum({"name": "eX", "values": one})
    true(not answer["ok"] and "already exists" in answer["message"], "but not twice")
    equal(sorted(enum_state(api)), ["eX"], "and the refused ones left nothing behind")
    # hexadecimal is a number too, and a negative one in a signed type
    true(api.new_enum({"name": "eHex", "baseType": "int16_t", "values": [
        {"name": "H_NEG", "value": "-2"}, {"name": "H_HEX", "value": "0x10"}]})["ok"],
         "-2 and 0x10")
    equal(enum_state(api)["eHex"]["values"], [["H_NEG", -2], ["H_HEX", 16]], "read as numbers")


def test_a_parameter_of_one(work):
    """Chosen as the data type: its base type, its range, one of its values."""
    document, api, _root, node = with_modes(work)
    equal((node.value_type_name, node.enum_type_name), ("uint8_t", "eFlightMode"),
          "the base type, with the enumeration beside it")
    equal((node.minimum, node.maximum, node.resolution), (0, 6, 1),
          "the range is its smallest value to its largest")
    equal(node.default_value, 0, "the default is its first value")
    tree = api.state({})["tree"][0]
    equal((tree["enumType"], tree["valueType"]), ("eFlightMode", "uint8_t"), "the page is told")
    equal(enum_state(api)["eFlightMode"]["usedHere"], ["FlightMode"], "and it is used here")

    api.update({"path": "FlightMode", "changes": {"minimum": 3, "maximum": 200}})
    equal((node.minimum, node.maximum), (0, 6), "the range cannot be edited away from it")

    true(api.update({"path": "FlightMode", "changes": {"default_value": 5}})["ok"], "HOLD")
    equal(document.validate_codes("ENUM015"), 0, "5 is one of its values")
    api.update({"path": "FlightMode", "changes": {"default_value": 3}})
    equal(document.validate_codes("ENUM015"), 1, "3 is in the range, and none of its values")
    equal(document.generate()["success"], False, "and is not generated")
    api.update({"path": "FlightMode", "changes": {"default_value": 5}})

    true(api.update({"path": "FlightMode", "changes": {"value_type_name": "uint16_t"}})["ok"],
         "a plain data type again")
    equal((node.value_type_name, node.enum_type_name), ("uint16_t", None),
          "a plain data type takes the enumeration away")
    api.update({"path": "FlightMode", "changes": {"maximum": 200}})
    equal(node.maximum, 200, "and its range is its own again")

    answer = api.update({"path": "FlightMode", "changes": {"enum_type_name": "eNothing"}})
    true(not answer["ok"] and "no enumeration called" in answer["message"],
         f"an enumeration the sublist does not have is refused: {answer}")


def test_editing_reaches_every_use(work):
    """A value keeps its meaning: a default that was HOLD stays HOLD."""
    document, api, root, node = with_modes(work)
    api.update({"path": "FlightMode", "changes": {"default_value": 5}})
    rows = [{"name": name, "value": str(number)} for name, number in COUNTED]

    rows[2]["value"] = "7"                              # HOLD 5 -> 7
    true(api.update_enum({"name": "eFlightMode", "changes": {"values": rows}})["ok"], "renumber")
    equal(node.default_value, 7, "the default follows HOLD to its new number")
    equal(node.maximum, 7, "and the range to its new largest value")

    answer = api.update_enum({"name": "eFlightMode", "changes": {"values": rows[:2]}})
    true(not answer["ok"] and "FlightMode" in answer["message"]
         and "FLIGHT_MODE_HOLD" in answer["message"],
         f"taking away a value that is a default is refused, saying where: {answer}")
    equal(len(enum_state(api)["eFlightMode"]["values"]), 4, "and nothing changed")

    too_big = [dict(row) for row in rows] + [{"name": "FLIGHT_MODE_FAR", "value": "300"}]
    answer = api.update_enum({"name": "eFlightMode", "changes": {"values": too_big}})
    true(not answer["ok"] and "does not fit" in answer["message"], "300 in a uint8_t")

    answer = api.update_enum({"name": "eFlightMode", "changes": {"baseType": "uint16_t"}})
    true(answer["ok"], f"a wider base type: {answer.get('message')}")
    equal(node.value_type_name, "uint16_t", "the parameter is of the new base type")

    answer = api.update_enum({"name": "eFlightMode", "changes": {"name": "eMode"}})
    true(answer["ok"], f"renamed: {answer.get('message')}")
    equal(node.enum_type_name, "eMode", "the parameter follows the new name")
    equal(sorted(enum_state(api)), ["eMode"], "and the old name is gone")
    document.save()
    text = types_file_for(root / "parameter_lists" / "list.xml").read_text(encoding="utf-8")
    true('<EnumType name="eMode" baseType="uint16_t">' in text, "the types file says so")
    true('<Value name="FLIGHT_MODE_HOLD" value="7" />' in text, "with the new number")


def test_deleting_one(work):
    """Refused while anything uses it - and saying what."""
    _document, api, _root, _node = with_modes(work)
    answer = api.delete_enum({"name": "eFlightMode"})
    true(not answer["ok"] and "FlightMode" in answer["message"],
         f"refused while FlightMode is one: {answer}")
    api.update({"path": "FlightMode", "changes": {"value_type_name": "uint8_t",
                                                  "enum_type_name": None}})
    true(api.delete_enum({"name": "eFlightMode"})["ok"], "deleted once nothing uses it")
    equal(enum_state(api), {}, "gone")
    answer = api.delete_enum({"name": "eFlightMode"})
    true(not answer["ok"] and "no enumeration" in answer["message"], "deleting it again says so")


def test_a_field_of_a_structure(work):
    """A field may be of one too: every structure of that type gets it."""
    document, api, _root = new_project(work)
    true(api.new_enum({"name": "eFlightMode", "values": MODES})["ok"], "declared")
    answer = api.add_structure({"name": "Mission", "type": "sMission", "fields": [
        {"name": "Mode", "valueType": "uint8_t", "enumType": "eFlightMode", "arraySize": 1},
        {"name": "Legs", "valueType": "uint16_t", "arraySize": 1}]})
    true(answer["ok"], f"a structure with a field of it: {answer.get('message')}")
    mode = document.find("Mission.Mode")
    equal((mode.value_type_name, mode.enum_type_name, mode.maximum),
          ("uint8_t", "eFlightMode", 6), "the field is an eFlightMode, with its range")
    equal(document.find("Mission.Legs").enum_type_name, None, "the other field is not")
    fields = {item["name"]: item for item in api.state({})["structTypes"]}["sMission"]["fields"]
    equal(fields[0]["enumType"], "eFlightMode", "the Structure types dialog is told")
    true("sMission.Mode (field)" in enum_state(api)["eFlightMode"]["usedHere"],
         "and the enumeration says where it is used")

    answer = api.new_type({"name": "sBad", "fields": [
        {"name": "Mode", "valueType": "uint8_t", "enumType": "eNothing", "arraySize": 1}]})
    true(not answer["ok"] and "eNothing" in answer["message"],
         f"a field of an enumeration the sublist does not have is refused: {answer}")

    rows = [{"name": name, "value": str(number)} for name, number in COUNTED]
    rows[3]["value"] = "9"
    true(api.update_enum({"name": "eFlightMode", "changes": {"values": rows}})["ok"], "LAND 9")
    equal(document.find("Mission.Mode").maximum, 9, "the field's range follows")

    # a field the structure already had, made one by editing the type
    api.update({"path": "Mission.Legs", "changes": {"default_value": 3}})
    answer = api.update_type({"name": "sMission", "changes": {"fields": [
        {"name": "Mode", "valueType": "uint8_t", "enumType": "eFlightMode", "arraySize": 1},
        {"name": "Legs", "valueType": "uint16_t", "enumType": "eFlightMode", "arraySize": 1}]}})
    true(answer["ok"], f"Legs becomes an eFlightMode too: {answer.get('message')}")
    legs = document.find("Mission.Legs")
    equal((legs.value_type_name, legs.minimum, legs.maximum, legs.default_value),
          ("uint8_t", 0, 9, 0), "its base type and range, and 3 - no value - becomes the first")
    equal(document.validate_codes("ENUM015"), 0, "so nothing is reported")


def test_saved_and_read_back(work):
    """In the types file beside the list, and on the parameter, and back."""
    document, api, root, _node = with_modes(work)
    api.update({"path": "FlightMode", "changes": {"default_value": 5}})
    document.save()
    listing = (root / "parameter_lists" / "list.xml").read_text(encoding="utf-8")
    true('valueType="uint8_t" enumType="eFlightMode"' in listing,
         "the parameter keeps its base type and names its enumeration")
    types = types_file_for(root / "parameter_lists" / "list.xml").read_text(encoding="utf-8")
    for name, number in COUNTED:
        true(f'<Value name="{name}" value="{number}" />' in types, f"{name} = {number} is saved")

    document.load(root / "parameter_lists" / "list.xml")
    equal(enum_state(api)["eFlightMode"]["values"], COUNTED, "read back the same")
    again = document.find("FlightMode")
    equal((again.enum_type_name, again.default_value, again.maximum), ("eFlightMode", 5, 6),
          "and the parameter with it")
    equal([item["code"] for item in document.validate() if item["code"].startswith("ENUM")],
          [], "nothing to report")


def test_it_belongs_to_its_sublist(work):
    """Like a structure type: the sublist's own, and a name free in the project."""
    document, api, root, _node = with_modes(work)
    document.save()
    second = _second_list(document, root)
    equal(enum_state(api), {}, "the second sublist sees none of the first's")
    answer = api.new_enum({"name": "eFlightMode", "values": MODES})
    true(not answer["ok"] and "list" in answer["message"],
         f"the name is taken in the project: {answer}")
    true(api.add({"parent": "", "kind": "primitive"})["ok"], "a parameter here")
    answer = api.update({"path": "NewParameter", "changes": {"enum_type_name": "eFlightMode"}})
    true(not answer["ok"], "it cannot be of the first sublist's enumeration")
    document.save()

    # ...and a file edited by hand to use it anyway is reported, not built
    text = second.read_text(encoding="utf-8")
    text = text.replace('valueType="uint8_t"', 'valueType="uint8_t" enumType="eFlightMode"', 1)
    second.write_text(text, encoding="utf-8")
    document.load(second)
    found = [item for item in document.validate() if item["code"] == "ENUM011"]
    equal(len(found), 1, "using another sublist's enumeration is one problem")
    true("list.xml" in found[0]["message"], f"naming the sublist that has it: {found[0]}")
    equal(document.generate()["success"], False, "and it is not generated")


# ------------------------------------------------------------- the validator
def _model(*parameters, enums=()):
    result = ParameterList(parameters=list(parameters))
    defines = Defines()
    for name in VALUE_TYPES:
        defines.add(COLUMN_VALUE_TYPES, name)
    for name in ("MONITORING", "SETTING"):
        defines.add(COLUMN_TYPES, name)
    defines.add(COLUMN_SYSTEM_NAMES, "SYS_NAV")
    defines.add(COLUMN_PARAM_MODES, "PARAM_MODE_USER")
    result.defines = defines
    for item in enums:
        result.struct_types.put_enum(item)
    return result


def _param(name="Mode", enum="eMode", value_type="uint8_t", default=0):
    node = Parameter(name=name, param_type="SETTING", value_type_name=value_type,
                     enum_type_name=enum, default_value=default, minimum=0, maximum=2,
                     resolution=1, user_name=name, description="An enumeration.")
    node.tags = {"SystemName": "SYS_NAV", "ResetProof": False, "Loggable": False,
                 "LogEncryption": False, "ParamMode": "PARAM_MODE_USER"}
    return node


def _enum(name="eMode", base="uint8_t", *values):
    return EnumType(name, base, [EnumValue(*item) for item in (values or
                    [("MODE_A", 0), ("MODE_B", 2)])])


def test_what_the_validator_finds(work):
    """A file edited by hand can say anything; the build says what is wrong."""
    def config(output_format):
        path = work / f"{output_format}.json"
        path.write_text(json.dumps({
            "inputs": {"model_file": str(work / "model.xml")},
            "output": {"code_directory": str(work / "gen"), "format": output_format},
            "style": {"snippet_file": str(SNIPPET_FILE)}}), encoding="utf-8")
        return Config.load(path)

    smart, table = config("smart_data"), config("param_table")

    def errors(model, chosen=smart):
        found = DiagnosticCollector()
        Validator(chosen).validate(model, found)
        return {item.code for item in found.items if item.severity is Severity.ERROR}

    cases = [
        ("a good one", _model(_param(), enums=[_enum()]), None),
        ("a name that is no C name", _model(enums=[_enum("2bad")]), "ENUM001"),
        ("a base that is no integer", _model(enums=[_enum("eF", "float32_t")]), "ENUM002"),
        ("no values", _model(enums=[EnumType("eNone", "uint8_t", [])]), "ENUM003"),
        ("a value name that is no C name",
         _model(enums=[_enum("eV", "uint8_t", ("A B", 0))]), "ENUM004"),
        ("one name twice", _model(enums=[_enum("eD", "uint8_t", ("A", 0), ("A", 1))]),
         "ENUM005"),
        ("one number twice", _model(enums=[_enum("eN", "uint8_t", ("A", 1), ("B", 1))]),
         "ENUM006"),
        ("a number its base cannot hold",
         _model(enums=[_enum("eW", "uint8_t", ("A", 256))]), "ENUM007"),
        ("a value named like another enumeration's",
         _model(enums=[_enum(), _enum("eOther", "uint8_t", ("MODE_A", 5))]), "ENUM008"),
        ("an enumeration nobody declares", _model(_param(enum="eGone")), "ENUM010"),
        ("in a parameter table", _model(_param(), enums=[_enum()]), "ENUM013"),
        ("not of its base type", _model(_param(value_type="uint16_t"), enums=[_enum()]),
         "ENUM014"),
        ("a default that is none of its values", _model(_param(default=1), enums=[_enum()]),
         "ENUM015"),
    ]
    wrong = []
    for title, model, code in cases:
        found = errors(model, table if code == "ENUM013" else smart)
        enum_codes = {item for item in found if item.startswith("ENUM")}
        if (code is None and enum_codes) or (code is not None and code not in found):
            wrong.append(f"{title}: expected {code or 'nothing'}, got {sorted(found) or '-'}")
    true(not wrong, "; ".join(wrong))


# ----------------------------------------------------------- the generated C
_TAGS = """<Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_NONE" />
      </Tags>"""
_LIST = f"""<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator" generatorVersion="1.0.0">
  <SourceFiles />
  <Parameters>
    <Parameter name="FlightMode" kind="primitive" enable="true" userName="FlightMode" type="SETTING"
               valueType="uint8_t" enumType="eFlightMode" size="1">
      <Source /><Limits default="5" />
      {_TAGS}
    </Parameter>
    <Parameter name="Lights" kind="primitive" enable="true" userName="Lights" type="SETTING"
               valueType="int16_t" enumType="eLight" size="3">
      <Source /><Limits default="-1" />
      {_TAGS}
    </Parameter>
    <Parameter name="Mission" kind="struct" enable="true" userName="Mission" type="SETTING"
               valueType="sMission" size="1">
      <Source /><Limits />
      {_TAGS}
    </Parameter>
  </Parameters>
</ParameterListModel>
"""
_TYPES = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListTypes schemaVersion="1.0" generator="parameter_list_code_generator" generatorVersion="1.0.0">
  <StructType name="sMission">
    <Field name="Mode" valueType="uint8_t" enumType="eFlightMode" />
    <Field name="Legs" valueType="uint16_t" />
  </StructType>
  <EnumType name="eFlightMode" baseType="uint8_t">
    <Value name="FLIGHT_MODE_MANUAL" value="0" />
    <Value name="FLIGHT_MODE_STABILIZE" value="1" />
    <Value name="FLIGHT_MODE_HOLD" value="5" />
    <Value name="FLIGHT_MODE_LAND" value="6" />
  </EnumType>
  <EnumType name="eLight" baseType="int16_t">
    <Value name="LIGHT_OFF" value="-1" />
    <Value name="LIGHT_DIM" value="10" />
    <Value name="LIGHT_ON" value="100" />
  </EnumType>
</ParameterListTypes>
"""
_MAIN = r"""
#include <stdio.h>
#include "cg_parameter_list.h"

static int check(int ok, const char *what) {
    if (!ok) printf("FAIL: %s\n", what);
    return ok ? 0 : 1;
}

int main(void) {
    int failed = 0;
    eFlightMode mode = 0U;
    eLight light = 0;

    if (fParameterList_Init() != 0U) { printf("FAIL: init\n"); return 1; }

    /* the typedef is the base type: the smart data functions take it as it is */
    failed += check(fSmartData_U8_Read(&Cg_SmartData_FlightMode, &mode) == eSMART_DATA_OK
                    && mode == FLIGHT_MODE_HOLD, "the default is FLIGHT_MODE_HOLD");
    mode = FLIGHT_MODE_LAND;
    failed += check(fSmartData_U8_Write(&Cg_SmartData_FlightMode, &mode) == eSMART_DATA_OK,
                    "FLIGHT_MODE_LAND is written");
    mode = 3U;                                  /* between STABILIZE (1) and HOLD (5) */
    failed += check(fSmartData_U8_Write(&Cg_SmartData_FlightMode, &mode)
                    == eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE, "3, in the range but no value");
    failed += check(fSmartData_U8_WriteByIndex(FLIGHT_MODE, &mode)
                    == eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE, "3 by index");
    failed += check(fSmartData_U8_SetDefaultValue(&Cg_SmartData_FlightMode, &mode)
                    == eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE, "3 as a default");
    mode = 9U;
    failed += check(fSmartData_U8_Write(&Cg_SmartData_FlightMode, &mode)
                    == eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE, "9, past the last value");
    failed += check(fSmartData_U8_Read(&Cg_SmartData_FlightMode, &mode) == eSMART_DATA_OK
                    && mode == FLIGHT_MODE_LAND, "the value stays FLIGHT_MODE_LAND");
    failed += check(IS_VALID_eFlightMode(5) && !IS_VALID_eFlightMode(2) && IS_VALID_eLight(-1)
                    && !IS_VALID_eLight(0), "IS_VALID checks every value");

    failed += check(fSmartData_I16_Read(&Cg_SmartData_Lights[2], &light) == eSMART_DATA_OK
                    && light == LIGHT_OFF, "every element starts at LIGHT_OFF (-1)");
    light = 50;
    failed += check(fSmartData_I16_Write(&Cg_SmartData_Lights[1], &light)
                    == eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE, "50 on an element");
    light = LIGHT_ON;
    failed += check(fSmartData_I16_Write(&Cg_SmartData_Lights[1], &light) == eSMART_DATA_OK,
                    "LIGHT_ON on an element");
    mode = 4U;
    failed += check(fSmartData_U8_Write(&Cg_SmartData_Mission.Mode, &mode)
                    == eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE, "4 on a field of it");
    {
        uint16_t legs = 7U;
        failed += check(fSmartData_U16_Write(&Cg_SmartData_Mission.Legs, &legs) == eSMART_DATA_OK,
                        "an ordinary field is not touched by any of it");
    }
    return failed;
}
"""


def test_the_generated_code_refuses_other_values(work):
    """Compiled with -Werror and run: every write refuses a number that is no value."""
    (work / "fixture.xml").write_text(_LIST, encoding="utf-8")
    (work / "fixture_types.xml").write_text(_TYPES, encoding="utf-8")
    config = compile_test.write_config(work, {"model_files": [str(work / "fixture.xml")]})
    equal(compile_test.generator_main(["--config", str(config), "--quiet"]), 0, "generated")
    generated = work / "generated"
    header = (generated / "cg_parameter_list_types.h").read_text(encoding="utf-8")
    true("typedef uint8_t eFlightMode;" in header, "the typedef")
    true("((eLight)(-1))" in header, "a negative value, in brackets")
    true("((value_) == FLIGHT_MODE_HOLD)" in header, "IS_VALID names every value")
    source = (generated / "cg_smart_data.c").read_text(encoding="utf-8")
    true("fSmartData_SetIsValid(&Cg_SmartData_FlightMode, fIsValid_eFlightMode)" in source,
         "the object is told which values it may hold")
    true("fSmartData_SetIsValid(&Cg_SmartData_Mission.Legs" not in source,
         "an ordinary field is not")

    if not compile_test.have_compiler(compile_test.C_COMPILER):
        print(f"         {paint('gcc not found - compiled and run: skipped', YELLOW)}")
        return
    stub = work / "stubs"
    stub.mkdir()
    (stub / "chrono.h").write_text(compile_test._CHRONO_STUB_H, encoding="utf-8")
    (work / "main.c").write_text(_MAIN, encoding="utf-8")
    includes = [f"-I{generated}", f"-I{ROOT / 'smart_data'}",
                f"-I{ROOT / 'parameter_descriptor'}", f"-I{stub}"]
    built = subprocess.run(
        [compile_test.C_COMPILER, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         *includes, str(ROOT / "smart_data" / "smart_data.c"),
         str(ROOT / "parameter_descriptor" / "parameter_descriptor.c"),
         str(generated / "cg_smart_data.c"), str(generated / "cg_parameter_list.c"),
         str(work / "main.c"), "-o", str(work / "enum.exe")], capture_output=True, text=True)
    true(built.returncode == 0, f"compiled with -Werror:\n{built.stderr[:3000]}")
    if compile_test.have_compiler(compile_test.CXX_COMPILER):
        cxx = subprocess.run(
            [compile_test.CXX_COMPILER, "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "-fsyntax-only", "-x", "c++", *includes, str(generated / "cg_parameter_list.h")],
            capture_output=True, text=True)
        true(cxx.returncode == 0, f"the headers compile as C++:\n{cxx.stderr[:2000]}")
    run = subprocess.run([str(work / "enum.exe")], capture_output=True, text=True)
    true(run.returncode == 0, f"every check in C held:\n{run.stdout}")


CASES = [
    ("declaring one", test_declaring_one),
    ("bad ones are refused", test_bad_ones_are_refused),
    ("a parameter of one", test_a_parameter_of_one),
    ("editing it reaches every use", test_editing_reaches_every_use),
    ("deleting one", test_deleting_one),
    ("a field of a structure", test_a_field_of_a_structure),
    ("saved and read back", test_saved_and_read_back),
    ("it belongs to its sublist", test_it_belongs_to_its_sublist),
    ("what the validator finds", test_what_the_validator_finds),
    ("the generated code refuses other values", test_the_generated_code_refuses_other_values),
]


def main() -> int:
    setup_logging(quiet=True)
    failures = 0
    with tempfile.TemporaryDirectory(prefix="pl_enum_") as raw:
        # the machine's drop-down lists are never written by a test
        choices.CHOICES_FILE = pathlib.Path(raw) / "choices.json"
        shutil.copy(choices.CHOICES_TEMPLATE, choices.CHOICES_FILE)
        for title, case in CASES:
            work = pathlib.Path(raw) / case.__name__
            work.mkdir()
            try:
                case(work)
            except Failure as error:
                failures += 1
                print(f"  [{paint('FAIL', BOLD + BRIGHT_RED)}] {title}\n         {error}")
                continue
            except Exception:                       # noqa: BLE001
                failures += 1
                print(f"  [{paint('ERROR', BOLD + BRIGHT_RED)}] {title}")
                print("         " + traceback.format_exc().replace("\n", "\n         "))
                continue
            print(f"  [{paint('PASS', GREEN)}] {title}")

    print()
    if failures:
        print(paint(f"{failures} of {len(CASES)} enumeration case(s) FAILED.",
                    BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} enumeration cases passed.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
