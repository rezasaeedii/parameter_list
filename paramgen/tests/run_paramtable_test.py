# -*- coding: utf-8 -*-
"""The ``param_table`` output format: one header of ADD_PARAM() lines.

The point of this format is not only what it generates but what it *refuses*.
The older firmware's table is a flat list of single values, so a structure or
an array is an error here and perfectly fine in a ``smart_data`` project - the
same file, judged by two different sets of rules depending on which project
opened it.  The last case checks both sides of exactly that.

Run it with::

    python tests/run_paramtable_test.py
"""

import pathlib
import re
import shutil
import sys
import tempfile
import traceback

APP = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "src"))

from pl_codegen.app_home import (PROJECT_FILE_NAME, PROJECT_TEMPLATE,  # noqa: E402
                                 copy_lib_into)
from pl_codegen.choices import default_choices                       # noqa: E402
from pl_codegen.codegen.files.param_table_h import system_of         # noqa: E402
from pl_codegen.config import Config                                 # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,       # noqa: E402
                                      colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils                    # noqa: E402
from pl_gui.api import Api                                           # noqa: E402
from pl_gui.document import Document                                 # noqa: E402
from pl_gui.workspace import Workspace                               # noqa: E402

_logging_utils._colour_enabled = colour_supported()


class Failure(AssertionError):
    """One case did not hold."""


def equal(got, want, what):
    if got != want:
        raise Failure(f"{what}: expected {want!r}, got {got!r}")


def true(value, what):
    if not value:
        raise Failure(what)


EMPTY_LIST = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Parameters />
</ParameterListModel>
"""


# --------------------------------------------------------------- the fixture
def new_project(work, name="agreement", lists=("sys_gs_manager_paramTable",),
                output_format="param_table", code_directory=""):
    """A project of the given format, with one empty list per name."""
    root = work / name
    (root / "parameter_lists").mkdir(parents=True, exist_ok=True)
    for item in lists:
        (root / "parameter_lists" / f"{item}.xml").write_text(EMPTY_LIST, encoding="utf-8")
    copy_lib_into(root / "lib")

    settings = PROJECT_TEMPLATE.read_text(encoding="utf-8").replace("{{NAME}}", name)
    settings = settings.replace(
        '"model_files": [],',
        '"model_files": [' + ", ".join(f'"{i}.xml"' for i in lists) + '],')
    settings = settings.replace(
        '"code_directory": "cg_parameter_list",',
        f'"format": "{output_format}",\n    "code_directory": "{code_directory}",')
    settings = settings.replace('"emit_timestamp": true,', '"emit_timestamp": false,')
    (root / PROJECT_FILE_NAME).write_text(settings, encoding="utf-8")

    document = Document(Config.load(root / PROJECT_FILE_NAME))
    document.load()
    # a settings file of its own: the app's is the user's recent list
    workspace = Workspace(work / f"{name}_settings.json")
    workspace.adopt(document)
    return document, Api(workspace), root


def add(api, document, name, **changes):
    """One parameter, filled in the way the editor fills one in."""
    api.add({"parent": "", "kind": "primitive"})
    fields = {"name": name, "user_name": name, "param_type": "SETTING",
              "value_type_name": "uint8_t", "default_value": 0, "minimum": 0,
              "maximum": 10, "resolution": 1,
              "tags": {"SystemName": "SYS_GS_MANAGER", "ResetProof": False,
                       "Loggable": False, "LogEncryption": False,
                       "ParamMode": "PARAM_MODE_USER"}}
    tags = changes.pop("tags", None)
    fields.update(changes)
    if tags:
        fields["tags"] = {**fields["tags"], **tags}
    document.update("NewParameter", fields)
    return name


def squeeze(line):
    """A row with its column padding taken out, for checks about content.

    The padding goes BEFORE the comma - that is what puts every comma of the
    file in the same place - so taking it out means both sides of one.
    """
    return re.sub(r",\s+", ", ", re.sub(r"\s+,", ",", line))


def codes(document, severity="error"):
    return [item["code"] for item in document.validate()
            if item["severity"] == severity]



#: Six rows of the hand-written file this format exists to replace,
#: copied out of it as they are written there.  The list below is those
#: same six parameters as XML; the table after it is what every column
#: of every row has to come back as.
REBUILT_LIST = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator" generatorVersion="1.0.0">
  <SourceFiles />
  <Parameters>
    <Parameter name="PR_GSM_TABLE_NUM" kind="primitive" enable="true"
               gsName="GSM_TABLE_NUM" type="SETTING"
               valueType="uint8_t" arraySize="1" address="400">
      <Source />
      <Limits default="31" minimum="0"
              maximum="255" resolution="1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_READ_ONLY" />
        <Tag id="Tag1" kind="free" value="7" />
      </Tags>
      <Description>GSM_TABLE_NUM returns last parameter number</Description>
    </Parameter>
    <Parameter name="PR_GSM_SERIAL_BAUD_RATE" kind="primitive" enable="true"
               gsName="SERIAL_BAUD_RATE" type="SETTING"
               valueType="int32_t" arraySize="1">
      <Source />
      <Limits default="115200" minimum="57600"
              maximum="921600" resolution="1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_FACTORY" />
        <Tag id="Tag1" kind="free" value="0" />
      </Tags>
      <Description>SERIAL_BAUD_RATE specifies the Ground station baud rate. Allowed baudartes: 57600, 115200, 230400, 460800, 921600</Description>
    </Parameter>
    <Parameter name="PR_GSM_INITIAL_LOCK_SIZE" kind="primitive" enable="true"
               gsName="INITIAL_LOCK_SIZE" type="SETTING"
               valueType="float32_t" arraySize="1">
      <Source />
      <Limits default="0.04" minimum="0.01"
              maximum="0.3" resolution="0.01" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
        <Tag id="Tag1" kind="free" value="0" />
      </Tags>
      <Description>Lock Box Size Parameter</Description>
    </Parameter>
    <Parameter name="PR_GSM_ALT_HOME" kind="primitive" enable="true"
               gsName="MOVING_HOME_ALT (Depr.)" type="SETTING"
               valueType="float32_t" arraySize="1">
      <Source />
      <Limits default="70.0" minimum="-1000.0"
              maximum="10000.0" resolution="1.0" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_READ_ONLY" />
        <Tag id="Tag1" kind="free" value="0" />
      </Tags>
      <Description>Deprecated</Description>
    </Parameter>
    <Parameter name="PR_GSM_GPS_CHAN" kind="primitive" enable="true"
               gsName="GPS Chan selection" type="SETTING"
               valueType="int8_t" arraySize="1">
      <Source />
      <Limits default="2" minimum="0"
              maximum="2" resolution="1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
        <Tag id="Tag1" kind="free" value="0" />
      </Tags>
      <Description>-1: UNKNOWN
0: GS_Link_GPS
1: InnerGS_GPS
2: Auto_Selection</Description>
    </Parameter>
    <Parameter name="PR_GSM_VIRTUAL_CORRUPTION" kind="primitive" enable="true"
               gsName="Virtual Corruption" type="SETTING"
               valueType="uint64_t" arraySize="1">
      <Source />
      <Limits default="0" minimum="0"
              maximum="0" resolution="1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_FACTORY" />
        <Tag id="Tag1" kind="free" value="0" />
      </Tags>
      <Description>NO_VC:0
LOW_FREQUENCY:1
STICK_CALIBRATION:2
NO_DATA_TRANSMIT:4
WD_RESET:8
SW_RESET:16
MULTIPLE_RESET:32
FIRST_BOOT:64
CENTER_THROTTLE:128
BOOTLOADER_INCORRECT:256
NO_DATA_RECEIVE:512
BATTERY_VOLTAGE:1024
GS_GPS:2048
GOHOME:4096</Description>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""

#: data type, TYPE_ENUM, PR_NAME, "gs name", SYS_NAME, index, default,
#: min, max, resolution, mode, address, "description"
REBUILT_ROWS = [
    ['uint8_t', 'TYPE_UINT8', 'PR_GSM_TABLE_NUM', '"GSM_TABLE_NUM"', 'SYS_GS_MANAGER', '0', '31', '0', '255', '1', 'PARAM_MODE_READ_ONLY', '400', '"GSM_TABLE_NUM returns last parameter number"'],
    ['int32_t', 'TYPE_INT32', 'PR_GSM_SERIAL_BAUD_RATE', '"SERIAL_BAUD_RATE"', 'SYS_GS_MANAGER', '1', '115200', '57600', '921600', '1', 'PARAM_MODE_FACTORY', '0', '"SERIAL_BAUD_RATE specifies the Ground station baud rate. Allowed baudartes: 57600, 115200, 230400, 460800, 921600"'],
    ['float', 'TYPE_FLOAT', 'PR_GSM_INITIAL_LOCK_SIZE', '"INITIAL_LOCK_SIZE"', 'SYS_GS_MANAGER', '2', '0.04', '0.01', '0.3', '0.01', 'PARAM_MODE_USER', '0', '"Lock Box Size Parameter"'],
    ['float', 'TYPE_FLOAT', 'PR_GSM_ALT_HOME', '"MOVING_HOME_ALT (Depr.)"', 'SYS_GS_MANAGER', '3', '70.0', '-1000.0', '10000.0', '1.0', 'PARAM_MODE_READ_ONLY', '0', '"Deprecated"'],
    ['int8_t', 'TYPE_INT8', 'PR_GSM_GPS_CHAN', '"GPS Chan selection"', 'SYS_GS_MANAGER', '4', '2', '0', '2', '1', 'PARAM_MODE_USER', '0', '"-1: UNKNOWN\\n0: GS_Link_GPS\\n1: InnerGS_GPS\\n2: Auto_Selection"'],
    ['uint64_t', 'TYPE_UINT64', 'PR_GSM_VIRTUAL_CORRUPTION', '"Virtual Corruption"', 'SYS_GS_MANAGER', '5', '0', '0', '0', '1', 'PARAM_MODE_FACTORY', '0', '"NO_VC:0\\nLOW_FREQUENCY:1\\nSTICK_CALIBRATION:2\\nNO_DATA_TRANSMIT:4\\nWD_RESET:8\\nSW_RESET:16\\nMULTIPLE_RESET:32\\nFIRST_BOOT:64\\nCENTER_THROTTLE:128\\nBOOTLOADER_INCORRECT:256\\nNO_DATA_RECEIVE:512\\nBATTERY_VOLTAGE:1024\\nGS_GPS:2048\\nGOHOME:4096"'],
]

# --------------------------------------------------------------- the cases
def test_one_file_per_project(work):
    """Two lists, one header, one #if block each, indices restarting at 0."""
    document, api, root = new_project(
        work, lists=("sys_gs_manager_paramTable", "sys_rhs_paramTable"))

    document.load(root / "parameter_lists" / "sys_gs_manager_paramTable.xml")
    add(api, document, "PR_GSM_A")
    add(api, document, "PR_GSM_B")
    document.save()

    document.load(root / "parameter_lists" / "sys_rhs_paramTable.xml")
    add(api, document, "PR_RHS_A")
    document.save()

    result = document.generate()
    true(result["success"], f"the build failed: {result.get('message')}")
    equal([pathlib.Path(f).name for f in result["files"]],
          ["nsrParamTables.h", "nsrParamOffsets.h", "nsrSystemNames.h"], "the files written")

    text = (root / "nsrParamTables.h").read_text(encoding="utf-8")
    # The banner names both lists from the project's folder, never with this
    # machine's folders - those changed the file on every machine that built it.
    true("Input file(s)  : parameter_lists/sys_gs_manager_paramTable.xml" in text
         and " parameter_lists/sys_rhs_paramTable.xml\n" in text,
         f"the lists are named from the project's folder: {text[:700]}")
    true(str(root) not in text and str(root.resolve()) not in text,
         "and not with this machine's folders")
    true("#if DESIRED_SUB_SYSTEM == SYS_GS_MANAGER || DESIRED_SUB_SYSTEM == SYS_ALL" in text,
         "the SYS_GS_MANAGER block")
    true("#if DESIRED_SUB_SYSTEM == SYS_RHS || DESIRED_SUB_SYSTEM == SYS_ALL" in text,
         "the SYS_RHS block")
    equal(text.count("#endif"), 2, "one #endif per block")

    rows = [line for line in text.splitlines() if line.startswith("ADD_PARAM(")]
    equal(len(rows), 3, "one row per parameter")
    # the index column is the sixth, and restarts inside each block
    indices = [row.split(",")[5].strip() for row in rows]
    equal(indices, ["0", "1", "0"], "the index restarts for each sub-system")


def test_the_columns(work):
    """Every column comes from where the format says it does."""
    document, api, root = new_project(work)
    add(api, document, "PR_A", value_type_name="float32_t", default_value=0.04,
        minimum=0.01, maximum=0.3, resolution=0.01,
        description="Lock Box Size Parameter",
        address=400, tags={"ParamMode": "PARAM_MODE_READ_ONLY", "Tag1": 7})
    add(api, document, "PR_B", user_name="Shown to the user",
        value_type_name="float64_t", default_value=1.5, minimum=0, maximum=10,
        resolution=0.001)
    document.save()
    true(document.generate()["success"], "the build")

    lines = [line for line in
             (root / "nsrParamTables.h").read_text(encoding="utf-8").splitlines()
             if line.startswith("ADD_PARAM(")]
    # The columns are padded to a common width, so the checks below look at the
    # row with its padding squeezed out; the padding itself is checked further
    # down, where it is the thing being tested rather than noise.
    first, second = (squeeze(row[len("ADD_PARAM("):-1]) for row in lines)

    true(first.startswith("float,"), f"float32_t is written 'float': {first[:40]}")
    true("TYPE_FLOAT," in first, "float32_t gets TYPE_FLOAT")
    true(second.startswith("double,"), f"float64_t is written 'double': {second[:40]}")
    true("TYPE_DOUBLE," in second, "float64_t gets TYPE_DOUBLE")

    true("PR_A," in first, "the name is written as typed, with no prefix added")
    true('"Shown to the user"' in second, "the user name is the quoted column")
    true("SYS_GS_MANAGER," in first, "the system comes from the file name")
    true("0.04, 0.01, 0.3, 0.01," in first, f"plain numbers, no suffixes: {first}")
    true("PARAM_MODE_READ_ONLY, 400," in first,
         "the Address field is the address column - not Tag1, which says 7")
    true("PARAM_MODE_USER, 0," in second, "an Address never set is 0")
    true('"Lock Box Size Parameter"' in first, "the description is the last column")

    # ...and the padding: every comma of the file stands under the comma above
    # it, which is what makes a table of three hundred rows readable down a
    # column.  The description is last, so it is not padded.
    places = [[index for index, char in enumerate(line) if char == ","]
              for line in lines]
    equal(places[1][:12], places[0][:12],
          "every comma but the last stands in the same column on every row")


def test_the_modes_come_from_the_machine(work):
    """The #define block is the machine's PARAM MODES list, numbered from 0."""
    document, api, root = new_project(work)
    add(api, document, "PR_A")
    document.save()
    document.generate()

    text = (root / "nsrParamTables.h").read_text(encoding="utf-8")
    for index, name in enumerate(document.model.defines.get("PARAM MODES")):
        true(f"#define {name}" in text, f"{name} is defined")
        line = next(l for l in text.splitlines() if l.startswith(f"#define {name} "))
        equal(line.split("(")[1].rstrip(")"), str(index), f"{name} is {index}")


def a_structure_in(api, document, name="Home"):
    """Build a structure the ordinary way; only a smart_data project may."""
    api.new_type({"name": "Position"})
    api.update_type({"name": "Position", "changes": {"fields": [
        {"name": "Lat", "valueType": "float64_t", "arraySize": 1}]}})
    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": name, "param_type": "SETTING", "log_id": 5,
                                  "tags": {"SystemName": "SYS_GS_MANAGER",
                                           "ResetProof": False, "Loggable": False,
                                           "LogEncryption": False,
                                           "ParamMode": "PARAM_MODE_USER"}})
    api.use_type({"path": name, "name": "Position"})
    document.update(f"{name}.Lat", {"minimum": -90, "maximum": 90,
                                    "default_value": 0, "resolution": 1e-7})
    return name


def hand_over(source_root, target_root, stem="sys_gs_manager_paramTable"):
    """Copy a list and its structures from one project to another."""
    for name in (f"{stem}.xml", f"{stem}_types.xml"):
        source = source_root / "parameter_lists" / name
        if source.is_file():
            shutil.copy2(source, target_root / "parameter_lists" / name)


def test_the_editor_will_not_build_one(work):
    """The guard rails: the editor refuses to make what the format cannot hold."""
    document, api, root = new_project(work)

    answer = api.add({"parent": "", "kind": "struct"})
    equal(answer["ok"], False, "adding a structure is refused")
    true("parameter table" in answer["message"], f"and says why: {answer['message']}")

    add(api, document, "PR_A")
    answer = api.update({"path": "PR_A", "changes": {"array_size": 4}})
    equal(answer["ok"], False, "an array size above 1 is refused")
    true("one value" in answer["message"], f"and says why: {answer['message']}")


def test_a_structure_that_arrived_from_elsewhere(work):
    """A list written by a smart_data project, opened by a param_table one.

    The guard rails stop you *building* a structure here; they cannot stop one
    arriving in a file, which is exactly what happens when a list is shared
    between two projects.  That is what the rule is for.
    """
    modern, modern_api, modern_root = new_project(
        work, name="modern", output_format="smart_data",
        code_directory="cg_parameter_list")
    a_structure_in(modern_api, modern)
    modern.save()

    old, _api, old_root = new_project(work, name="old")
    hand_over(modern_root, old_root)
    old.load(old_root / "parameter_lists" / "sys_gs_manager_paramTable.xml")

    true("PTB001" in codes(old), f"the structure is an error here: {codes(old)}")
    equal(old.generate()["success"], False, "and the build is refused")


def test_an_array_that_arrived_from_elsewhere(work):
    """Same, for an array: one value per row, so four values have nowhere to go."""
    modern, modern_api, modern_root = new_project(
        work, name="modern", output_format="smart_data",
        code_directory="cg_parameter_list")
    add(modern_api, modern, "PR_A", array_size=4, log_id=10)
    modern.save()

    old, _api, old_root = new_project(work, name="old")
    hand_over(modern_root, old_root)
    old.load(old_root / "parameter_lists" / "sys_gs_manager_paramTable.xml")

    true("PTB002" in codes(old), f"an array is an error here: {codes(old)}")
    equal(old.generate()["success"], False, "and the build is refused")


def test_a_boolean_is_refused(work):
    """The table's type enum has no boolean."""
    document, api, root = new_project(work)
    add(api, document, "PR_A", value_type_name="bool_t")
    true("PTB006" in codes(document), f"bool_t is an error: {codes(document)}")


def test_the_ignored_tags_say_nothing(work):
    """Reset proof and the logging tags are set freely here, in silence.

    They have no column in ADD_PARAM, and this format neither stores nor logs -
    but the list is shared, and the smart-data project built from the same file
    uses them for real.  Saying so on every build was noise nobody could act
    on, so the three warnings were taken out.  (Reported.)

    A TRUE is set in this project in the next case; here it arrives in a list
    shared with a project that DOES generate smart data.
    """
    other, other_api, other_root = new_project(work, name="smart",
                                               output_format="smart_data")
    add(other_api, other, "PR_A", log_id=10,
        tags={"ResetProof": True, "Loggable": True})
    add(other_api, other, "PR_B", tags={"LogEncryption": True})
    other.save()

    document, api, root = new_project(work)
    hand_over(other_root, root)
    document.load()

    warnings = codes(document, "warning")
    for code in ("PTB007", "PTB003", "PTB004"):
        true(code not in warnings, f"{code} says nothing any more: {warnings}")
    equal(codes(document), [], "and none of them is an error either")
    true(document.generate()["success"], "so the build goes through, quietly")


def test_the_editor_sets_them_but_not_the_sub_system(work):
    """Reset proof, the logging tags and LogID are the form's; the sub-system is not.

    They used to be read-only here too.  They have no column in ADD_PARAM, but
    the list is shared with projects that do use them, so they are set here
    like any tag, and nothing is said about them.  Tag System Name stays the
    file's: a form that sends none keeps it.  (Reported.)
    """
    document, api, root = new_project(work)
    add(api, document, "PR_A")

    # what the form of a parameter-table project sends now: the three tags and
    # the log id - and still no Tag System Name
    answer = api.update({"path": "PR_A", "changes": {
        "log_id": 7,
        "tags": {"ResetProof": True, "Loggable": True, "LogEncryption": True,
                 "ParamMode": "PARAM_MODE_USER"}}})
    equal(answer["ok"], True, f"the edit is taken: {answer.get('message')}")
    node = document.model.parameters[0]
    equal((node.tags.get("ResetProof"), node.tags.get("Loggable"),
           node.tags.get("LogEncryption")), (True, True, True),
          "reset proof and both logging tags are set here")
    equal(node.log_id, 7, "and so is the log id")
    equal(node.tags.get("SystemName"), "SYS_GS_MANAGER",
          "while the sub-system, which the form does not send, stays the file's")

    warnings = codes(document, "warning")
    for code in ("PTB007", "PTB003", "PTB004"):
        true(code not in warnings, f"{code} does not warn about a tag it set: {warnings}")
    true(document.generate()["success"], "and the build still goes through")

    api.update({"path": "PR_A", "changes": {"tags": {
        "ResetProof": False, "Loggable": False, "LogEncryption": False,
        "ParamMode": "PARAM_MODE_USER"}}})
    node = document.model.parameters[0]
    equal((node.tags.get("ResetProof"), node.tags.get("Loggable"),
           node.tags.get("LogEncryption")), (False, False, False),
          "and switched off here again")


def test_the_file_name_names_the_system(work):
    """Case never matters, and an unknown name is refused by name."""
    equal(system_of(pathlib.Path("sys_gs_manager_paramTable.xml")), "SYS_GS_MANAGER",
          "lower case with a camel suffix")
    equal(system_of(pathlib.Path("SYS_GS_MANAGER_PARAMTABLE.xml")), "SYS_GS_MANAGER",
          "all upper case")
    equal(system_of(pathlib.Path("Sys_Gs_Manager_ParamTable.xml")), "SYS_GS_MANAGER",
          "mixed case")

    document, api, root = new_project(work, lists=("nothing_like_a_system",))
    add(api, document, "PR_A")
    found = codes(document)
    true("PTB005" in found, f"an unnamed system is an error: {found}")

    message = next(item["message"] for item in document.validate()
                   if item["code"] == "PTB005")
    true("nothing_like_a_system.xml" in message,
         f"the message names the file: {message}")


def test_the_output_lands_where_it_is_told(work):
    """An empty code_directory is the project's own folder."""
    document, api, root = new_project(work, code_directory="")
    add(api, document, "PR_A")
    document.save()
    document.generate()
    true((root / "nsrParamTables.h").is_file(), "an empty code_directory is the root")

    other, api2, root2 = new_project(work, name="elsewhere", code_directory="out/here")
    add(api2, other, "PR_A")
    other.save()
    other.generate()
    true((root2 / "out" / "here" / "nsrParamTables.h").is_file(),
         "a code_directory is honoured")


def test_the_same_list_in_both_formats(work):
    """The asymmetry, from both sides.

    One file, two projects.  In the smart_data one it builds; in the
    param_table one the same bytes are an error.  Nothing about the file
    changed - the project reading it did.
    """
    modern, modern_api, modern_root = new_project(
        work, name="modern", output_format="smart_data",
        code_directory="cg_parameter_list")
    a_structure_in(modern_api, modern)
    modern.save()

    found = codes(modern)
    equal([code for code in found if code.startswith("PTB")], [],
          f"no param-table rule fires in a smart_data project: {found}")
    true(modern.generate()["success"],
         f"and it builds there: {modern.generate().get('message')}")

    old, _api, old_root = new_project(work, name="old")
    hand_over(modern_root, old_root)
    old.load(old_root / "parameter_lists" / "sys_gs_manager_paramTable.xml")

    true("PTB001" in codes(old),
         f"the same file is an error in param_table: {codes(old)}")


def cells_of(line: str):
    """The thirteen arguments of one ADD_PARAM line, quotes respected.

    A description holds commas of its own, so the split has to know where a
    string literal starts and ends - which is the whole reason this is not a
    call to ``str.split``.
    """
    inside = line[line.index("(") + 1:line.rindex(")")]
    out, quoted, cell, index = [], False, "", 0
    while index < len(inside):
        char = inside[index]
        if quoted:
            cell += char
            if char == "\\" and index + 1 < len(inside):
                cell += inside[index + 1]
                index += 2
                continue
            if char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            cell += char
        elif char == ",":
            out.append(cell.strip())
            cell = ""
        else:
            cell += char
        index += 1
    out.append(cell.strip())
    return out


def test_the_file_it_replaces(work):
    """Six real rows of the hand-written file, rebuilt from a list.

    This is the claim the whole format rests on: that what the tool writes can
    take the place of the file somebody maintains by hand.  So the fixture is
    not invented - it is six rows lifted out of that file, and every one of the
    thirteen columns has to come back exactly as it was written there.
    """
    document, api, root = new_project(work)
    (root / "parameter_lists" / "sys_gs_manager_paramTable.xml").write_text(
        REBUILT_LIST, encoding="utf-8")
    document.load()
    equal(codes(document), [], "the rows of the real file are accepted")
    true(document.generate()["success"], "the build")

    rows = [cells_of(line) for line in
            (root / "nsrParamTables.h").read_text(encoding="utf-8").splitlines()
            if line.startswith("ADD_PARAM(")]
    equal(len(rows), len(REBUILT_ROWS), "one row per parameter")

    names = ["data type", "TYPE_ENUM", "PR_NAME", "gs name", "SYS_NAME",
             "index", "default", "min", "max", "resolution", "mode",
             "address", "description"]
    for number, (want, got) in enumerate(zip(REBUILT_ROWS, rows)):
        for column, (left, right) in enumerate(zip(want, got)):
            equal(right, left,
                  f"row {number} ({want[2]}), the {names[column]} column")




def test_reordering_the_lists_moves_nothing(work):
    """Swapping two lists round changes the file and nothing in it.

    The blocks change places, but a parameter's number is its number INSIDE its
    own sub-system, and none of those moved.  Saying "17 offsets MOVED" at that
    point - which is what comparing global positions used to say - is a warning
    about a danger that is not there, and a warning nobody can act on is a
    warning people learn to ignore.
    """
    document, api, root = new_project(
        work, lists=("sys_gs_manager_paramTable", "sys_rhs_paramTable"))
    add(api, document, "PR_A")
    add(api, document, "PR_B")
    document.save()

    document.load(root / "parameter_lists" / "sys_rhs_paramTable.xml")
    add(api, document, "PR_C", tags={"SystemName": "SYS_RHS"})
    document.save()
    true(document.generate()["success"], "the first build")

    order = [str(p) for p in document.config.inputs.model_files]
    document.select_lists(list(reversed(order)))
    result = document.generate()
    true(result["success"], "the build after the swap")

    blocks = [line for line in
              (root / "nsrParamTables.h").read_text(encoding="utf-8").splitlines()
              if line.startswith("#if ")]
    true("SYS_RHS" in blocks[0], f"the swap reached the file: {blocks}")

    drift = result["drift"]
    true(drift["table"], "the drift check knows which format this is")
    equal(drift["reindexed"], [], "no parameter changed its number")
    equal(drift["moved"], [], "and there are no byte offsets in this format")
    true(not drift["breaksStoredData"], f"so nothing is broken: {drift['summary']}")


def indices_shown(api, merged=False):
    """``name -> the index the editor shows beside it``."""
    state = api.state({"allLists": True} if merged else {})
    return {node["name"]: [value["index"] for value in node["values"]]
            for node in state["tree"]}


def test_a_sublist_counts_from_zero(work):
    """One sublist on its own is numbered the way ADD_PARAM numbers it.

    nsrParamTables.h restarts the index in every block, so the second list's
    first parameter is 0 there.  The editor showed its place in the whole
    build instead - 2 - which is a number the generated file never writes.
    The merged view still counts the whole build, and smart data, whose
    descriptor table is one table, counts the whole build everywhere.
    """
    document, api, root = new_project(
        work, lists=("sys_gs_manager_paramTable", "sys_rhs_paramTable"))
    add(api, document, "PR_A")
    add(api, document, "PR_B")
    document.save()
    document.load(root / "parameter_lists" / "sys_rhs_paramTable.xml")
    add(api, document, "PR_C", tags={"SystemName": "SYS_RHS"})
    add(api, document, "PR_D", tags={"SystemName": "SYS_RHS"})
    document.save()

    equal(indices_shown(api), {"PR_C": [0], "PR_D": [1]},
          "the open sublist counts from zero")
    equal(indices_shown(api, merged=True),
          {"PR_A": [0], "PR_B": [1], "PR_C": [2], "PR_D": [3]},
          "every sublist, merged, counts the whole build")

    true(document.generate()["success"], "the build")
    written = {cells[2]: int(cells[5]) for cells in
               (cells_of(line) for line in
                (root / "nsrParamTables.h").read_text(encoding="utf-8").splitlines()
                if line.startswith("ADD_PARAM("))}
    for name, shown in indices_shown(api).items():
        equal(shown, [written[name]], f"{name}: the editor shows what ADD_PARAM writes")

    modern, modern_api, modern_root = new_project(
        work, name="modern", lists=("first", "second"),
        output_format="smart_data", code_directory="cg_parameter_list")
    add(modern_api, modern, "PR_A")
    add(modern_api, modern, "PR_B")
    modern.save()
    modern.load(modern_root / "parameter_lists" / "second.xml")
    add(modern_api, modern, "PR_C")
    modern.save()
    equal(indices_shown(modern_api), {"PR_C": [2]},
          "smart data counts the whole build")


def every_value_shown(api, merged=False):
    """``(index, element name)`` of every value the editor shows, by index."""
    found = []

    def walk(node):
        found.extend((value["index"], value["name"]) for value in node["values"])
        for child in node.get("children") or []:
            walk(child)

    for node in api.state({"allLists": True} if merged else {})["tree"]:
        walk(node)
    return sorted(found)


def test_the_same_name_in_two_sublists(work):
    """A name is unique in one sublist only, and each keeps its own index.

    Two lists whose parameters keep the names the editor gives them - both
    have a 'NewParameter' - and the values were looked up by name.  So the
    second list's 'NewParameter' was shown the first one's index: in the
    merged view, and in smart data in its own list too, which looked exactly
    like every sublist counting from zero.

    The first list holds an array and an array of structures as well, whose
    values are not one run, and every number shown has to be the one the
    generator's flatten() gives that value - once each, nothing twice.
    """
    modern, api, root = new_project(
        work, name="modern", lists=("first", "second"),
        output_format="smart_data", code_directory="cg_parameter_list")
    api.new_type({"name": "Wheel"})
    api.update_type({"name": "Wheel", "changes": {"fields": [
        {"name": "Speed", "valueType": "float32_t", "arraySize": 1},
        {"name": "Grip", "valueType": "uint8_t", "arraySize": 1}]}})
    api.add({"parent": "", "kind": "struct"})
    api.update({"path": "NewStruct", "changes": {"array_size": 2}})
    api.use_type({"path": "NewStruct", "name": "Wheel"})
    api.add({"parent": "", "kind": "primitive"})
    api.add({"parent": "", "kind": "primitive"})
    api.update({"path": "NewParameter", "changes": {"array_size": 3}})
    modern.save()
    modern.load(root / "parameter_lists" / "second.xml")
    api.add({"parent": "", "kind": "primitive"})
    api.add({"parent": "", "kind": "primitive"})
    modern.save()

    build = [(index, leaf.name)
             for index, leaf in enumerate(modern.merged_model().flatten())]
    equal([name for _index, name in build].count("NewParameter2"), 2,
          "the fixture: both lists have a NewParameter2")
    equal(every_value_shown(api, merged=True), build,
          "every sublist, merged: each value its own index, from the whole build")
    first_count = len(build) - 2
    equal(every_value_shown(api), build[first_count:],
          "smart data, the second list alone: the whole build's numbers")

    table, table_api, table_root = new_project(
        work, lists=("sys_gs_manager_paramTable", "sys_rhs_paramTable"))
    for stem in ("sys_gs_manager_paramTable", "sys_rhs_paramTable"):
        table.load(table_root / "parameter_lists" / f"{stem}.xml")
        table_api.add({"parent": "", "kind": "primitive"})
        table_api.add({"parent": "", "kind": "primitive"})
        table.save()
    equal(every_value_shown(table_api),
          [(0, "NewParameter"), (1, "NewParameter2")],
          "parameter table, the second list alone: from zero")
    equal(every_value_shown(table_api, merged=True),
          [(0, "NewParameter"), (1, "NewParameter2"),
           (2, "NewParameter"), (3, "NewParameter2")],
          "parameter table, merged: the whole build")


def test_a_new_row_in_the_middle_is_the_one_that_warns(work):
    """The danger this format DOES have: a number that moved."""
    document, api, root = new_project(work)
    add(api, document, "PR_A")
    add(api, document, "PR_B")
    document.save()
    document.generate()

    add(api, document, "PR_MIDDLE")
    document.move("PR_MIDDLE", -1)
    document.save()
    result = document.generate()

    drift = result["drift"]
    moved = {item["parameter"]: (item["old"], item["new"])
             for item in drift["reindexed"]}
    equal(moved.get("PR_B"), (1, 2), "the row after the new one is renumbered")
    true(drift["breaksStoredData"],
         "and that is what a ground station would read wrongly")
    true(any("number" in line for line in drift["report"]),
         f"the report says what moved: {drift['report'][:2]}")


def test_an_abandoned_copy_is_reported(work):
    """The output folder changed, and the old file is still sitting there.

    Nothing writes to it any more, and nothing about it says so: every change
    made afterwards "does not appear in the file" for whoever keeps opening the
    old one.  One walk of the project folder answers that question before it is
    asked.
    """
    document, api, root = new_project(work, code_directory="out")
    add(api, document, "PR_A")
    document.save()
    true(document.generate()["success"], "the first build")
    true((root / "out" / "nsrParamTables.h").is_file(), "it went to out/")

    settings = root / PROJECT_FILE_NAME
    settings.write_text(
        settings.read_text(encoding="utf-8")
                .replace('"code_directory": "out"', '"code_directory": "elsewhere"'),
        encoding="utf-8")

    result = document.generate()
    true(result["success"], "the build after the move")
    true((root / "elsewhere" / "nsrParamTables.h").is_file(), "it goes there now")

    warnings = [item for item in result["diagnostics"] if item["code"] == "OUT001"]
    equal(sorted(pathlib.Path(w["location"]["file"]).name for w in warnings),
          ["nsrParamOffsets.h", "nsrParamTables.h", "nsrSystemNames.h"],
          f"every abandoned file is reported: "
          f"{[i['code'] for i in result['diagnostics']]}")
    true(all("out" in w["message"] for w in warnings), "and named")
    true(all("code_directory" in (w["hint"] or "") for w in warnings),
         "with the reason")




def offset_rows(root):
    """The (index, offset, size, type, name) rows of the note, per sub-system."""
    blocks = {}
    system = None
    for line in (root / "nsrParamOffsets.h").read_text(encoding="utf-8").splitlines():
        if line.startswith("/* ---- "):
            system = line.split()[2]
            blocks[system] = []
            continue
        cells = line.split()
        if system and len(cells) == 5 and cells[0].isdigit():
            blocks[system].append(tuple(cells))
    return blocks


def test_the_offsets_note(work):
    """Beside the table, a comment saying where each value sits.

    The firmware lays a sub-system's values out one after another, so the third
    parameter's offset is the sum of the sizes above it.  The table cannot show
    that and the note is nothing but comments, so it costs the build nothing.
    """
    document, api, root = new_project(
        work, lists=("sys_gs_manager_paramTable", "sys_rhs_paramTable"))
    add(api, document, "PR_A", value_type_name="uint8_t")
    add(api, document, "PR_B", value_type_name="int16_t")
    add(api, document, "PR_C", value_type_name="float64_t")
    document.save()

    document.load(root / "parameter_lists" / "sys_rhs_paramTable.xml")
    add(api, document, "PR_RHS", value_type_name="uint32_t",
        tags={"SystemName": "SYS_RHS"})
    document.save()
    true(document.generate()["success"], "the build")

    blocks = offset_rows(root)
    equal(blocks["SYS_GS_MANAGER"],
          [("0", "0", "1", "uint8_t", "PR_A"),
           ("1", "1", "2", "int16_t", "PR_B"),
           ("2", "3", "8", "double", "PR_C")],
          "the offset is the running total of the sizes above it")
    equal(blocks["SYS_RHS"], [("0", "0", "4", "uint32_t", "PR_RHS")],
          "and every sub-system starts again at zero")

    text = (root / "nsrParamOffsets.h").read_text(encoding="utf-8")
    true("11 byte(s) in total" in text, f"the total of the block: {text[-400:]}")
    # every line of it is inside a comment: it has to add nothing to a build
    body = text.split("*/", 1)[1]
    true("ADD_PARAM" not in body, "the note holds no code")


def test_a_disabled_parameter_takes_nothing(work):
    """Switching one off moves the index AND the offset of the ones after it."""
    document, api, root = new_project(work)
    add(api, document, "PR_A", value_type_name="uint32_t")
    add(api, document, "PR_B", value_type_name="uint8_t")
    add(api, document, "PR_C", value_type_name="uint8_t")
    document.save()
    true(document.generate()["success"], "the first build")
    equal(offset_rows(root)["SYS_GS_MANAGER"],
          [("0", "0", "4", "uint32_t", "PR_A"),
           ("1", "4", "1", "uint8_t", "PR_B"),
           ("2", "5", "1", "uint8_t", "PR_C")],
          "all three are in")

    document.update("PR_A", {"enable": False})
    document.save()
    true(document.generate()["success"], "the build after disabling one")

    equal(offset_rows(root)["SYS_GS_MANAGER"],
          [("0", "0", "1", "uint8_t", "PR_B"),
           ("1", "1", "1", "uint8_t", "PR_C")],
          "the disabled one takes no index and no byte")
    rows = [line for line in
            (root / "nsrParamTables.h").read_text(encoding="utf-8").splitlines()
            if line.startswith("ADD_PARAM(")]
    equal(len(rows), 2, "and it is not in the table either")


def test_a_new_project_gets_no_library(work):
    """A new project is the lists and nothing else - no lib/ in either format.

    The C library the smart-data output plugs into belongs to the FIRMWARE:
    where it sits in a firmware tree, and which version that tree is on, is not
    this tool's business.  Copying one in only produced a folder to delete, so
    the reference copy stays in the app and is taken by hand.  (Asked for.)
    """
    from pl_gui.workspace import Workspace

    made = Workspace(work / "settings.json").create(
        work / "tabled", "Tabled", output_format="param_table")
    root = made.parent
    true(not (root / "lib").exists(), f"no lib/: {sorted(p.name for p in root.iterdir())}")
    true('"format": "param_table"' in made.read_text(encoding="utf-8"),
         "and the project says which format it is")
    true((root / "parameter_lists").is_dir(), "the lists folder is still made")

    other = Workspace(work / "settings.json").create(work / "smart", "Smart")
    true(not (other.parent / "lib").exists(),
         "a smart-data project is not given one either")
    true((other.parent / "parameter_lists").is_dir(),
         "but it still gets somewhere to put its lists")


def test_a_new_list_must_name_a_sub_system(work):
    """In this format a list's file name IS its sub-system.  (Reported.)

    A list called anything else used to be created, put in the build, and only
    then reported as PTB005.  It is refused now, before anything is written.
    """
    document, api, root = new_project(work)
    add(api, document, "PR_A")
    folder = root / "parameter_lists"
    files_before = sorted(item.name for item in folder.iterdir())
    build_before = list(document.config.inputs.model_files)

    answer = api.new_list({"name": "parameter_list_test"})
    equal(answer["ok"], False, "a name that is not a sub-system is refused")
    true("does not name a sub-system" in answer.get("message", ""),
         f"and it says why: {answer.get('message')}")
    true("SYS_RHS" in answer["message"], "listing the sub-systems it could be")
    equal(sorted(item.name for item in folder.iterdir()), files_before,
          "nothing was written")
    equal(document.config.inputs.model_files, build_before, "the build is unchanged")
    true("parameter_list_test" not in (root / PROJECT_FILE_NAME).read_text(encoding="utf-8"),
         "and so is the project file")

    answer = api.new_list({"name": "SYS_RHS"})
    equal(answer["ok"], True, f"a sub-system's name is taken: {answer.get('message')}")
    equal(pathlib.Path(answer["path"]).name, "sys_rhs_paramTable.xml",
          "and written the one way the format reads it")
    true(any(item.name == "sys_rhs_paramTable.xml"
             for item in document.config.inputs.model_files), "it is in the build")
    true("PTB005" not in codes(document), "and nothing says it names no sub-system")

    first, api2, root2 = new_project(work, name="listless", lists=())
    answer = api2.new_list({"name": "sys_gs_manager"})
    equal(answer["ok"], True,
          f"a project's first list is judged the same way: {answer.get('message')}")
    equal(pathlib.Path(answer["path"]).name, "sys_gs_manager_paramTable.xml",
          "and named the same way")


def test_a_sub_system_has_one_list(work):
    """Two lists of one sub-system would be two blocks for it, both from 0."""
    document, api, root = new_project(work, lists=("sys_rhs_paramTable",))
    answer = api.new_list({"name": "sys_rhs"})
    equal(answer["ok"], False, "a second list for SYS_RHS is refused")
    true("already has a parameter sublist" in answer.get("message", ""),
         f"naming the one it has: {answer.get('message')}")
    true("sys_rhs_paramTable.xml" in answer["message"], "by its file name")

    other = root / "parameter_lists" / "sys_rhs.xml"
    other.write_text(EMPTY_LIST, encoding="utf-8")
    answer = api.select_lists({"paths": [str(item) for item in
                                         document.config.inputs.model_files]
                                        + [str(other)]})
    equal(answer["ok"], False,
          f"ticking a second SYS_RHS list into the build is refused too: {answer}")


def test_an_existing_file_must_name_a_sub_system(work):
    """Adding a file that is already there is judged the same way."""
    document, api, root = new_project(work)
    folder = root / "parameter_lists"
    stray = folder / "notes.xml"
    stray.write_text(EMPTY_LIST, encoding="utf-8")
    build_before = list(document.config.inputs.model_files)

    answer = api.add_existing_list({"path": str(stray)})
    equal(answer["ok"], False, "a file that names no sub-system is not added")
    true("does not name a sub-system" in answer.get("message", ""),
         f"and it says why: {answer.get('message')}")
    equal(document.config.inputs.model_files, build_before, "the build is unchanged")

    answer = api.select_lists({"paths": [str(item) for item in build_before]
                                        + [str(stray)]})
    equal(answer["ok"], False, "ticking it into the build is refused as well")
    true("does not name a sub-system" in answer.get("message", ""),
         f"for the same reason: {answer.get('message')}")
    equal(document.config.inputs.model_files, build_before,
          "and the build is still unchanged")

    # A copy that would have had to be renamed - sys_rhs_paramTable_2.xml -
    # would name no sub-system: refused before anything is copied.
    (folder / "sys_rhs_paramTable.xml").write_text(EMPTY_LIST, encoding="utf-8")
    elsewhere = work / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "sys_rhs_paramTable.xml").write_text(EMPTY_LIST, encoding="utf-8")
    files_before = sorted(item.name for item in folder.iterdir())
    answer = api.add_existing_list({"path": str(elsewhere / "sys_rhs_paramTable.xml")})
    equal(answer["ok"], False, f"a clash in the list folder is refused: {answer}")
    equal(sorted(item.name for item in folder.iterdir()), files_before,
          "and nothing was copied")


def test_an_old_badly_named_list_still_reorders(work):
    """A build that already holds one is not locked by the new check."""
    document, api, root = new_project(
        work, lists=("sys_rhs_paramTable", "old_badly_named"))
    add(api, document, "PR_A")
    order = [str(item) for item in document.config.inputs.model_files]

    answer = api.select_lists({"paths": list(reversed(order))})
    equal(answer["ok"], True, f"reordering is not refused: {answer.get('message')}")
    equal([pathlib.Path(item).name for item in answer["paths"]],
          ["old_badly_named.xml", "sys_rhs_paramTable.xml"], "in the new order")
    true("PTB005" in codes(document), "while PTB005 goes on reporting it")

    answer = api.select_lists({"paths": [order[0]]})
    equal(answer["ok"], True, f"and it can be unticked: {answer.get('message')}")


def test_a_smart_data_project_takes_any_name(work):
    """The check belongs to the parameter-table format only."""
    document, api, root = new_project(work, name="smart", output_format="smart_data")
    answer = api.new_list({"name": "anything_at_all"})
    equal(answer["ok"], True, f"any name in smart data: {answer.get('message')}")
    equal(pathlib.Path(answer["path"]).name, "anything_at_all.xml", "kept as typed")


def test_a_new_parameter_carries_its_lists_sub_system(work):
    """In a parameter table the file's sub-system goes into the tag.  (Reported.)

    The form showed the file's sub-system in place of the tag, and the tag
    itself stayed SYS_UNKNOWN - in the grid and in the file.  The list is the
    database: a smart-data project reading it decides the sub-system by the tag.
    """
    document, api, root = new_project(work, lists=("sys_rhs_paramTable",))
    api.add({"parent": "", "kind": "primitive"})
    equal(document.find("NewParameter").tags.get("SystemName"), "SYS_RHS",
          "a new parameter says its list's sub-system")
    row = next(item for item in api.state({})["tree"] if item["path"] == "NewParameter")
    equal(row["tags"].get("SystemName"), "SYS_RHS", "and so does the grid")

    document.save()
    text = (root / "parameter_lists" / "sys_rhs_paramTable.xml").read_text(encoding="utf-8")
    true('<Tag id="SystemName" kind="enum" value="SYS_RHS" />' in text,
         f"and so does the file: {text}")


def test_opening_a_list_writes_in_its_sub_system(work):
    """A list whose parameters say otherwise is corrected when it is opened."""
    smart, smart_api, smart_root = new_project(
        work, name="smart", lists=("sys_rhs_paramTable",), output_format="smart_data")
    add(smart_api, smart, "PR_A", tags={"SystemName": "SYS_UNKNOWN"})
    add(smart_api, smart, "PR_B", tags={"SystemName": "SYS_GS_MANAGER"})
    smart.save()

    document, api, root = new_project(work, lists=("sys_rhs_paramTable",))
    hand_over(smart_root, root, stem="sys_rhs_paramTable")
    document.load()
    equal([node.tags.get("SystemName") for node in document.model.parameters],
          ["SYS_RHS", "SYS_RHS"], "every parameter says its file's sub-system once opened")
    equal(document.dirty, False, "without marking the list modified")
    found = [item for item in document.validate() if item["code"] == "PTB008"]
    equal([item["severity"] for item in found], ["warning"],
          f"and one warning says so: {found}")
    true("save" in found[0]["message"], f"telling what to do: {found[0]['message']}")

    document.save()
    equal(document.validate_codes("PTB008"), 0, "saving writes it, and the warning goes")
    document.load()
    equal(document.validate_codes("PTB008"), 0, "and it stays written")

    hand_over(root, smart_root, stem="sys_rhs_paramTable")
    smart.load()
    equal([node.tags.get("SystemName") for node in smart.model.parameters],
          ["SYS_RHS", "SYS_RHS"],
          "so a smart-data project reading the same file sees the sub-system")


def test_a_list_on_disk_that_disagrees_warns(work):
    """A list of the build that was never saved that way is named."""
    smart, smart_api, smart_root = new_project(
        work, name="smart", lists=("sys_rhs_paramTable",), output_format="smart_data")
    add(smart_api, smart, "PR_RHS", tags={"SystemName": "SYS_UNKNOWN"})
    smart.save()

    document, api, root = new_project(
        work, lists=("sys_gs_manager_paramTable", "sys_rhs_paramTable"))
    hand_over(smart_root, root, stem="sys_rhs_paramTable")
    add(api, document, "PR_GSM")
    found = [item for item in document.validate() if item["code"] == "PTB008"]
    equal(len(found), 1, f"one warning, for the list on disk: {found}")
    equal(found[0]["severity"], "warning", "a warning, not an error")
    true("sys_rhs_paramTable.xml" in found[0]["message"],
         f"naming that list: {found[0]['message']}")

    document.save()
    true(document.generate()["success"], "and it does not stop the build")


def test_a_file_that_names_no_system_is_not_stamped(work):
    """A file that names no sub-system writes none: PTB005 says what is wrong."""
    document, api, root = new_project(work, lists=("nothing_like_a_system",))
    api.add({"parent": "", "kind": "primitive"})
    true(document.find("NewParameter").tags.get("SystemName") != "NOTHING_LIKE_A_SYSTEM",
         "no made-up sub-system is written into the tag")
    equal(document.validate_codes("PTB008"), 0, "and there is no PTB008 about it")
    true("PTB005" in codes(document), "PTB005 is what reports the file")


def test_the_check_and_ok_agree(work):
    """The Open dialog's check says what OK would say - before OK.  (Reported.)

    The check used to answer only "is it a parameter list?", so a list that
    names no sub-system looked fine and was refused only after OK.
    """
    document, api, root = new_project(work)
    stray = root / "parameter_lists" / "notes.xml"
    stray.write_text(EMPTY_LIST, encoding="utf-8")

    verdict = api.inspect_list({"path": str(stray)})
    answer = api.add_existing_list({"path": str(stray)})
    equal((verdict["ok"], answer["ok"]), (False, False), "both refuse it")
    equal(verdict.get("reason"), answer.get("message"), "for the same reason")
    true("does not name a sub-system" in (verdict.get("reason") or ""),
         f"said before OK: {verdict.get('reason')}")

def test_the_address_is_a_field_of_its_own(work):
    """The table's address is the Address field - 0 unless set, not Tag1.  (Reported.)"""
    document, api, root = new_project(work)
    add(api, document, "PR_A")
    equal(document.find("PR_A").address, 0, "a new parameter's address is 0")

    for bad in (-1, "abc", 1.5):
        answer = api.update({"path": "PR_A", "changes": {"address": bad}})
        equal(answer["ok"], False, f"address {bad!r} is refused")
        true("whole number" in (answer.get("message") or ""),
             f"saying what it takes: {answer.get('message')}")

    answer = api.update({"path": "PR_A", "changes": {"address": "400"}})
    equal(answer["ok"], True, f"a whole number is taken: {answer.get('message')}")
    equal(document.find("PR_A").address, 400, "and kept as a number")
    node = next(item for item in api.state({})["tree"] if item["path"] == "PR_A")
    equal(node["address"], 400, "the form and the grid get it")

    copy = api.duplicate({"path": "PR_A"})
    equal(document.find(copy["selected"]).address, 0,
          "a copy is placed by the firmware: address 0")

    document.save()
    text = (root / "parameter_lists" / "sys_gs_manager_paramTable.xml").read_text(
        encoding="utf-8")
    true('address="400"' in text and 'address="0"' in text,
         f"both are written into the file: {text}")


def test_a_hand_written_address_is_checked(work):
    """An address the table cannot take, edited into a file by hand, is PTB009."""
    document, api, root = new_project(work)
    add(api, document, "PR_A")
    document.find("PR_A").address = -5
    true("PTB009" in codes(document), f"a negative address is an error: {codes(document)}")


def test_none_is_the_first_mode(work):
    """PARAM_MODE_NONE is a mode of its own, first in the shipped list.  (Asked for.)

    So it is ``#define PARAM_MODE_NONE (0)`` and every other mode is one
    higher.  A parameter table still lets a parameter have any mode - only a
    smart-data project fixes it.
    """
    equal(default_choices()["paramModes"][0], "PARAM_MODE_NONE", "first in the shipped list")

    document, api, root = new_project(work)
    equal(api.state({})["fixedTags"], {}, "nothing is fixed in a parameter table")
    api.add({"parent": "", "kind": "primitive"})
    modes = document.model.defines.get("PARAM MODES")
    equal(document.find("NewParameter").tags["ParamMode"], modes[0],
          "a new parameter takes the first mode of the list")
    api.delete({"path": "NewParameter"})

    add(api, document, "PR_A", tags={"ParamMode": "PARAM_MODE_FACTORY"})
    node = next(item for item in api.state({})["tree"] if item["name"] == "PR_A")
    equal(node["tags"]["ParamMode"], "PARAM_MODE_FACTORY", "the grid shows the mode chosen")
    document.save()
    true(document.generate()["success"], "the build")
    text = (root / "nsrParamTables.h").read_text(encoding="utf-8")
    row = next(squeeze(line) for line in text.splitlines() if line.startswith("ADD_PARAM("))
    true("PARAM_MODE_FACTORY," in row, f"the row has the mode chosen: {row}")
    if "PARAM_MODE_NONE" in modes:
        line = next(l for l in text.splitlines() if l.startswith("#define PARAM_MODE_NONE "))
        equal(line.split("(")[1].rstrip(")"), str(modes.index("PARAM_MODE_NONE")),
              "NONE is numbered by its place in the list")


def test_the_table_numbers_modes_by_their_place(work):
    """The numbers of the Drop-down lists dialog are the smart-data header's.  (Asked for.)

    A parameter table writes its #define PARAM_MODE_... block as it always has:
    numbered by the place in the list, with no #ifndef - so a number given in
    the dialog, even one two modes share, changes nothing here.
    """
    import pl_codegen.choices as choices
    real = choices.CHOICES_FILE
    choices.CHOICES_FILE = work / "choices.json"   # never the machine's own list
    try:
        document, api, root = new_project(work)
        true(api.set_defines({"list": "paramModes", "values": [
            "PARAM_MODE_NONE = 40", "PARAM_MODE_USER = 40",
            "PARAM_MODE_FACTORY = 7"]})["ok"], "the list")
        add(api, document, "PR_A")
        true("DEF005" not in codes(document), f"no clash in a table: {codes(document)}")
        document.save()
        true(document.generate()["success"], "the build")
        text = (root / "nsrParamTables.h").read_text(encoding="utf-8")
        defines = [re.sub(r"\s+", " ", line) for line in text.splitlines()
                   if line.startswith("#define PARAM_MODE")]
        equal(defines, ["#define PARAM_MODE_NONE (0)", "#define PARAM_MODE_USER (1)",
                        "#define PARAM_MODE_FACTORY (2)"], "numbered by place, as before")
        true("#ifndef" not in text, "and no #ifndef")
    finally:
        choices.CHOICES_FILE = real


def test_the_system_names_have_a_file_of_their_own(work):
    """nsrSystemNames.h: every system name with its number, beside the other two.  (Asked for.)

    The table's '#if DESIRED_SUB_SYSTEM == SYS_NAV' lines need the names as
    macros.  The number is the Drop-down lists dialog's, each name is written
    only #ifndef, and nothing else is in the file - the table does not include
    it, the firmware does.
    """
    import pl_codegen.choices as choices
    real = choices.CHOICES_FILE
    choices.CHOICES_FILE = work / "choices.json"   # never the machine's own list
    try:
        document, api, root = new_project(work)
        true(api.set_defines({"list": "systemNames", "values": [
            "SYS_UNKNOWN = 0", "SYS_GS_MANAGER = 2", "SYS_NEXT", "SYS_NAV = 0x10",
            "SYS_TEST = -3"]})["ok"],
             "the list - a negative number too")
        add(api, document, "PR_A")
        document.save()
        result = document.generate()
        true(result["success"], f"the build: {result.get('message')}")
        true(any(pathlib.Path(f).name == "nsrSystemNames.h" for f in result["files"]),
             "it is written with the other two")

        text = (root / "nsrSystemNames.h").read_text(encoding="utf-8")
        defined = re.findall(r"#ifndef (\w+)\n#define (\w+) +\((-?\d+)\)\n#endif\n", text)
        equal([(name, int(number)) for guard, name, number in defined if guard == name],
              [("SYS_UNKNOWN", 0), ("SYS_GS_MANAGER", 2), ("SYS_NEXT", 3), ("SYS_NAV", 16),
               ("SYS_TEST", -3)],
              "every name, with the dialog's number, only #ifndef")
        true("#ifndef NSRSYSTEMNAMES_H\n#define NSRSYSTEMNAMES_H" in text,
             "the file has an include guard")
        true("PARAM_MODE" not in text and "ADD_PARAM(" not in text, "and holds nothing else")
        table = (root / "nsrParamTables.h").read_text(encoding="utf-8")
        true("nsrSystemNames" not in table, "the table does not include it")

        api.set_defines({"list": "systemNames", "values": [
            "SYS_UNKNOWN = 0", "SYS_GS_MANAGER = 2", "SYS_NAV = 2"]})
        true("DEF005" in codes(document), "two system names with one number are an error here too")
    finally:
        choices.CHOICES_FILE = real



CASES = [
    ("one file, one block per list", test_one_file_per_project),
    ("every column", test_the_columns),
    ("the modes come from the machine", test_the_modes_come_from_the_machine),
    ("the editor will not build one", test_the_editor_will_not_build_one),
    ("a structure that arrived from elsewhere", test_a_structure_that_arrived_from_elsewhere),
    ("an array that arrived from elsewhere", test_an_array_that_arrived_from_elsewhere),
    ("a boolean is refused", test_a_boolean_is_refused),
    ("the ignored tags say nothing", test_the_ignored_tags_say_nothing),
    ("the editor sets them, not the sub-system",
     test_the_editor_sets_them_but_not_the_sub_system),
    ("the file name names the system", test_the_file_name_names_the_system),
    ("the output lands where it is told", test_the_output_lands_where_it_is_told),
    ("the same list in both formats", test_the_same_list_in_both_formats),
    ("the file it replaces, rebuilt", test_the_file_it_replaces),
    ("reordering the lists moves nothing", test_reordering_the_lists_moves_nothing),
    ("a sublist counts from zero", test_a_sublist_counts_from_zero),
    ("the same name in two sublists", test_the_same_name_in_two_sublists),
    ("a new row in the middle warns", test_a_new_row_in_the_middle_is_the_one_that_warns),
    ("an abandoned copy is reported", test_an_abandoned_copy_is_reported),
    ("the offsets note", test_the_offsets_note),
    ("a disabled parameter takes nothing", test_a_disabled_parameter_takes_nothing),
    ("a new project gets no library", test_a_new_project_gets_no_library),
    ("a new list must name a sub-system", test_a_new_list_must_name_a_sub_system),
    ("a sub-system has one list", test_a_sub_system_has_one_list),
    ("an existing file must name a sub-system", test_an_existing_file_must_name_a_sub_system),
    ("an old badly named list still reorders", test_an_old_badly_named_list_still_reorders),
    ("a smart-data project takes any name", test_a_smart_data_project_takes_any_name),
    ("a new parameter carries its list's sub-system",
     test_a_new_parameter_carries_its_lists_sub_system),
    ("opening a list writes in its sub-system", test_opening_a_list_writes_in_its_sub_system),
    ("a list on disk that disagrees warns", test_a_list_on_disk_that_disagrees_warns),
    ("a file that names no system is not stamped",
     test_a_file_that_names_no_system_is_not_stamped),
    ("the check and OK agree", test_the_check_and_ok_agree),
    ("the address is a field of its own", test_the_address_is_a_field_of_its_own),
    ("a hand-written address is checked", test_a_hand_written_address_is_checked),
    ("NONE is the first mode", test_none_is_the_first_mode),
    ("the table numbers modes by their place", test_the_table_numbers_modes_by_their_place),
    ("the system names have a file of their own",
     test_the_system_names_have_a_file_of_their_own),
]


def main() -> int:
    failures = 0
    for title, case in CASES:
        with tempfile.TemporaryDirectory(prefix="pl_paramtable_") as raw:
            try:
                case(pathlib.Path(raw))
            except Failure as error:
                failures += 1
                print(f"  [{paint('FAIL', BOLD + BRIGHT_RED)}] {title}\n         {error}")
                continue
            except Exception:                              # noqa: BLE001
                failures += 1
                print(f"  [{paint('ERROR', BOLD + BRIGHT_RED)}] {title}")
                print("         " + traceback.format_exc().replace("\n", "\n         "))
                continue
        print(f"  [{paint('PASS', GREEN)}] {title}")

    print()
    if failures:
        print(paint(f"{failures} of {len(CASES)} parameter-table case(s) FAILED.",
                    BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} parameter-table cases passed.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
