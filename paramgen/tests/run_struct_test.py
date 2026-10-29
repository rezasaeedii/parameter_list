# -*- coding: utf-8 -*-
"""Structure types: declaring them, using them, changing them, deleting them.

Every case here is something a person does to a struct in the editor, driven
through the same API the buttons call.  Four of them are bugs that were
reported from real use:

  * two structures could be given the same name;
  * deleting a structure left it in the type list;
  * a parameter could be given a structure as its data type, which generated
    nonsense;
  * changing a type left every parameter already built from it behind.

Run it with::

    python tests/run_struct_test.py
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
from pl_codegen.config import Config                                 # noqa: E402
from pl_codegen.errors import DiagnosticCollector                    # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,       # noqa: E402
                                      colour_supported, paint)
from pl_codegen.xml_model.types_xml import read_types, types_file_for  # noqa: E402
from pl_codegen.xml_model.xml_reader import read_xml                 # noqa: E402
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
  <Defines>
    <DefineGroup name="TYPE"><Value value="MONITORING" /><Value value="SETTING" /></DefineGroup>
    <DefineGroup name="PARAM MODES"><Value value="PARAM_MODE_USER" /></DefineGroup>
    <DefineGroup name="SYSTEM NAMES"><Value value="SYS_NAV" /></DefineGroup>
    <DefineGroup name="VALUE TYPES">
      <Value value="bool_t" /><Value value="uint8_t" /><Value value="int16_t" />
      <Value value="uint16_t" /><Value value="float32_t" /><Value value="float64_t" />
    </DefineGroup>
  </Defines>
  <Parameters />
</ParameterListModel>
"""


def new_project(work: pathlib.Path, name: str = "structs"):
    """A project with one empty parameter list, opened."""
    root = work / name
    (root / "parameter_lists").mkdir(parents=True)
    (root / "parameter_lists" / "list.xml").write_text(EMPTY_LIST, encoding="utf-8")
    copy_lib_into(root / "lib")
    settings = PROJECT_TEMPLATE.read_text(encoding="utf-8").replace("{{NAME}}", name)
    settings = settings.replace('"model_files": [],', '"model_files": ["list.xml"],')
    (root / PROJECT_FILE_NAME).write_text(settings, encoding="utf-8")

    document = Document(Config.load(root / PROJECT_FILE_NAME))
    document.load()
    # a settings file of its own: the app's is the user's recent list
    workspace = Workspace(work / f"{name}_settings.json")
    workspace.adopt(document)
    return document, Api(workspace), root


def a_type(api, name, fields):
    """Declare a type and give it fields, the way the panel does."""
    answer = api.new_type({"name": name})
    true(answer["ok"], f"declaring '{name}': {answer.get('message')}")
    answer = api.update_type({"name": name, "changes": {"fields": fields}})
    true(answer["ok"], f"giving '{name}' its fields: {answer.get('message')}")
    return answer["name"]


F32 = {"name": "Lat", "valueType": "float64_t", "arraySize": 1}


# ------------------------------------------------------------------ cases
def test_one_name_one_type(work):
    """Two structure types cannot share a name.  (Reported bug.)"""
    _document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32)])

    again = api.new_type({"name": "Position"})
    equal(again["ok"], False, "declaring 'Position' twice is refused")
    true("already exists" in again["message"], "and says why")

    # ...and the same through a rename, which is the other way in
    a_type(api, "Attitude", [dict(F32, name="Roll", valueType="float32_t")])
    renamed = api.update_type({"name": "Attitude", "changes": {"name": "Position"}})
    equal(renamed["ok"], False, "renaming onto a taken name is refused")

    names = [row["name"] for row in api.state({})["structTypes"]]
    equal(sorted(names), ["Attitude", "Position"], "both types are still there")


def test_a_parameter_cannot_be_a_structure(work):
    """A parameter holds a value; a structure type is not one.  (Reported bug.)

    Two halves: the editor refuses the edit and says why, and a file that was
    written that way by hand is reported rather than generated.
    """
    document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32)])

    api.add({"parent": "", "kind": "primitive"})
    document.update("NewParameter", {"name": "Speed"})

    refused = api.update({"path": "Speed", "changes": {"value_type_name": "Position"}})
    equal(refused["ok"], False, "a parameter cannot be given a structure type")
    true("structure type" in refused["message"], "and says why")
    equal(document.find("Speed").value_type_name, "uint8_t", "the old type is kept")

    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": "Where"})
    refused = api.update({"path": "Where", "changes": {"value_type_name": "float32_t"}})
    equal(refused["ok"], False, "a structure cannot be given a data type")
    true("data type" in refused["message"], "and says why")

    # a file written that way by hand still has to be reported, not generated
    document.find("Speed").value_type_name = "Position"
    equal(document.validate_codes("TYP004"), 1,
          "a parameter typed as a structure is an error")
    document.find("Speed").value_type_name = "uint8_t"
    document.find("Where").value_type_name = "float32_t"
    equal(document.validate_codes("TYP005"), 1,
          "a structure typed as a data type is an error")


def test_deleting_a_structure(work):
    """Deleting the last parameter of a type leaves the type deletable.

    The reported bug: deleting a structure left it in the type list for ever,
    because the list and the types were the same thing.  They are separate now,
    and the type is deleted from its own panel - but only once nothing uses it,
    which is the answer somebody actually needs.
    """
    document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    api.add({"parent": "", "kind": "struct"})
    api.use_type({"path": "NewStruct", "name": "Position"})

    refused = api.delete_type({"name": "Position"})
    equal(refused["ok"], False, "a type in use is not deleted")
    true("still used" in refused["message"], "and says by what")

    equal(document.delete("NewStruct"), True, "the parameter is deleted")
    equal(api.state({})["structTypes"][0]["usedHere"], [], "nothing uses it now")

    gone = api.delete_type({"name": "Position"})
    equal(gone["ok"], True, f"an unused type is deleted: {gone.get('message')}")
    equal([row["name"] for row in api.state({})["structTypes"]], [],
          "and is gone from the list")


def test_editing_a_type_reaches_every_parameter(work):
    """Add a field to a type and every parameter of that type grows it."""
    document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32), dict(F32, name="Lon")])

    for name in ("Home", "Target"):
        api.add({"parent": "", "kind": "struct"})
        document.update("NewStruct", {"name": name})
        api.use_type({"path": name, "name": "Position"})

    equal([c.name for c in document.find("Home").children], ["Lat", "Lon"],
          "the parameter has the type's fields")

    # a field added in the MIDDLE, which is the case that moves log ids
    api.update_type({"name": "Position", "changes": {"fields": [
        dict(F32), dict(F32, name="Alt", valueType="float32_t"),
        dict(F32, name="Lon")]}})

    for name in ("Home", "Target"):
        equal([c.name for c in document.find(name).children], ["Lat", "Alt", "Lon"],
              f"'{name}' grew the new field, in the right place")

    # a field removed disappears everywhere
    api.update_type({"name": "Position", "changes": {"fields": [dict(F32)]}})
    for name in ("Home", "Target"):
        equal([c.name for c in document.find(name).children], ["Lat"],
              f"'{name}' lost the removed fields")


def test_limits_are_the_parameters_own(work):
    """A type says what fields there are; the limits belong to the parameter."""
    document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32), dict(F32, name="Lon")])

    for name in ("Home", "Target"):
        api.add({"parent": "", "kind": "struct"})
        document.update("NewStruct", {"name": name})
        api.use_type({"path": name, "name": "Position"})

    document.update("Home.Lat", {"minimum": -90, "maximum": 90, "default_value": 10})
    document.update("Target.Lat", {"minimum": -10, "maximum": 10, "default_value": 0})

    equal(document.find("Home.Lat").maximum, 90, "Home keeps its own maximum")
    equal(document.find("Target.Lat").maximum, 10, "Target keeps its own")

    # ...and they survive an edit of the type
    api.update_type({"name": "Position", "changes": {"fields": [
        dict(F32), dict(F32, name="Lon"), dict(F32, name="Alt", valueType="float32_t")]}})
    equal(document.find("Home.Lat").maximum, 90, "still Home's own after a type edit")
    equal(document.find("Target.Lat").maximum, 10, "still Target's own")
    # what a new parameter starts with - no range - and nobody else's limits
    # (it used to start empty, with a warning on every field: asked to change)
    equal((document.find("Home.Alt").minimum, document.find("Home.Alt").maximum),
          (0.0, 0.0), "a new field starts with no range, not with another field's")


def test_renaming_a_type(work):
    """Renaming a type renames it everywhere it is named."""
    document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    a_type(api, "Waypoint", [{"name": "Where", "valueType": "Position", "arraySize": 1}])

    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": "Home"})
    api.use_type({"path": "Home", "name": "Position"})

    answer = api.update_type({"name": "Position", "changes": {"name": "GeoPoint"}})
    true(answer["ok"], f"the rename went through: {answer.get('message')}")

    equal(document.find("Home").value_type_name, "GeoPoint", "the parameter follows")
    waypoint = document.find_struct_type("Waypoint")
    equal(waypoint.fields[0].value_type_name, "GeoPoint", "the other type follows too")
    equal(document.validate_codes("TYP003"), 0, "nothing points at the old name")


def test_a_type_cannot_contain_itself(work):
    """A struct that holds a copy of itself has no size."""
    _document, api, _root = new_project(work)
    a_type(api, "Node", [dict(F32)])
    api.update_type({"name": "Node", "changes": {"fields": [
        {"name": "Next", "valueType": "Node", "arraySize": 1}]}})

    document = _document
    equal(document.validate_codes("TYP015"), 1, "the cycle is reported")


def test_the_types_file_travels_with_the_list(work):
    """A list is saved with its types beside it, and only the ones it uses."""
    document, api, root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    a_type(api, "Unused", [dict(F32, name="Nothing")])

    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": "Home"})
    api.use_type({"path": "Home", "name": "Position"})
    document.save()

    beside = types_file_for(root / "parameter_lists" / "list.xml")
    true(beside.is_file(), "the types file is written next to the list")
    written = read_types(beside)
    # Everything this list declares, used or not: a type somebody has just
    # made and has not placed yet must survive being saved.
    equal(written.names(), ["Position", "Unused"], "the list's own types")

    # ...and reading the pair back gives the same parameters
    again = read_xml(root / "parameter_lists" / "list.xml", DiagnosticCollector())
    equal(again.struct_types.names(), ["Position", "Unused"], "the types come back")
    equal([c.name for c in again.parameters[0].children], ["Lat"],
          "and the parameter still has its fields")


def test_a_list_from_another_project(work):
    """A list opened somewhere else keeps its structures."""
    document, api, root = new_project(work, "first")
    a_type(api, "Position", [dict(F32), dict(F32, name="Lon")])
    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": "Home"})
    api.use_type({"path": "Home", "name": "Position"})
    document.save()

    # copy the two files into a project that has never heard of Position
    other, _api2, other_root = new_project(work, "second")
    for name in ("list.xml", "list_types.xml"):
        shutil.copy(root / "parameter_lists" / name,
                    other_root / "parameter_lists" / f"moved_{name}")

    moved = read_xml(other_root / "parameter_lists" / "moved_list.xml",
                     DiagnosticCollector())
    equal(moved.struct_types.names(), ["Position"], "the type travelled with it")
    equal([c.name for c in moved.parameters[0].children], ["Lat", "Lon"],
          "and the parameter kept its shape")


def test_a_new_parameter_is_never_a_broken_structure(work):
    """Adding a structure gives it a type when there is one to give.

    The reported bug: adding a parameter and setting its kind to 'struct' left
    a structure with no type, no fields and no way to get either.
    """
    document, api, _root = new_project(work)

    added = api.add({"parent": "", "kind": "struct"})
    true(added["ok"], "a structure can be added with no types declared yet")
    equal(document.validate_codes("TYP002"), 1,
          "and says, in one error, that it needs a type")

    a_type(api, "Position", [dict(F32)])
    api.use_type({"path": added["selected"], "name": "Position"})
    equal(document.validate_codes("TYP002"), 0, "which giving it a type answers")
    equal([c.name for c in document.find(added["selected"]).children], ["Lat"],
          "and it has the type's fields")


def test_a_fields_shape_belongs_to_the_type(work):
    """A field's name, data type and array size cannot be changed on the parameter.

    Its unit and description can - they are this use's own, which the second
    half of the case checks.

    They used to look changeable: the edit was accepted, the type kept the old
    value, and the next thing that re-applied the type threw the edit away
    without a word.
    """
    document, api, _root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": "Home"})
    api.use_type({"path": "Home", "name": "Position"})

    for key, value in (("name", "Renamed"), ("value_type_name", "int16_t"),
                       ("array_size", 4), ("enable", False)):
        answer = api.update({"path": "Home.Lat", "changes": {key: value}})
        equal(answer["ok"], False, f"changing a field's {key} on the parameter")
        true("structure type" in answer["message"], f"and saying why for {key}")

    # what IS the parameter's own goes through
    ok_answer = api.update({"path": "Home.Lat", "changes": {"maximum": 90}})
    equal(ok_answer["ok"], True, "the limits are still the parameter's own")
    equal(document.find("Home.Lat").maximum, 90, "and they land")

    # ...and so are the unit and the description: they say what THIS use of the
    # type means, so they are set here and they land here
    for key, value in (("unit", "rad"), ("description", "latitude of home")):
        answer = api.update({"path": "Home.Lat", "changes": {key: value}})
        equal(answer["ok"], True, f"a field's {key} is the parameter's own: "
                                  f"{answer.get('message')}")
    equal(document.find("Home.Lat").unit, "rad", "the unit landed")
    equal(document.find("Home.Lat").description, "latitude of home",
          "the description landed")


def test_deleting_a_list_takes_its_structures(work):
    """A list's structures file is not left behind when the list is deleted."""
    document, api, root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    api.add({"parent": "", "kind": "struct"})
    document.update("NewStruct", {"name": "Home"})
    api.use_type({"path": "Home", "name": "Position"})
    document.save()

    # a second list, because a build always needs one left
    document.create_list("keeper")

    beside = types_file_for(root / "parameter_lists" / "list.xml")
    true(beside.is_file(), "the structures file was written")
    document.remove_list(str(root / "parameter_lists" / "list.xml"), delete_file=True)
    equal(beside.is_file(), False, "the structures file went with the list")


def test_a_list_from_elsewhere_is_copied_in(work):
    """A list from another project is copied in, structures and all."""
    first, api, first_root = new_project(work, "first")
    a_type(api, "Position", [dict(F32)])
    api.add({"parent": "", "kind": "struct"})
    first.update("NewStruct", {"name": "Home"})
    api.use_type({"path": "Home", "name": "Position"})
    first.save()

    second, _api2, second_root = new_project(work, "second")
    brought = second.add_existing_list(str(first_root / "parameter_lists" / "list.xml"))

    true(str(brought).startswith(str(second_root)),
         f"the list was not copied into the project: {brought}")
    true(types_file_for(brought).is_file(), "its structures did not come with it")
    entries = [str(item) for item in second.config.inputs.model_files]
    true(all(".." not in entry for entry in entries),
         f"the project file points outside itself: {entries}")



def test_unit_and_description_belong_to_the_use(work):
    """One type, two uses, two meanings.  (Reported.)

    A structure type is only a shape.  ``xyz`` can be a speed in one parameter
    and an offset in another, so the unit and the description of its fields are
    set where it is used - and a type edit, a save, a reload and the generated
    code all have to keep each use's own.  They used to belong to the type, so
    every use of it was forced to share one unit.
    """
    document, api, root = new_project(work)
    a_type(api, "xyz", [{"name": "x", "valueType": "float32_t", "arraySize": 1},
                        {"name": "y", "valueType": "float32_t", "arraySize": 1}])
    for name in ("Speed", "Move"):
        api.add({"parent": "", "kind": "struct"})
        document.update("NewStruct", {"name": name})
        api.use_type({"path": name, "name": "xyz"})

    meaning = {"Speed": ("m/s", "speed along x"), "Move": ("m", "offset along x")}
    for name, (unit, text) in meaning.items():
        answer = api.update({"path": f"{name}.x",
                             "changes": {"unit": unit, "description": text}})
        equal(answer["ok"], True, f"setting {name}.x: {answer.get('message')}")

    def both_kept(when):
        for name, (unit, text) in meaning.items():
            field = document.find(f"{name}.x")
            equal(field.unit, unit, f"{when}: the unit of {name}.x")
            equal(field.description, text, f"{when}: the description of {name}.x")

    both_kept("right after setting them")

    # the type grows a field: both uses keep what they said about x
    grown = api.update_type({"name": "xyz", "changes": {"fields": [
        {"name": "x", "valueType": "float32_t", "arraySize": 1},
        {"name": "y", "valueType": "float32_t", "arraySize": 1},
        {"name": "z", "valueType": "float32_t", "arraySize": 1}]}})
    equal(grown["ok"], True, f"adding z to the type: {grown.get('message')}")
    equal([child.name for child in document.find("Speed").children], ["x", "y", "z"],
          "the parameter grew z")
    both_kept("after the type changed")
    true(not document.find("Speed.z").unit, "a field the type just added has no unit yet")

    document.save()
    document.load()
    both_kept("after a save and a reload")

    structures = types_file_for(root / "parameter_lists" / "list.xml").read_text(
        encoding="utf-8")
    true("unit=" not in structures, f"the types file names no unit: {structures}")
    true("description=" not in structures, f"and no description: {structures}")

    # every field needs limits to build; they are the parameter's own as well
    for name in meaning:
        for member in ("x", "y", "z"):
            document.update(f"{name}.{member}", {"default_value": 0, "minimum": 0,
                                                 "maximum": 0, "resolution": 0.1})
    result = document.generate()
    true(result["success"], f"the build: {result.get('message')}")
    def generated(suffix):
        return next(pathlib.Path(item) for item in result["files"]
                    if item.endswith(suffix)).read_text(encoding="utf-8")

    # ONE typedef for the type, and both parameters are instances of it
    types_h = generated("_types.h")
    equal(types_h.count("typedef struct {"), 1, f"one typedef for xyz: {types_h}")
    true("} sCgStruct_xyz;" in types_h, "named after the type")
    smart_c = generated("cg_smart_data.c")
    true("sCgStruct_xyz Cg_SmartData_Speed;" in smart_c
         and "sCgStruct_xyz Cg_SmartData_Move;" in smart_c,
         f"both declared as instances of it: {smart_c[:1500]}")

    # ...so what each use MEANS lives where that use is built, not in the type
    speed_x = next(line for line in smart_c.splitlines()
                   if "&Cg_SmartData_Speed.x," in line)
    move_x = next(line for line in smart_c.splitlines()
                  if "&Cg_SmartData_Move.x," in line)
    true('"m/s"' in speed_x, f"Speed.x is built with its own unit: {speed_x}")
    true('"m"' in move_x and '"m/s"' not in move_x,
         f"and Move.x with its own: {move_x}")
    table_c = generated("cg_parameter_list.c")
    true("speed along x" in table_c and "offset along x" in table_c,
         "each description is in the parameter table")



def test_enabling_a_field_belongs_to_the_type(work):
    """A field is on or off for every parameter of its type at once.  (Reported.)

    Every parameter of a type is an instance of ONE C typedef, so they cannot
    disagree about which fields there are: switching a field off is an edit of
    the type, and it reaches every use, the typedef and the types file.
    """
    document, api, root = new_project(work)
    a_type(api, "xyz", [{"name": "x", "valueType": "float32_t", "arraySize": 1},
                        {"name": "y", "valueType": "float32_t", "arraySize": 1}])
    for name in ("Speed", "Move"):
        api.add({"parent": "", "kind": "struct"})
        document.update("NewStruct", {"name": name})
        api.use_type({"path": name, "name": "xyz"})

    refused = api.update({"path": "Speed.x", "changes": {"enable": False}})
    equal(refused["ok"], False, "one use cannot switch a field off on its own")
    true("structure type" in (refused.get("message") or ""),
         f"and it says why: {refused.get('message')}")

    answer = api.update_type({"name": "xyz", "changes": {"fields": [
        {"name": "x", "valueType": "float32_t", "arraySize": 1, "enable": False},
        {"name": "y", "valueType": "float32_t", "arraySize": 1}]}})
    equal(answer["ok"], True, f"switching x off in the type: {answer.get('message')}")
    for name in ("Speed", "Move"):
        equal(document.find(f"{name}.x").enable, False, f"{name}.x is off")
        equal(document.find(f"{name}.y").enable, True, f"{name}.y is still on")

    document.save()
    structures = types_file_for(root / "parameter_lists" / "list.xml").read_text(
        encoding="utf-8")
    true('name="x" valueType="float32_t" enable="false"' in structures,
         f"the types file says x is off: {structures}")
    document.load()
    equal(document.find("Move.x").enable, False, "and it is still off after a reload")

    for name in ("Speed", "Move"):
        document.update(f"{name}.y", {"default_value": 0, "minimum": 0,
                                      "maximum": 0, "resolution": 0.1})
    result = document.generate()
    true(result["success"], f"the build: {result.get('message')}")
    types_h = next(pathlib.Path(item) for item in result["files"]
                   if item.endswith("_types.h")).read_text(encoding="utf-8")
    typedef = types_h.split("typedef struct {")[1].split("} sCgStruct_xyz;")[0]
    true(" y;" in typedef and " x;" not in typedef,
         f"the typedef holds y and not x: {typedef}")


def test_a_refused_structure_leaves_nothing(work):
    """Adding a structure is one step: refused, it leaves nothing.  (Reported.)

    The dialog used to make a call per piece.  When a field was refused, an
    empty type had already been declared (TYP007) and trying again said the
    name was taken; when the name was taken, a NewStruct with no type was left
    behind (TYP002).  Undo then walked back through each of those states.
    """
    document, api, _root = new_project(work)
    api.add({"parent": "", "kind": "primitive"})
    document.update("NewParameter", {"name": "Taken"})
    document.save()
    document.load()                   # a clean start: nothing to undo, nothing unsaved

    refusals = [
        ({"name": "Home", "type": "Position",
          "fields": [{"name": "", "valueType": "float64_t"}]}, "needs a name"),
        ({"name": "Taken", "type": "Position", "fields": [dict(F32)]}, "already used"),
        ({"name": "1bad", "type": "Position", "fields": [dict(F32)]}, "valid C identifier"),
        ({"name": "Home", "type": "Position",
          "fields": [dict(F32, valueType="Nowhere")]}, "neither a data type"),
        ({"name": "Home", "type": "Position", "fields": []}, "at least one field"),
        ({"name": "Home", "type": "Position", "fields": [dict(F32), dict(F32)]}, "Two fields"),
        ({"name": "Home", "type": "Missing"}, "no structure type called"),
    ]
    for request, reason in refusals:
        answer = api.add_structure(request)
        equal(answer["ok"], False, f"refused: {request}")
        true(reason in (answer.get("message") or ""),
             f"saying '{reason}': {answer.get('message')}")
        equal([node.name for node in document.model.parameters], ["Taken"],
              f"no parameter is left behind by {request}")
        equal(document.model.struct_types.names(), [],
              f"no type is left behind by {request}")
        equal((document.can_undo, document.dirty), (False, False),
              f"nothing to undo and nothing unsaved after {request}")

    answer = api.add_structure({"name": "Home", "type": "Position", "fields": [dict(F32)]})
    equal(answer["ok"], True, f"the corrected request goes through: {answer.get('message')}")
    equal(answer["selected"], "Home", "and selects the new structure")
    equal([child.name for child in document.find("Home").children], ["Lat"],
          "which has the type's fields")
    equal(document.validate_codes("TYP002") + document.validate_codes("TYP007"), 0,
          "and no type problem")

    api.undo({})
    equal(([node.name for node in document.model.parameters],
           document.model.struct_types.names()), (["Taken"], []),
          "one Undo takes the structure and the type it brought away together")

    # ...and the same for 'New structure type' in the Structure types panel
    refused = api.new_type({"name": "Gps", "fields": [{"name": "Fix", "valueType": ""}]})
    equal(refused["ok"], False, "a type with a field of no data type is not declared")
    equal(document.model.struct_types.names(), [], "and nothing is left of it")
    made = api.new_type({"name": "Gps", "fields": [{"name": "Fix", "valueType": "uint8_t"}]})
    equal(made["ok"], True, f"declared with its fields in one step: {made.get('message')}")
    equal([member.name for member in document.model.struct_types.get("Gps").fields],
          ["Fix"], "fields and all")


def test_deleting_a_structure_keeps_its_type(work):
    """A type goes only when it is deleted in 'Structure types…'.  (Asked for.)

    Deleting a structure used to offer its type along.  A type is a declaration
    of its list, and a structure only one use of it: the type stays, unused, in
    that list, until somebody deletes it where types are deleted.
    """
    document, api, _root = new_project(work)
    a_type(api, "Inner", [dict(F32)])
    a_type(api, "Outer", [{"name": "In", "valueType": "Inner", "arraySize": 1}])
    true(api.add_structure({"name": "Home", "type": "Outer"})["ok"], "Home is added")

    answer = api.delete({"path": "Home", "types": ["Inner", "Outer"]})
    equal(answer["ok"], True, f"Home is deleted: {answer.get('message')}")
    equal(document.model.struct_types.names(), ["Inner", "Outer"],
          "and both types stay - even when a caller still asks for them")

    api.undo({})
    true(document.find("Home") is not None, "one Undo brings Home back")
    api.redo({})

    true(not api.delete_type({"name": "Inner"})["ok"], "Inner is held by Outer, so it stays")
    true(api.delete_type({"name": "Outer"})["ok"], "deleting Outer in the panel works")
    true(api.delete_type({"name": "Inner"})["ok"], "and then Inner")
    equal(document.model.struct_types.names(), [], "which is the one way a type goes")


def test_the_merged_types_file_holds_what_the_project_uses(work):
    """The build's types file is every type the project USES.  (Asked for.)

    Beside the full parameter list the build writes the structure types of the
    whole project.  A type a list declares and nothing uses stays in that list's
    own types file, but it is not one the project uses, so it is not there.
    """
    document, api, root = new_project(work)
    api.add({"parent": "", "kind": "primitive"})
    a_type(api, "Wheel", [{"name": "Rpm", "valueType": "uint16_t", "arraySize": 1}])
    a_type(api, "Axle", [{"name": "Left", "valueType": "Wheel", "arraySize": 1}])
    a_type(api, "Spare", [dict(F32)])
    true(api.add_structure({"name": "Front", "type": "Axle"})["ok"], "Front is added")
    true(api.add_structure({"name": "Gone", "type": "Position",
                            "fields": [dict(F32)]})["ok"], "Gone is added")
    api.delete({"path": "Gone"})

    result = document.generate()
    true(result["success"], f"Generate works: {result.get('message')}")
    # Beside wherever the project's own 'full_parameter_list_file' setting
    # says the merged snapshot goes - never assumed to be one particular
    # folder, which is a project's own setting to change.
    merged = types_file_for(document.config.output.xml_file)
    equal(read_types(merged).names(), ["Axle", "Wheel"],
          "the types in use - Wheel only through Axle - and nothing else")
    equal(read_types(types_file_for(root / "parameter_lists" / "list.xml")).names(),
          ["Axle", "Position", "Spare", "Wheel"],
          "while the list's own file keeps every type it declares")


def test_a_type_nothing_uses_cannot_block_generate(work):
    """A broken type is an error only while the build uses it.  (Reported.)"""
    document, api, _root = new_project(work)
    answer = api.add_structure({"name": "Home", "type": "Position", "fields": [dict(F32)]})
    true(answer["ok"], f"adding Home: {answer.get('message')}")
    api.add({"parent": "", "kind": "primitive"})
    document.update("NewParameter", {"name": "Speed"})

    # broken the way a file edited by hand can be - the editor refuses it now
    document.model.struct_types.get("Position").fields[0].value_type_name = "Nowhere"

    found = [item for item in document.validate() if item["code"] == "TYP013"]
    equal([item["severity"] for item in found], ["error"], "while Home uses it, it is an error")
    equal((found[0]["location"]["structType"], found[0]["location"]["parameter"]),
          ("Position", "Home"), "naming the type and the structure that holds it")

    equal(document.delete("Home"), True, "Home is deleted, its type kept")
    found = [item for item in document.validate() if item["code"] == "TYP013"]
    equal([item["severity"] for item in found], ["warning"],
          "once nothing uses it, the same finding is a warning")
    true("nothing is generated from it" in found[0]["message"],
         f"that says why: {found[0]['message']}")
    equal(found[0]["location"]["parameter"], None, "and it no longer points at a parameter")

    result = document.generate()
    true(result["success"], f"so it does not block Generate: {result.get('message')}")


def test_a_refused_type_edit_changes_nothing(work):
    """A type edit is checked whole before it touches anything.  (Reported.)"""
    document, api, root = new_project(work)
    api.add_structure({"name": "Home", "type": "Position", "fields": [dict(F32)]})
    document.save()
    document.load()

    refused = api.update_type({"name": "Position", "changes": {
        "name": "1bad", "fields": [dict(F32), dict(F32, name="Lon")]}})
    equal(refused["ok"], False, "an invalid new name is refused")
    equal([member.name for member in document.model.struct_types.get("Position").fields],
          ["Lat"], "and the fields that came with it were not written either")
    equal([child.name for child in document.find("Home").children], ["Lat"],
          "nor was the structure reshaped")
    equal((document.can_undo, document.dirty), (False, False), "no undo step, nothing unsaved")

    refused = api.update({"path": "Home.Lat", "changes": {"name": "Other"}})
    equal(refused["ok"], False, "a field's name is its type's")
    equal((document.can_undo, document.dirty), (False, False),
          "and a refused parameter edit leaves no undo step and nothing unsaved either")

    # another list's type is not this list's to edit at all - even a perfectly
    # good edit is refused, and nothing is copied in (it used to be: an edit
    # copied the type into this list, so one name ended up in two lists)
    second = root / "parameter_lists" / "second.xml"
    second.write_text(EMPTY_LIST, encoding="utf-8")
    document.select_lists([str(root / "parameter_lists" / "list.xml"), str(second)])
    document.load(second)
    refused = api.update_type({"name": "Position", "changes": {"fields": [
        dict(F32), dict(F32, name="Lon")]}})
    equal(refused["ok"], False, "another list's type cannot be edited from here")
    equal(document.model.struct_types.names(), [],
          "and Position was not copied into this list")
    equal(document.dirty, False, "which is not marked modified")


def test_a_fields_place_belongs_to_the_type(work):
    """A field cannot be deleted, duplicated, moved or added on its own.  (Reported.)

    A structure's fields are its type's, so each of these was thrown away by the
    next thing that re-applied the type: the deleted field came back, the
    duplicate vanished, and the generated code never had either.
    """
    document, api, _root = new_project(work)
    answer = api.add_structure({"name": "Home", "type": "Position",
                                "fields": [dict(F32), dict(F32, name="Lon")]})
    true(answer["ok"], f"adding Home: {answer.get('message')}")

    for action, request in (("delete", {"path": "Home.Lat"}),
                            ("duplicate", {"path": "Home.Lat"}),
                            ("move", {"path": "Home.Lon", "offset": -1}),
                            ("add", {"parent": "Home", "kind": "primitive"})):
        answer = getattr(api, action)(request)
        equal(answer["ok"], False, f"{action} on a field is refused")
        true("structure type 'Position'" in (answer.get("message") or ""),
             f"{action} says which type the fields belong to: {answer.get('message')}")
    equal([child.name for child in document.find("Home").children], ["Lat", "Lon"],
          "and the structure still has exactly the type's fields")

    answer = api.duplicate({"path": "Home"})
    equal(answer["ok"], True, "the structure itself is still duplicated whole")


def test_the_types_file_was_renamed(work):
    """A list whose types are in the older file reads them, and is moved on.

    The file beside a list is "<list>_types.xml" now; it was
    "<list>_structures.xml".  A list nobody has saved since then still has its
    types in the old file, and those types are its parameters' SHAPE - reading
    only the new name would leave every structure without fields.  Saving
    writes the new name and takes the old file away, so there is never a second
    copy to wonder about.  (Asked for.)
    """
    document, api, root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    true(api.add_structure({"name": "Home", "type": "Position"})["ok"], "Home is added")
    document.save()

    current = root / "parameter_lists" / "list_types.xml"
    older = current.with_name("list_structures.xml")
    true(current.is_file(), "the types are written under the new name")

    current.rename(older)                  # a project written before the rename
    document.load()
    equal(document.model.struct_types.names(), ["Position"],
          "the older file is read when it is the only one there")
    equal([field.name for field in document.find("Home").children], ["Lat"],
          "so the structure still has its shape")

    document.save()
    true(current.is_file(), "saving writes the new name")
    true(not older.is_file(), "and the old file is gone, not left as a second copy")


def _second_list(document, root):
    """A second, empty list in the build, opened."""
    second = root / "parameter_lists" / "second.xml"
    second.write_text(EMPTY_LIST, encoding="utf-8")
    document.select_lists([str(root / "parameter_lists" / "list.xml"), str(second)])
    document.load(second)
    return second


def _rename_on_disk(path, old, new):
    text = path.read_text(encoding="utf-8")
    true(old in text, f"{path.name} holds {old}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_another_lists_type_never_reshapes_this_one(work):
    """A list's structures take their shape from its OWN types.  (Found testing.)

    The editor reshaped the open list by the merged types of the whole build,
    and a merge keeps the first declaration of a name - so when a list earlier
    in the build declared a type of the same name with fewer fields, the first
    edit here dropped the fields it lacked, with their limits and units.
    """
    document, api, root = new_project(work)
    a_type(api, "Position", [dict(F32)])
    document.save()

    second = _second_list(document, root)
    a_type(api, "Place", [dict(F32), dict(F32, name="Lon")])
    true(api.add_structure({"name": "Away", "type": "Place"})["ok"], "Away is added")
    api.update({"path": "Away.Lon", "changes": {"unit": "deg"}})
    document.save()
    # the same name in both lists, the way a hand edit or a copied list has it
    _rename_on_disk(second, 'valueType="Place"', 'valueType="Position"')
    _rename_on_disk(types_file_for(second), 'name="Place"', 'name="Position"')
    document.load(second)

    a_type(api, "Other", [dict(F32)])          # any type edit reshapes the list
    equal([child.name for child in document.find("Away").children], ["Lat", "Lon"],
          "Away keeps both of its own fields")
    equal(document.find("Away.Lon").unit, "deg", "and what its second field says")
    equal(document.validate_codes("TYP016"), 1, "while one name in two lists is an error")


def test_a_list_cannot_use_another_lists_type(work):
    """A structure may only be of a type its own list declares.  (Found testing.)

    The build merged every list's types into one library and checked the
    structures against that, so a list naming a type only another list declared
    passed - and was generated with the other list's typedef.
    """
    document, api, root = new_project(work)
    true(api.add_structure({"name": "Home", "type": "Position",
                            "fields": [dict(F32)]})["ok"], "Home is added")
    document.save()

    second = _second_list(document, root)
    true(api.add_structure({"name": "Away", "type": "Place",
                            "fields": [dict(F32)]})["ok"], "Away is added")
    document.save()
    # a list whose types file did not come along, naming list.xml's type
    types_file_for(second).unlink()
    _rename_on_disk(second, 'valueType="Place"', 'valueType="Position"')
    document.load(second)

    found = [item for item in document.validate() if item["code"] == "TYP017"]
    equal(len(found), 1, "using another list's type is one problem")
    equal(found[0]["severity"], "error", "and an error")
    true("list.xml" in found[0]["message"] and "second.xml" in found[0]["message"],
         f"naming both lists: {found[0]['message']}")
    equal(document.validate_codes("TYP003"), 0, "not also a type nobody has")
    equal(document.generate()["success"], False,
          "and it is not generated with the other list's typedef")


def test_an_unused_type_stays_until_it_is_deleted(work):
    """A type nothing uses any more stays its list's until it is deleted.  (Asked for.)

    Shown in that list's 'Structure types…' only, kept in its types file across
    a save and a reopen, and no error - until somebody deletes it there.
    """
    document, api, root = new_project(work)
    api.add({"parent": "", "kind": "primitive"})
    true(api.add_structure({"name": "Home", "type": "Position",
                            "fields": [dict(F32)]})["ok"], "Home is added")
    document.save()
    true(api.delete({"path": "Home"})["ok"], "Home is deleted, its type kept")
    document.save()
    document.load()

    beside = types_file_for(root / "parameter_lists" / "list.xml")
    equal([(row["name"], row["usedHere"]) for row in api.state({})["structTypes"]],
          [("Position", [])], "still in the list's panel, used by nothing")
    equal(read_types(beside).names(), ["Position"], "and in its types file")
    equal([item["code"] for item in document.validate() if item["severity"] == "error"],
          [], "and nothing about it is an error")

    true(api.delete_type({"name": "Position"})["ok"], "until it is deleted")
    document.save()
    true(not beside.exists(), "which takes it out of the file too")


def test_a_list_with_an_older_types_file_comes_whole(work):
    """A list brought in brings its types from "<list>_structures.xml" too.  (Found testing.)

    Only "<list>_types.xml" was copied, so a list whose types still had the
    older name arrived with every structure naming a type nobody declared.
    """
    first, api, first_root = new_project(work, "first")
    api.add_structure({"name": "Home", "type": "Position", "fields": [dict(F32)]})
    first.save()
    source = first_root / "parameter_lists" / "list.xml"
    types_file_for(source).rename(source.with_name("list_structures.xml"))

    second, api2, _second_root = new_project(work, "second")
    brought = second.add_existing_list(str(source))
    true(types_file_for(brought).is_file(), "its types came along, under the current name")
    second.load(brought)
    equal([row["name"] for row in api2.state({})["structTypes"]], ["Position"],
          "the brought list has its type")
    equal(second.validate_codes("TYP003"), 0, "and its structure is of a type it has")


def test_a_long_name_reaches_the_table_in_full(work):
    """The table header writes every name in full.  (Reported.)

    Its cells were cut at 28 characters with a '~', so a long name reached
    cg_parameter_list_table.h as 'EngineCoolantTemperatureSen~' - in the one
    file meant for looking a parameter up.
    """
    document, api, root = new_project(work)
    api.add({"parent": "", "kind": "primitive"})
    long_value = "EngineCoolantTemperatureSensorReading"
    document.update("NewParameter", {"name": long_value})
    field = dict(F32, name="SecondaryAxisPositionEstimate")
    true(api.add_structure({"name": "VeryLongStructureInstanceName", "type": "Pose",
                            "fields": [field]})["ok"], "the structure is added")

    result = document.generate()
    true(result["success"], f"Generate works: {result.get('message')}")
    table = (root / "cg_parameter_list" / "cg_parameter_list_table.h").read_text(
        encoding="utf-8")
    for name in (long_value, "VeryLongStructureInstanceName.SecondaryAxisPositionEstimate"):
        true(name in table, f"'{name}' is in the table in full")
    true("~" not in table, "and nothing in it is cut short with '~'")


def test_the_table_notes_name_what_is_there(work):
    """The notes under the tables name the columns and fields that exist.  (Reported.)

    The note under the values table explained a '#' column whose heading is
    'Index', and the note under the offsets still sized a value by ArraySize -
    a descriptor field that was removed when one row became one value.
    """
    document, api, root = new_project(work)
    api.add({"parent": "", "kind": "primitive"})
    result = document.generate()
    true(result["success"], f"Generate works: {result.get('message')}")
    table = (root / "cg_parameter_list" / "cg_parameter_list_table.h").read_text(
        encoding="utf-8")

    headings = re.search(r"^\s*\| (Index \|.*)\|\s*$", table, re.M)
    true(headings is not None, "the values table has a heading row")
    named = re.findall(r"^\s*'([^']+)' is the index", table, re.M)
    equal(named, ["Index"], "the note names the index column once, by its heading")
    true(named[0] in [cell.strip() for cell in headings.group(1).split("|")],
         "and that heading is really in the table")
    true("ArraySize" not in table, "no note names the removed ArraySize field")
    true("sizeof(value) * array size" in table, "the offsets note says what a value takes")


CASES = [
    ("one name is one type", test_one_name_one_type),
    ("a parameter cannot be a structure", test_a_parameter_cannot_be_a_structure),
    ("deleting a structure", test_deleting_a_structure),
    ("editing a type reaches every parameter", test_editing_a_type_reaches_every_parameter),
    ("limits belong to the parameter", test_limits_are_the_parameters_own),
    ("renaming a type", test_renaming_a_type),
    ("a type cannot contain itself", test_a_type_cannot_contain_itself),
    ("the types file was renamed", test_the_types_file_was_renamed),
    ("the types file travels with the list", test_the_types_file_travels_with_the_list),
    ("a list opened in another project", test_a_list_from_another_project),
    ("a new structure is never broken", test_a_new_parameter_is_never_a_broken_structure),
    ("a field's shape belongs to its type", test_a_fields_shape_belongs_to_the_type),
    ("deleting a list takes its structures", test_deleting_a_list_takes_its_structures),
    ("a list from elsewhere is copied in", test_a_list_from_elsewhere_is_copied_in),
    ("unit and description belong to the use", test_unit_and_description_belong_to_the_use),
    ("enabling a field belongs to the type", test_enabling_a_field_belongs_to_the_type),
    ("a refused structure leaves nothing", test_a_refused_structure_leaves_nothing),
    ("deleting a structure keeps its type", test_deleting_a_structure_keeps_its_type),
    ("the merged types file holds what the project uses",
     test_the_merged_types_file_holds_what_the_project_uses),
    ("a type nothing uses cannot block Generate", test_a_type_nothing_uses_cannot_block_generate),
    ("a refused type edit changes nothing", test_a_refused_type_edit_changes_nothing),
    ("a field's place belongs to its type", test_a_fields_place_belongs_to_the_type),
    ("another list's type never reshapes this one",
     test_another_lists_type_never_reshapes_this_one),
    ("a list cannot use another list's type", test_a_list_cannot_use_another_lists_type),
    ("an unused type stays until it is deleted", test_an_unused_type_stays_until_it_is_deleted),
    ("a list with an older types file comes whole",
     test_a_list_with_an_older_types_file_comes_whole),
    ("a long name reaches the table in full", test_a_long_name_reaches_the_table_in_full),
    ("the table notes name what is there", test_the_table_notes_name_what_is_there),
]


def main() -> int:
    failures = 0
    for title, case in CASES:
        with tempfile.TemporaryDirectory(prefix="pl_struct_") as raw:
            try:
                case(pathlib.Path(raw))
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
        print(paint(f"{failures} of {len(CASES)} structure case(s) FAILED.",
                    BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} structure cases passed.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
