"""Tests of the editor: the half of the tool that a person actually clicks.

Everything here goes through :class:`pl_gui.api.Api`, which is exactly what the
browser calls, so a test passing here means the button in the toolbar works.
The whole thing runs on a *copy* of the project in a temporary folder, so it can
create files, rewrite the configuration and reorder the build without ever
touching the project the user is working in.

Run it with::

    python tests/run_editor_test.py
"""

from __future__ import annotations

import ast
import copy
import os
import shutil
import re
import sys
import tempfile
from pathlib import Path
from typing import Callable, List, Tuple

#: The app folder: the editor, the generator, the templates, the manuals.
APP_DIR = Path(__file__).resolve().parent.parent
#: The repository root - paramgen/ and the C library beside it - for the whole-tree scans.
ROOT_DIR = APP_DIR.parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen.config import Config          # noqa: E402
from pl_codegen.errors import DiagnosticCollector          # noqa: E402
from pl_codegen.xml_model.xml_reader import read_xml       # noqa: E402
from pl_codegen.xml_model.xml_writer import write_xml      # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,  # noqa: E402
                                            colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils  # noqa: E402
from pl_codegen.app_home import (LEGACY_PROJECT_FILE_NAME, PROJECT_FILE_NAME,
                                 PROJECT_TEMPLATE, copy_lib_into, project_file_in)
from pl_codegen.cli import resolve_config_path
from pl_codegen.model.struct_type import StructTypeLibrary
from pl_codegen.model.tags import TAG_REGISTRY, TagKind
from pl_codegen.xml_model.types_xml import is_types_file, types_file_for
from pl_gui.api import Api
from pl_gui.workspace import Workspace                           # noqa: E402
from pl_gui.document import Document, machine_roots  # noqa: E402
from pl_gui.config_file import rewrite_model_files   # noqa: E402

_logging_utils._colour_enabled = colour_supported()


class Failure(AssertionError):
    """One expectation that did not hold."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise Failure(f"{message}: expected {expected!r}, got {actual!r}")


# --------------------------------------------------------------- the fixture
def open_copy(work: Path, *, empty: bool = False) -> Tuple[Document, Api, Path]:
    """A Document on a throw-away copy of the project.

    With ``empty`` the document is emptied of parameters before the test starts,
    so a case can say exactly what the list contains without depending on what
    the project happens to hold today.  The drop-down lists are kept - a case
    that adds a parameter needs a type and a system name to give it.

    Emptying the open list is *not* enough on its own.  The problems and the
    indices ``Api.state`` reports come from the whole build
    (``merged_model()``), so a parameter somebody happened to save in another
    list would show up in a case that thought it had started from nothing.
    The other lists are therefore emptied on disk as well, which is what makes
    ``empty`` mean empty.
    """
    config_path = _a_project(work / "project")
    _build_from_the_list_folder(config_path)
    document = Document(Config.load(config_path))
    document.load()
    if empty:
        _empty_the_other_lists(document)
        document.model.parameters.clear()
        document.model.struct_types = StructTypeLibrary()

    # The Api works for a workspace - the editor opens one project at a time -
    # so the copy is handed to one directly.  Opening it the ordinary way
    # would put a temp folder into the user's recent-projects list, and it
    # would be gone before they ever saw it.  Its settings file is its own for
    # the same reason: listing the recent projects rewrites the file.
    workspace = Workspace(work / "settings.json")
    workspace.adopt(document)
    return document, Api(workspace), config_path


#: Three small lists, so the cases about several lists have something real to
#: work on.  The first is the one the tests edit.
_FIXTURE_LISTS = ("main", "navigation", "power")


def _a_project(root: Path) -> Path:
    """Build a throw-away project and return its project file.

    Written from scratch every time, in the temp folder the case was given.
    It used to COPY the demo project out of the user's own tree - which meant
    the tests read whatever happened to be in it that day, and one of them
    reached far enough to write into it.  A test must never be able to touch
    somebody's work, and a fixture it builds itself is also the only fixture
    that says, in one place, exactly what the cases are standing on.
    """
    (root / "parameter_lists").mkdir(parents=True, exist_ok=True)
    for name in _FIXTURE_LISTS:
        (root / "parameter_lists" / f"{name}.xml").write_text(
            _FIXTURE_LIST, encoding="utf-8")
    copy_lib_into(root / "lib")

    settings = PROJECT_TEMPLATE.read_text(encoding="utf-8").replace("{{NAME}}", "Fixture")
    settings = settings.replace(
        '"model_files": [],',
        '"model_files": [' + ", ".join(f'"{name}.xml"' for name in _FIXTURE_LISTS) + '],')
    target = root / PROJECT_FILE_NAME
    target.write_text(settings, encoding="utf-8")
    return target


_FIXTURE_LIST = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Parameters>
    <Parameter name="Airspeed" kind="primitive" enable="true" userName="Airspeed"
               type="MONITORING" valueType="float32_t" arraySize="1" unit="m/s"
               logId="100">
      <Source />
      <Limits default="0" minimum="0" maximum="120" resolution="0.01" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Description>How fast the air is going past.</Description>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""


def _build_from_the_list_folder(config_path: Path) -> None:
    """Point the copy's build at the lists in ``parameter_lists/``.

    A test must measure the editor, not the configuration the user happens to
    have open.  Working on one list, at a path of your own choosing, outside the
    list folder, is a supported thing to do - so a suite that asserted "every
    list is in the folder" against the live configuration was reporting the
    user's working state as a failure of the tool.

    The copy is therefore put into the state the project ships in, and the cases
    that care about several lists, or about the folder, have something stable to
    stand on.  The rewrite goes through the same JSONC editor the GUI uses, so
    the comments in the configuration survive - which one of the cases checks.
    """
    lists = sorted(path for path
                   in (config_path.parent / "parameter_lists").glob("*.xml")
                   if not is_types_file(path))
    if lists:
        rewrite_model_files(config_path, [path.name for path in lists])


def _empty_the_other_lists(document: Document) -> None:
    """Strip every list of the build except the open one, on disk."""
    for path in document.config.inputs.model_files:
        if path == document.path or not path.is_file():
            continue
        other = read_xml(path, DiagnosticCollector())
        other.parameters.clear()
        other.struct_types = StructTypeLibrary()
        write_xml(other, path, emit_timestamp=False)


# --------------------------------------------------------------- the cases
def test_structure_types(work: Path) -> None:
    """A structure is OF a type, and editing the type reaches every one of them.

    The old behaviour this replaces: a "type" was a copy, so a parameter built
    from one went its own way the moment it was made.  Now the type owns the
    shape and the parameter owns the limits, and there is a case for each half.
    """
    document, api, _config = open_copy(work, empty=True)

    made = api.new_type({"name": "sPosition"})
    check(made["ok"], f"the type was not declared: {made}")
    check(api.update_type({"name": "sPosition", "changes": {"fields": [
        {"name": "Lat", "valueType": "float64_t", "arraySize": 1},
        {"name": "Samples", "valueType": "int16_t", "arraySize": 4},
    ]}})["ok"], "the type's fields were not set")

    listed = api.state({})["structTypes"]
    equal([item["name"] for item in listed], ["sPosition"], "the type list")
    equal(len(listed[0]["fields"]), 2, "how many fields it has")

    # a structure picks its type from a list holding only structure types
    document.add_parameter("", "struct")
    document.update("NewStruct", {"name": "Target"})
    check(api.use_type({"path": "Target", "name": "sPosition"})["ok"],
          "the type could not be applied")

    target = document.find("Target")
    equal(target.kind.value, "struct", "it is a structure")
    equal([child.name for child in target.children], ["Lat", "Samples"], "the fields")
    check(not target.children[0].unit, "a field starts with no unit: the type has none")
    document.update("Target.Lat", {"unit": "deg"})
    equal(document.find("Target.Lat").unit, "deg",
          "the unit is set on the parameter's own field")
    check(target.param_type is not None, "the parameter keeps its own type")
    check(target.tags.get("SystemName") is not None, "and its own tags")

    # the limits belong to the parameter, not to the type
    document.update("Target.Lat", {"maximum": 45.0})
    equal(document.find("Target").children[0].maximum, 45.0, "the limit was written")
    equal(len(document.find_struct_type("sPosition").fields), 2,
          "and the type is unchanged by it")

    # editing the type reaches the parameter
    check(api.update_type({"name": "sPosition", "changes": {"fields": [
        {"name": "Lat", "valueType": "float64_t", "arraySize": 1},
        {"name": "Alt", "valueType": "float32_t", "arraySize": 1},
        {"name": "Samples", "valueType": "int16_t", "arraySize": 4},
    ]}})["ok"], "the type could not be edited")
    equal([child.name for child in document.find("Target").children],
          ["Lat", "Alt", "Samples"], "the parameter grew the new field, in place")
    equal(document.find("Target.Lat").unit, "deg",
          "and the unit this parameter gave its field survived the type edit")
    equal(document.find("Target.Lat").maximum, 45.0, "and kept the limit it had")

    # the type survives a save and a reload, in the file beside the list
    saved = document.save()
    again = Document(document.config)
    again.load(saved)
    equal(again.model.struct_types.names(), ["sPosition"], "the types after a reload")
    equal([child.name for child in again.find("Target").children],
          ["Lat", "Alt", "Samples"], "and the parameter still has its fields")

    # a type still in use is not deleted, and says so
    refused = api.delete_type({"name": "sPosition"})
    equal(refused["ok"], False, "a type in use was deleted")
    check("still used" in refused["message"], "and it did not say why")

    check(document.delete("Target"), "the parameter was not deleted")
    check(api.delete_type({"name": "sPosition"})["ok"], "an unused type was not removed")
    equal(api.state({})["structTypes"], [], "the type list after removing the only type")


def test_structure_arrays(work: Path) -> None:
    """An array of structures produces one set of values per element."""
    document, _api, _config = open_copy(work, empty=True)

    # A structure is of a TYPE, and the type says what fields it has.
    document.create_struct_type("Wheel")
    document.update_struct_type("Wheel", {"fields": [
        {"name": "Speed", "valueType": "float32_t", "arraySize": 1}]})

    document.add_parameter("", "struct")
    document.update("NewStruct", {"name": "Wheels", "array_size": 3,
                                  # log_id is a field of its own, not a tag
                                  "log_id": 900,
                                  "tags": {"Loggable": True,
                                           "SystemName": "SYS_NAV",
                                           "ParamMode": "PARAM_MODE_USER",
                                           "ResetProof": False, "LogEncryption": False}})
    document.use_struct_type("Wheels", "Wheel")
    document.update("Wheels.Speed",
                    {"minimum": 0, "maximum": 0, "resolution": 0.001, "default_value": 0.0})

    leaves = document.model.flatten()
    equal([leaf.name for leaf in leaves],
          ["Wheels[0].Speed", "Wheels[1].Speed", "Wheels[2].Speed"], "the expanded leaves")
    equal([leaf.log_id for leaf in leaves], [900, 901, 902], "one log id per value")

    # A log id counts values, never bytes: a float32_t[10] takes ten ids, and so
    # would a uint8_t[10].  Every element is a value in its own right - its own
    # row, its own index, its own id - so three struct elements each holding an
    # array of 10 produce thirty values numbered 900..929.
    # The array size of a field is the TYPE's, so this is where it changes -
    # and it changes for every parameter of that type at once.
    document.update_struct_type("Wheel", {"fields": [
        {"name": "Speed", "valueType": "float32_t", "arraySize": 10}]})
    expanded = document.model.flatten()
    equal(len(expanded), 30, "three elements of ten values each")
    equal([leaf.name for leaf in expanded[:2]],
          ["Wheels[0].Speed[0]", "Wheels[0].Speed[1]"], "every element is its own value")
    equal([expanded[0].log_id, expanded[10].log_id, expanded[20].log_id],
          [900, 910, 920], "each struct element starts a block of ten ids")
    equal([leaf.log_id for leaf in expanded], list(range(900, 930)),
          "the ids run without a gap, one per value")

    # 'the next free id' is a property of the whole project, not of this list:
    # the other lists of the build reserve ids too, and an id that is free here
    # but taken in another list is not free.
    free = document.next_free_log_id()
    check(free >= 930, f"the next free id must be past this list's block, got {free}")
    for leaf in document.merged_model().flatten():
        log_id = leaf.log_id
        if isinstance(log_id, int) and not isinstance(log_id, bool):
            check(free > log_id, f"id {free} is not free: '{leaf.name}' already uses {log_id}")


def test_parameter_lists(work: Path) -> None:
    """Creating, choosing and ordering the parameter lists of the project."""
    document, api, config_path = open_copy(work)
    # The file the app makes is plain JSON now, but an older project came with
    # a page of comments and somebody may write a note of their own: a change
    # of lists must never throw them away.
    config_path.write_text(config_path.read_text(encoding="utf-8").replace(
        "{", "{\n  // a note somebody wrote - no button may throw it away", 1),
        encoding="utf-8")
    before = config_path.read_text(encoding="utf-8")
    check("//" in before, "the fixture configuration has no comments to preserve")

    listed = api.lists({})
    equal(Path(listed["directory"]).name, "parameter_lists", "the parameter list folder")
    check(all(item["inFolder"] for item in listed["lists"]),
          "every list of the project should live in the one folder")
    selected = [item["file"] for item in listed["lists"] if item["selected"]]
    check(len(selected) >= 1, "no list takes part in the build")

    # a name is sanitised into something that cannot leave the folder
    answer = api.new_list({"name": "../../gimbal telemetry!"})
    check(answer["ok"], f"the list was not created: {answer}")
    created = Path(answer["path"])
    equal(created.name, "gimbal_telemetry.xml", "the file name made from the typed name")
    equal(created.parent, document.list_directory(), "the new list is in the folder")
    check(created.is_file(), "the new list was not written to disk")
    check(created in document.config.inputs.model_files,
          "the new list did not join the build")

    # a name that is already taken is refused rather than overwriting a list
    check(not api.new_list({"name": "gimbal_telemetry"})["ok"],
          "creating a list twice overwrote the first one")

    # The order chosen here is the order the generator merges in, so the check
    # below needs two lists that actually hold parameters - reversed, so that
    # "the order was kept" cannot pass by accident.
    directory = document.list_directory()
    filled = [path for path in sorted(directory.glob("*.xml"))
              if not is_types_file(path) and _parameter_names(path)]
    check(len(filled) >= 2,
          "the project needs two non-empty parameter lists to test the order with")
    chosen = list(reversed(filled[:2]))
    answer = api.select_lists({"paths": [str(path) for path in chosen]})
    check(answer["ok"], f"the choice was not saved: {answer}")

    after = config_path.read_text(encoding="utf-8")
    check("//" in after, "rewriting the configuration deleted its comments")
    equal([line for line in before.splitlines() if line.strip().startswith("//")],
          [line for line in after.splitlines() if line.strip().startswith("//")],
          "the comments of the configuration file")

    reloaded = Config.load(config_path)
    equal([path.name for path in reloaded.inputs.model_files],
          [path.name for path in chosen],
          "what run_generate.py reads after the editor saved the choice")

    # ... and the indices of the generated code really follow that order: the
    # values of the first list come first, then the values of the second.
    expected = [name for path in chosen for name in _parameter_names(path)]
    document = Document(reloaded)
    document.load(reloaded.inputs.model_files[0])
    equal([leaf.name for leaf in document.merged_model().flatten()], expected,
          "the order of the values in the merged model")


def test_list_selection_edge_cases(work: Path) -> None:
    """The ways a hand-edited configuration can be odd, and what happens then."""
    document, api, config_path = open_copy(work)
    directory = document.list_directory()
    first = document.config.inputs.model_files[0]

    # The same list twice would be merged twice and every name in it would
    # collide with itself; the first mention wins so the chosen order survives.
    answer = api.select_lists({"paths": [str(first), str(directory / "power.xml"),
                                         str(first)]})
    check(answer["ok"], f"the choice was not saved: {answer}")
    equal([Path(p).name for p in answer["paths"]], [first.name, "power.xml"],
          "the duplicate should have been dropped")
    equal([path.name for path in Config.load(config_path).inputs.model_files],
          [first.name, "power.xml"], "what the configuration file says")

    # A configuration that already names a list twice still gives the dialog one
    # row per file - two rows with the same path would bind to the same object.
    document.config.inputs.model_files = [first, first]
    paths = [item["path"] for item in document.known_lists()]
    equal(len(paths), len(set(paths)), "the dialog was given a duplicated row")

    # Generating with a list that is not on disk is reported, not raised: the
    # editor shows that state as "(new)", so it is reachable by just clicking.
    document.config.inputs.model_files = [directory / "does_not_exist.xml"]
    result = api.generate({})
    check(not result["success"], "generating from a missing list reported success")
    check(bool(result.get("message")), "the failure came back with nothing to read")


def test_a_type_belongs_to_its_list(work: Path) -> None:
    """A structure type is its own list's: no other list sees, uses or reuses it.

    It used to be offered in every list, and using it from another list copied
    it in - so one name ended up in two lists' files, and the first of them in
    the build then reshaped the other's structures.  Now it is not offered, a
    second list cannot take its name, and one name in two lists on disk is an
    error naming both, even when both say the same thing.
    """
    document, api, _config = open_copy(work)
    first, other = document.config.inputs.model_files[:2]
    fields = [{"name": "Fix", "valueType": "uint8_t", "arraySize": 1}]
    document.load(other)
    check(api.new_type({"name": "sNavShape", "fields": fields})["ok"],
          "the type was not declared")
    document.save()

    document.load(first)
    names = [item["name"] for item in api.state({})["structTypes"]]
    check("sNavShape" not in names, f"another list's type is not offered here: {names}")
    check(not api.add_structure({"name": "Nav", "type": "sNavShape"})["ok"],
          "a structure here cannot be of another list's type")
    answer = api.new_type({"name": "sNavShape", "fields": fields})
    check(not answer["ok"] and other.stem in answer.get("message", ""),
          f"its name is taken here, and the refusal names the list: {answer}")
    check(not api.delete_type({"name": "sNavShape"})["ok"],
          "nor can it be deleted from here")

    # one name in two lists' files - a hand edit, or a list brought in from
    # somewhere - is an error naming both, although the two are identical
    shutil.copy2(types_file_for(other), types_file_for(first))
    document.load(first)
    clash = [item for item in api.state({})["diagnostics"] if item["code"] == "TYP016"]
    check(len(clash) == 1 and clash[0]["severity"] == "error",
          f"one name in two lists is one error: {clash}")
    check(first.name in clash[0]["message"] and other.name in clash[0]["message"],
          f"naming both lists: {clash[0]['message']}")
    check(not document.generate()["success"], "and nothing is generated until one is renamed")


def _parameter_names(path: Path) -> List[str]:
    """The values one parameter list contributes, in order."""
    from pl_codegen.errors import DiagnosticCollector
    from pl_codegen.xml_model.xml_reader import read_xml

    return [leaf.name for leaf in read_xml(path, DiagnosticCollector()).flatten()]


def test_layout_warning(work: Path) -> None:
    """Generating must say when it moved a value a board may already store.

    The offset of a reset-proof value is positional, so inserting, disabling,
    moving or widening a parameter shifts everything after it - and none of that
    shows up in the generated code.  This is the check that it never happens
    quietly.

    The case builds its own parameters rather than using whatever the project
    holds today.  Every step here has to *generate*, and a project someone is
    halfway through editing may legitimately not - a duplicate name while two
    lists are being merged, say.  Depending on that would turn "your draft has
    an error" into "the memory layout warning is broken", which is a different
    and much more alarming thing to read.
    """
    document, api, _config = open_copy(work, empty=True)

    for name in ("Alpha", "Beta", "Gamma"):
        path = document.add_parameter("", "primitive")
        document.update(path, {"name": name, "user_name": name})
    document.save()

    # the copy carries the project's last build; drop it so the first generate
    # here really is a first build
    previous = document.config.output.xml_file
    if previous.is_file():
        previous.unlink()

    first = api.generate({})
    check(first["success"], f"the first build failed: {first.get('message')}")
    check(first["drift"]["firstRun"], "the very first build has nothing to compare with")

    # generating again without touching anything must be silent
    again = api.generate({})
    check(not again["drift"]["breaksStoredData"], "an unchanged model reported a move")
    equal(again["drift"]["moved"], [], "an unchanged model moved something")

    # ... and moving a parameter to the front must not be
    names = [node.name for node in document.model.parameters]
    check(len(names) >= 2, "the project needs two parameters for this case")
    document.move(names[-1], -(len(names) - 1))
    moved = api.generate({})
    check(moved["success"], "generating after the move failed")
    drift = moved["drift"]
    check(drift["breaksStoredData"],
          "moving a parameter to the front did not warn about the memory layout")
    check(bool(drift["moved"]), "the warning named no parameter")
    check("MOVED" in drift["summary"], f"the summary is not loud enough: {drift['summary']}")
    for entry in drift["moved"]:
        check(entry["old"] != entry["new"],
              f"'{entry['parameter']}' is listed as moved but did not move")

    # Appending to the END of the LAST list in the build changes nothing that
    # already exists - and that is the whole point of the advice the warning
    # gives, so it has to actually hold.
    api.open_file({"path": str(document.config.inputs.model_files[-1])})
    document.add_parameter("", "primitive")
    document.update("NewParameter", {"name": "AppendedAtTheEnd"})
    appended = api.generate({})
    check(appended["success"], "generating after the append failed")
    equal(appended["drift"]["moved"], [],
          "appending at the end of the last list moved something that existed")
    check("AppendedAtTheEnd" in appended["drift"]["added"],
          "the appended parameter was not reported as added")


def test_no_external_dependency(_project: Path) -> None:
    """The tool must run on a machine that has never seen the internet.

    The company machines are offline, so `pip install` is not a step anybody can
    take: an import that is not in the Python standard library does not fail at
    the point where it was added, it fails on somebody else's desk, on the day
    they first open the editor.

    This is checked by reading the imports rather than by trying them, so it
    fails on the machine that ADDED the dependency - which is the only machine
    where fixing it is cheap.
    """
    standard = set(sys.stdlib_module_names)
    ours = {"pl_codegen", "pl_gui", "tests", "setup_environment"}

    offenders = []
    for path in sorted(APP_DIR.rglob("*.py")):
        # docs/ is the manual build. It runs on a developer's machine once a
        # release, not on the offline machines the tool has to work on, so it
        # is allowed the browser driver and the PDF reader it needs.
        if "__pycache__" in path.parts or "docs" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            raise Failure(f"{path.relative_to(APP_DIR)} does not parse: {error}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                if root not in standard and root not in ours:
                    offenders.append(f"{path.relative_to(APP_DIR)}: {name}")

    equal(sorted(set(offenders)), [], "imports that are not in the standard library")


def test_every_pane_redraws(_project: Path) -> None:
    """A mutation must never redraw only half the screen.

    The editor keeps no state of its own: the model is the truth and every pane
    is drawn from it.  ``refresh(true)`` is the one exception - it leaves the
    form on the right alone so that typing is not interrupted mid-word - and it
    is safe ONLY where the action cannot have changed the selected node.

    Ticking Enabled in the tree broke exactly that rule once: the model and the
    tree moved, the form did not, and the two halves of the screen then
    disagreed about the same parameter with nothing to say which was right.

    So: any method that calls ``api.update`` - the one action that changes a
    node's fields - must redraw the form as well.  A DOM test could catch this
    too, but it would need a browser; this reads the source and needs nothing.
    """
    # the real source, not the temporary fixture copy: this reads the code the
    # project ships, and the fixture has no web/ folder
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")

    # Comments are stripped first, or the rule catches the comment that explains
    # the rule - "NOT refresh(true), because ..." reads as a call to it.
    code = re.sub(r"/\*.*?\*/", "", app_js, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)

    # split into methods: "  name(args) {" or "  async name(args) {" at one indent
    methods = re.split(r"\n  (?=(?:async )?[A-Za-z_]\w*\s*\()", code)
    offenders = []
    for body in methods:
        name = re.match(r"(?:async )?([A-Za-z_]\w*)\s*\(", body)
        if not name:
            continue
        if "api.update(" not in body:
            continue
        if re.search(r"refresh\(\s*true\s*\)", body):
            offenders.append(name.group(1))

    equal(offenders, [],
          "methods that change a node but keep the stale form (use refresh(), "
          "not refresh(true))")

    # and the checkbox in the tree has to go through that same update action,
    # rather than poking the model or the DOM behind its back
    bodies = {}
    for body in methods:
        found = re.match(r"(?:async )?([A-Za-z_]\w*)\s*\(", body)
        if found:
            bodies.setdefault(found.group(1), body)

    check("setEnabled" in bodies, "app.js still has a setEnabled method")
    check("api.update(" in bodies["setEnabled"],
          "the tree's Enabled tick goes through the normal update action")

    # The form is allowed to skip its own redraw while somebody is typing in it
    # - it already shows what they typed - but ONLY for a change the form
    # itself made.  The caret can be parked in a box while the reader ticks
    # something in the tree, and that change has to reach the form like any
    # other; getting this wrong is how the two halves of the screen last
    # disagreed.  So exactly one method may raise the flag.
    raisers = sorted(name for name, body in bodies.items()
                     if "editorView.ownEdit = true" in body)
    equal(raisers, ["applyChanges"],
          "methods that let the editor skip its redraw (only the form's own "
          "edits may)")

    editor_js = (APP_DIR / "src" / "pl_gui" / "web" / "editor.js").read_text(encoding="utf-8")
    check("this.ownEdit && this.keepsWhatIsOnScreen()" in editor_js,
          "editor.js must gate the skip on BOTH the flag and where the focus is")

    # and the flag has to be put down again, or the form stops redrawing for
    # good after the first edit
    check("finally" in bodies["applyChanges"]
          and "editorView.ownEdit = false" in bodies["applyChanges"],
          "applyChanges must clear ownEdit in a finally block")


def test_one_name_for_one_thing(_project: Path) -> None:
    """A concept must be called the same thing everywhere.

    Renaming something across a project is the change most likely to be left
    half done: the compiler catches the identifiers, the tests catch the keys,
    and nothing at all catches a heading in a generated comment, a label in a
    dialog, or a sentence in a docstring.  Every one of those was missed once.

    So the banned words are listed here.  If a rename is ever reversed, or a new
    name is chosen, this list is the one place that decides it - and the suite
    says exactly which files still disagree.
    """
    # word that must not appear -> what it is called now, and why
    BANNED = {
        "eParameterListDescriptorGroup": "eParameterType",
        "sParameterListDescriptorTag": "sParameterTag",
        "ePARAMETER_GROUP_": "ePARAMETER_TYPE_",
        "DEFAULT_GROUPS": "DEFAULT_PARAMETER_TYPES",
        "GroupRule": "ParameterTypeRule",
        "COLUMN_GROUPS": "COLUMN_TYPES",
        "data_type_name": "value_type_name",
        "PARAMETER_LIST_OFFSET_": "removed: the offsets are in cg_parameter_list_table.h only",
        "PARAMETER_LIST_SIZE_": "PARAMETER_LIST_TAG_<TAG>_SIZE",
        "TagLogId": "LogId (it is not a tag)",
        "fParameterList_GetLogIdSize": "removed with the LogId offset area",
        "ArraySize;": "removed: one descriptor is one value",
        "DataTypeRule": "ValueTypeRule",
        # the heading of the generated overview table
        '"DataType"': '"ValueType"',
    }
    # the old smart-data macro spelling, before the file_Function_ convention
    for old in ("fSmartDataRead_", "fSmartDataWrite_", "fSmartDataSetMinimum_",
                "fSmartDataGetMaximum_", "fSmartDataUserRead_"):
        BANNED[old] = old.replace("fSmartData", "fSmartData_")

    # The documentation is searched too.  It is the place a stale name survives
    # longest, because nothing compiles it and nobody greps it - and a manual
    # that calls a button by a name it no longer has is worse than no manual.
    searched = []
    for pattern in ("*.py", "*.js", "*.c", "*.h", "*.json", "*.html"):
        searched += [p for p in ROOT_DIR.rglob(pattern)
                     if "__pycache__" not in p.parts and ".dist" not in p.parts]

    offences = []
    for path in searched:
        # this file names the banned words on purpose
        if path.name == "run_editor_test.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # A manual that explains a rename has to name the old thing; those
        # sections are marked, and only those are exempt.
        text = re.sub(r"<!-- HISTORY-BLOCK.*?/HISTORY-BLOCK -->", "", text, flags=re.S)
        for banned, instead in BANNED.items():
            if banned in text:
                offences.append(f"{path.relative_to(ROOT_DIR)}: '{banned}' "
                                f"(now: {instead})")

    equal(sorted(offences), [], "old names still in the source")

    # The manuals name the controls of the editor.  A label that was renamed in
    # index.html and not in the manual sends the reader looking for something
    # that is not on screen, so the two are checked against each other.
    labels = (APP_DIR / "src" / "pl_gui" / "web" / "index.html").read_text(encoding="utf-8")
    grid = (APP_DIR / "src" / "pl_gui" / "web" / "grid.js").read_text(encoding="utf-8")
    for shown, gone in (("Value type", "Data type"),
                        ("Tag ParamMode", "ParamMode column"),
                        ("Structure types…", "Save as a type"),
                        ("Structure type", "the mixed Data type list")):
        if shown in labels or shown in grid:
            continue
        raise Failure(f"the editor no longer shows '{shown}'; the manuals still "
                      f"describe it, so update them and this list together "
                      f"(it replaced '{gone}')")


def test_a_drop_down_opens_the_first_time(_project: Path) -> None:
    """A drop-down opened right after typing in a box stays open.  (Reported.)

    Leaving a box sends it, and the click that opens a drop-down is what leaves
    the box.  The answer came back while the list was open and the whole form
    was rebuilt, list included - so it closed at once, and on some machines
    every list had to be opened twice.  The form now remembers which control
    sent a change: one sent by a text box never rebuilds the form while the
    reader is on another control of it, since a text box changes nothing but
    its own value.  A change sent by a drop-down or a checkbox is still
    redrawn - picking bool_t has to take the range boxes away.

    Seen and fixed in a real browser; this pins the rule down from the source.
    """
    editor_js = (APP_DIR / "src" / "pl_gui" / "web" / "editor.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", editor_js, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)

    keeps = code.split("keepsWhatIsOnScreen() {", 1)
    check(len(keeps) == 2, "editor.js decides in keepsWhatIsOnScreen() whether to keep the form")
    body = keeps[1].split("\n  },", 1)[0]
    check("this.isBeingTypedIn()" in body, "it keeps the form while a box is typed in")
    check("this.isTextBox(this.sentBy)" in body,
          "and while the reader is on another control after a text box sent the change")

    # Every change the form sends records its sender, or the rule above has
    # nothing to go on: onChange is called from send() and from nowhere else.
    equal(code.count("this.onChange("), 1, "the form sends through one place")
    send = code.split("send(from) {", 1)
    check(len(send) == 2 and "this.sentBy = from" in send[1].split("\n  },", 1)[0]
          and "this.onChange(" in send[1].split("\n  },", 1)[0],
          "send() records the sender before it hands the change on")
    check("this.send(input)" in code, "each box and list says it was the sender")


def test_the_first_click_is_never_lost(_project: Path) -> None:
    """A click right after typing in the form does what it says.  (Reported.)

    Pressing the mouse leaves the box, the box sends what it holds, and the
    answer redraws the grid, the Problems panel and the sub list picker -
    usually before the button is let go.  The browser only calls it a click
    when the press and the release land on the same element, so a click on a
    row, a twisty, a link under the table or a problem did nothing; a filter
    box lost the caret it had just been given; an open list closed.  Every one
    of them had to be clicked twice.

    Seen and fixed in a real browser; this pins the rules down from the source.
    """
    web = APP_DIR / "src" / "pl_gui" / "web"

    def code_of(name: str) -> str:
        text = (web / name).read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return re.sub(r"^\s*//.*$", "", text, flags=re.M)

    grid_js, app_js = code_of("grid.js"), code_of("app.js")

    check("function onSteadyClick(container, identify, act)" in grid_js,
          "one helper takes a click from the press and the release")
    helper = grid_js.split("function onSteadyClick(", 1)[1].split("\n}\n", 1)[0]
    check('"mousedown"' in helper and '"mouseup"' in helper and '"click"' not in helper,
          "and never from the browser's 'click', which the redraw swallows")

    init = grid_js.split("  init(element, onSelect, onToggleEnable) {", 1)[1].split("\n  },", 1)[0]
    check("onSteadyClick(element," in init,
          "the grid's rows, twisties and links are clicked on the element every redraw keeps")
    for part in ("[data-toggle-row]", ".grid-foot a[id]", ".grid-row[data-path]",
                 "this.onSelect(value)", "this.toggleRow(value)", "this.followLink(value)"):
        check(part in init, f"the grid's press-and-release knows {part}")
    wire = grid_js.split("  wire(filterBoxes) {", 1)[1].split("\n  },", 1)[0]
    check('row.addEventListener("click"' not in grid_js
          and 'button.addEventListener("click"' not in wire,
          "no row or twisty waits for a 'click' of its own any more")

    render = grid_js.split("  render(nodes, selectedPath, problemPaths) {", 1)[1]
    check("this.drawnTop === top" in render and "this.wire(false)" in render,
          "a redraw keeps the header and the filter boxes when they are what they were")
    check("again.focus()" in render.split("this.wire(true)", 1)[1].split("\n  },", 1)[0],
          "and puts the caret back in its filter box when they are not")

    problems = app_js.split("  paintProblems(diagnostics) {", 1)[1].split("\n  },", 1)[0]
    check('addEventListener("click"' not in problems,
          "a problem row waits for no 'click' of its own")
    check("onSteadyClick(document.getElementById(\"problems\")" in app_js
          and "this.bindProblemRows();" in app_js,
          "the Problems panel is clicked through the same helper, bound once")

    modules = app_js.split("  paintModules(state) {", 1)[1].split("\n  },", 1)[0]
    check("this.drawnModules !== html" in modules,
          "the sub list picker is written again only when its entries change")

    apply = app_js.split("  async applyChanges(changes) {", 1)[1].split("\n  },", 1)[0]
    check("const target = this.selected;" in apply
          and "api.update(target, changes)" in apply
          and "this.selected === target" in apply,
          "an answer that comes back after another row was clicked does not take "
          "the selection back")


def test_a_new_field_starts_with_no_warning(work: Path) -> None:
    """A field starts with the values a new parameter starts with.  (Asked for.)

    A field used to start with nothing at all - no default, no limits, no
    resolution - so a structure of a hundred elements opened with a warning
    on every field, each to be filled in by hand.  Now it starts the way
    '+ Add variable' does: a default of 0 and no range (both limits 0), with
    its type's resolution; a boolean FALSE with 0 / 1 / 1.  A field whose type
    changes has its values brought to the new type, as a parameter's are; a
    field that was there already keeps what it has.
    """
    document, api, _config = open_copy(work, empty=True)
    added = api.add_structure({"name": "Wheels", "type": "sWheel", "fields": [
        {"name": "Speed", "valueType": "float32_t"},
        {"name": "Count", "valueType": "uint16_t", "arraySize": 4},
        {"name": "Ok", "valueType": "bool_t"}]})
    check(added["ok"], f"the structure was not added: {added.get('message')}")
    api.update({"path": "Wheels", "changes": {"array_size": 100}})

    def values(name):
        node = document.find(f"Wheels.{name}")
        return (node.default_value, node.minimum, node.maximum, node.resolution)

    def warned():
        return sorted({item["code"] for item in document.validate()
                       if item["code"].startswith("RNG")})

    equal((values("Speed"), values("Count"), values("Ok")),
          ((0.0, 0.0, 0.0, 0.001), (0, 0, 0, 1), (False, 0, 1, 1)),
          "every field starts with a default, no range and its type's resolution")
    equal(warned(), [], "so a new structure of a hundred elements opens with no warning")

    api.update({"path": "Wheels.Count", "changes": {"minimum": 1, "maximum": 50,
                                                    "default_value": 5}})
    api.update_type({"name": "sWheel", "changes": {"fields": [
        {"name": "Speed", "valueType": "uint8_t"},
        {"name": "Count", "valueType": "uint8_t", "arraySize": 4},
        {"name": "Ok", "valueType": "bool_t"},
        {"name": "Temp", "valueType": "int8_t"}]}})
    equal(values("Temp"), (0, 0, 0, 1), "a field added to the type starts the same way")
    equal(values("Speed"), (0, 0, 0, 1),
          "a field whose type changed holds what the new type can hold")
    equal(values("Count"), (5, 1, 50, 1), "and what somebody wrote, if it still fits, stays")
    equal(warned(), [], "and nothing is warned about")

    # A field read from a file with nothing in it is left as it is: only a
    # field the type has just given a structure starts with values.
    speed = document.find("Wheels.Speed")
    speed.default_value = speed.minimum = speed.maximum = speed.resolution = None
    document.save()
    document.load()
    api.update({"path": "Wheels", "changes": {"description": "Four wheels."}})
    equal(values("Speed"), (None, None, None, None),
          "a field that was there already keeps what it has, even nothing")


def test_changing_the_value_type(work: Path) -> None:
    """Changing the type must leave nothing the new type cannot hold.

    The minimum, the maximum, the resolution and the default value only mean
    anything in terms of the value type, so a type change has to bring them
    along.  Left behind they are not merely untidy - turning a float32_t into a
    bool_t used to keep its 0..120 range, and the boolean form has no minimum
    or maximum box, so the warning that followed could be read and could not be
    acted on from the editor at all.

    Every pair of types is walked here, in both directions, and the model has
    to come out clean each time.
    """
    from pl_codegen.model.types import VALUE_TYPES

    document, api, _config = open_copy(work, empty=True)
    document.add_parameter("", "primitive")
    document.update("NewParameter", {
        "name": "Probe", "param_type": "MONITORING",
        "tags": {"SystemName": "SYS_NAV", "ParamMode": "PARAM_MODE_USER",
                 "ResetProof": False, "Loggable": False, "LogEncryption": False}})

    names = list(VALUE_TYPES)
    for start in names:
        for target in names:
            # a plausible starting point for the first type
            document.update("Probe", {"value_type_name": start})
            if start == "bool_t":
                document.update("Probe", {"default_value": True})
            elif start.startswith("float"):
                # FRACTIONS on purpose: an integer type can hold none of these,
                # and a value merely inside the new type's range is not yet a
                # value it can carry - C would quietly make 10.5 into 10.
                document.update("Probe", {"minimum": -10.5, "maximum": 10.5,
                                          "default_value": 7.25, "resolution": 0.25})
            else:
                document.update("Probe", {"minimum": 0, "maximum": 100,
                                          "default_value": 7, "resolution": 1})

            document.update("Probe", {"value_type_name": target})

            # only what this test is about: an empty user name is a house-style
            # notice and has nothing to do with the type change
            complaints = [item for item in api.state({})["diagnostics"]
                          if str(item.get("location", {}).get("parameter", "")) == "Probe"
                          and item["code"][:3] in ("RNG", "TYP", "VAL")]
            equal([f"{c['code']}: {c['message']}" for c in complaints], [],
                  f"{start} -> {target} left the parameter in a state the editor "
                  f"cannot repair")

            node = document.find("Probe")
            value_type = node.value_type
            if value_type is not None and not value_type.is_float and not value_type.is_bool:
                for field in ("minimum", "maximum", "default_value", "resolution"):
                    value = getattr(node, field)
                    if value is None or isinstance(value, bool):
                        continue
                    check(float(value).is_integer(),
                          f"{start} -> {target} left {field}={value} on an integer type")
            if target == "bool_t":
                equal(isinstance(node.default_value, bool), True,
                      f"{start} -> bool_t left a non-boolean default")
            else:
                check(not isinstance(node.default_value, bool),
                      f"{start} -> {target} left a boolean default on a number")


def test_a_boolean_keeps_its_shape(work: Path) -> None:
    """A boolean must hold 0 / 1 / 1 and a real boolean default, always.

    Its form shows no minimum, maximum or resolution box, so a number written
    into one of those could never be seen and never be corrected.  The values
    were normalised when the TYPE changed, which left two ways in that skipped
    it: an update already in flight when the type became bool_t, and a
    structure converted straight to bool_t.
    """
    document, api, _config = open_copy(work, empty=True)
    document.add_parameter("", "primitive")
    document.update("NewParameter", {
        "name": "Flag", "param_type": "MONITORING",
        "tags": {"SystemName": "SYS_NAV", "ParamMode": "PARAM_MODE_USER",
                 "ResetProof": False, "Loggable": False, "LogEncryption": False}})

    def shape():
        node = document.find("Flag")
        return (node.minimum, node.maximum, node.resolution,
                isinstance(node.default_value, bool))

    document.update("Flag", {"value_type_name": "bool_t"})
    equal(shape(), (0, 1, 1, True), "a fresh boolean")

    # numbers written straight at it, as a stale page would
    document.update("Flag", {"minimum": 100, "maximum": -128,
                             "default_value": -1, "resolution": 0.5})
    equal(shape(), (0, 1, 1, True), "a boolean after nonsense was written at it")

    # A STRUCTURE cannot be turned into a boolean at all now: a structure is
    # of a structure type and holds fields, and the two are kept apart rather
    # than one silently becoming the other.
    document.add_parameter("", "struct")
    document.update("NewStruct", {"name": "Shape"})
    refused = api.update({"path": "Shape", "changes": {"value_type_name": "bool_t"}})
    equal(refused["ok"], False, "a structure was allowed to become a boolean")
    check("structure type" in refused["message"],
          f"the refusal should say what a structure needs: {refused['message']}")
    equal(document.find("Shape").kind.value, "struct", "and it is still a structure")
    check(document.delete("Shape"), "the structure could not be deleted")

    # Errors and warnings only: an info is the tool telling you what it did,
    # not something wrong with the model.
    complaints = [item["code"] for item in api.state({})["diagnostics"]
                  if item["code"][:3] in ("RNG", "TYP", "VAL")
                  and item["severity"] != "info"]
    equal(complaints, [], "a normalised boolean should report nothing")



def test_every_drive_can_be_reached(work: Path) -> None:
    """A project on another drive can be browsed to, opened and created.  (Reported.)

    Walking up from a folder ends at the root of ITS drive - the parent of
    ``C:\\`` is ``C:\\`` - so the dialogs could only ever reach the drive they
    started on.  Somebody whose work is on E: could not open a project and, with
    no box to type a folder into, could not create one either.
    """
    _document, api, config = open_copy(work)

    # -- the backend offers the roots, and both dialogs get them -----------
    roots = machine_roots()
    check(bool(roots), "the machine has at least one root to start from")
    for root in roots:
        check(Path(root).is_dir(), f"'{root}' is offered and is really there")
    if os.name == "nt":
        check(all(len(root) == 3 and root[1:] == ":\\" for root in roots),
              f"on Windows they are drive roots: {roots}")

    projects = api.browse_projects({"directory": str(config.parent)})
    check(projects["ok"], f"browsing was refused: {projects.get('message')}")
    equal(projects["drives"], roots, "the project dialog is told where it may start")

    lists = api.browse({"directory": str(config.parent)})
    check(lists["ok"], f"browsing was refused: {lists.get('message')}")
    equal(lists["drives"], roots, "and so is the parameter-list dialog")

    # -- the walk really does stop at a root, which is why they are needed -
    root = Path(str(config)).anchor
    at_root = api.browse_projects({"directory": root})
    check(at_root["ok"], f"a drive root cannot be listed: {at_root.get('message')}")
    equal(at_root["parent"], "", "there is nothing above a drive root to walk to")

    # -- and a project can be made in a folder that is only typed, not walked
    somewhere = work / "typed" / "not" / "walked" / "to"
    made = api.new_project({"folder": str(somewhere), "name": "Elsewhere",
                            "format": "smart_data"})
    check(made["ok"], f"a typed folder was refused: {made.get('message')}")
    check(Path(made["path"]).is_file(), "and the project file is really there")


def test_the_dialogs_start_where_the_project_is(work: Path) -> None:
    """Open starts at the project, New beside the app, a sub list at the lists.  (Reported.)

    Every Open began one folder ABOVE the project - for a project at F:\\test,
    the root of the drive - and had to be walked down from there each time.
    Now Open starts in the folder the project file is in, New starts beside the
    app (never inside it: the app folder is not written to while anybody
    works), and the sub list dialogs at the project's sub list folder.  The
    system's dialog and the page's own start at the same places.
    """
    from pl_codegen.app_home import APP_DIR as APP
    from pl_gui.api import CHOICES, start_folder

    document, api, config = open_copy(work)
    project, lists = config.parent, document.config.inputs.model_directory
    for what, wanted in (("project", project), ("project-location", APP.parent),
                         ("sub-list", lists), ("sub-list-location", lists)):
        equal(start_folder(api.workspace, what).resolve(), wanted.resolve(),
              f"where the '{what}' dialog starts")

    state = api.state({})
    equal(sorted(state["startFolders"]), sorted(CHOICES), "the page is told every start")
    equal(Path(state["startFolders"]["project"]).resolve(), project.resolve(),
          "and Open's is the project's own folder")
    check(isinstance(state["nativeDialogs"], bool), "and whether the system's dialog is there")

    # The page's own dialogs start at the same places.
    opened = api.browse_projects({"directory": "", "for": "open"})
    equal(Path(opened["directory"]).resolve(), project.resolve(), "in-page Open")
    made = api.browse_projects({"directory": "", "for": "new"})
    equal(Path(made["directory"]).resolve(), APP.parent.resolve(), "in-page New")

    # With no project open and none recent, every dialog starts beside the app:
    # not at a drive root, and not inside the app.
    nothing = Workspace(work / "no_settings.json")
    for what in CHOICES:
        place = start_folder(nothing, what).resolve()
        equal(place, APP.parent.resolve(), f"'{what}' with nothing open")
        check(place != APP.resolve() and APP.resolve() not in place.parents,
              f"'{what}' never starts inside the app")
    equal(Workspace(work / "no_settings.json").recent(), [],
          "and that left no project behind in the recent list")


def test_a_typed_path_is_listed_at_once(work: Path) -> None:
    """Whatever is in a dialog's path box is listed as it is typed.  (Reported.)

    A pasted path showed nothing until Enter, while a click showed the folder at
    once.  The box is now read while it is typed into, so the backend makes
    sense of every half-typed state: a file lists its folder with the file
    picked, a path that is not there lists the nearest folder that is, and a
    path in quotes - Windows' "Copy as path" - is a path.
    """
    document, api, config = open_copy(work)
    project = config.parent
    lists = document.config.inputs.model_directory
    main = lists / "main.xml"

    for name, browse in (("the project dialog", api.browse_projects),
                         ("the sub list dialog", api.browse)):
        answer = browse({"directory": str(lists)})
        check(answer["ok"], f"{name}: a folder is listed: {answer.get('message')}")
        equal((Path(answer["directory"]).resolve(), answer["selected"], answer["missing"]),
              (lists.resolve(), "", ""), f"{name}: a folder is listed as it always was")

        answer = browse({"directory": str(main)})
        equal((Path(answer["directory"]).resolve(), Path(answer["selected"]).resolve()),
              (lists.resolve(), main.resolve()), f"{name}: a file lists its folder, picked")

        typed = project / "not" / "there" / "yet"
        answer = browse({"directory": str(typed)})
        check(answer["ok"], f"{name}: a path not there yet is not an error")
        equal((Path(answer["directory"]).resolve(), answer["missing"]),
              (project.resolve(), str(typed)), f"{name}: the nearest folder that is there")

        answer = browse({"directory": f'"{lists}"'})
        equal(Path(answer["directory"]).resolve(), lists.resolve(),
              f"{name}: a path in quotes is that path")

    # A relative path would be relative to wherever the server runs: it names
    # nothing yet, and is not reported as missing either - "it will be made"
    # would be a promise Create then refuses.
    answer = api.browse_projects({"directory": "parameter_lists", "for": "open"})
    equal((Path(answer["directory"]).resolve(), answer["missing"]), (project.resolve(), ""),
          "a relative path leaves the dialog where it starts")


def test_the_systems_own_dialog(work: Path) -> None:
    """Open and Browse use the system's dialog, and say so when there is none.

    The dialog is shown by a process of its own (native_dialog.py) and can only
    be looked at by a person, so what is tested here is everything around it:
    what the child is asked, what its answers mean, one dialog at a time, the
    switch that turns it off, and - where a desktop is there - that the child
    really can make its window.
    """
    import json
    import subprocess

    from pl_gui import native_dialog

    _document, api, config = open_copy(work)
    equal(api.choose({"what": "nothing"})["ok"], False, "an unknown choice is refused")

    # -- none on this machine: the page is told, and uses its own --------
    real_available, real_run = native_dialog.available, subprocess.run
    try:
        native_dialog.available = lambda: False
        answer = api.choose({"what": "project"})
        check(answer.get("unavailable") and not answer["ok"],
              f"no system dialog is said, not hidden: {answer}")
        equal(api.state({})["nativeDialogs"], False, "and the page knows it before it asks")

        # -- what the child is asked, and what its answers mean ------------
        native_dialog.available = lambda: True
        asked: List[List[str]] = []
        replies = []

        def fake_run(command, **_options):
            asked.append(command)
            return replies.pop(0)

        subprocess.run = fake_run
        chosen = str(config)
        replies.append(subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"path": chosen}) + "\n", stderr=""))
        answer = api.choose({"what": "project"})
        equal((answer["ok"], answer["path"], answer["cancelled"]), (True, chosen, False),
              "the file chosen comes back")
        command = asked[-1]
        equal(command[0], sys.executable, "the dialog runs on this same Python")
        check(command[1].endswith("native_dialog.py"), "as native_dialog.py")
        check(command[2].isascii(), "with a request any console code page can carry")
        request = json.loads(command[2])
        equal((request["kind"], Path(request["start"]).resolve()),
              (native_dialog.KIND_FILE, config.parent.resolve()),
              "a file dialog, opening at the project")
        # every JSON file, not just pl_project.json: a project file may be
        # renamed by its owner (asked for)
        equal(request["filetypes"], [["Project file (JSON)", ["*.json"]]],
              "showing every JSON file")

        replies.append(subprocess.CompletedProcess([], 0, stdout='{"path": ""}\n', stderr=""))
        answer = api.choose({"what": "project-location", "start": str(work / "not" / "yet")})
        equal((answer["ok"], answer["path"], answer["cancelled"]), (True, "", True),
              "Cancel is an answer, not a failure")
        equal(Path(json.loads(asked[-1][2])["start"]).resolve(), work.resolve(),
              "a Location not there yet opens at the nearest folder that is")

        replies.append(subprocess.CompletedProcess(
            [], 1, stdout="", stderr="ModuleNotFoundError: No module named 'tkinter'\n"))
        answer = api.choose({"what": "sub-list"})
        check(answer.get("unavailable"), f"a dialog that could not be shown says so: {answer}")
        check("tkinter" in answer["message"], "and why")

        # -- one at a time ---------------------------------------------------
        native_dialog._one_at_a_time.acquire()
        try:
            answer = api.choose({"what": "project"})
        finally:
            native_dialog._one_at_a_time.release()
        check(answer.get("busy"), f"a second dialog waits for the first: {answer}")
    finally:
        native_dialog.available, subprocess.run = real_available, real_run

    # -- the switch ------------------------------------------------------------
    os.environ[native_dialog.SWITCH] = "0"
    try:
        equal(native_dialog.available(), False, f"{native_dialog.SWITCH}=0 turns it off")
    finally:
        del os.environ[native_dialog.SWITCH]

    # -- the real child, showing nothing: it can make its window here ---------
    if native_dialog.available():
        done = subprocess.run(native_dialog.child_command({"kind": native_dialog.KIND_PROBE}),
                              capture_output=True, text=True, timeout=60)
        equal((done.returncode, done.stdout.strip()), (0, '{"path": ""}'),
              f"the dialog process starts and answers: {done.stderr.strip()}")


def test_the_dialogs_try_the_system_first(_project: Path) -> None:
    """Every Open and Browse tries the system's dialog, and the page's follows its box.

    Read from the source, like the other rules here: the menu, the start screen
    and both sub list buttons go to the system's dialog first and to the page's
    own only when there is none, and each of the page's dialogs is drawn once,
    with a listing that follows its path box - not re-opened for every step.
    """
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", app_js, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    bodies = {}
    for body in re.split(r"\n  (?=(?:async )?[A-Za-z_]\w*\s*\()", code):
        found = re.match(r"(?:async )?([A-Za-z_]\w*)\s*\(", body)
        if found:
            bodies.setdefault(found.group(1), body)

    check('"open-project": () => this.openProjectFlow()' in code
          and 'on("btn-start-open", () => this.openProjectFlow())' in code,
          "Open project, from the menu and the start screen, tries the system's dialog")
    check(re.search(r'"btn-open-list"\)\.addEventListener\("click",\s*\(\) => '
                    r'this\.addExistingSubList\(\)\)', code) is not None,
          "and so does 'Add an existing parameter sub list…'")
    for flow, what, fallback in (("openProjectFlow", '"project"', "this.openProjectDialog()"),
                                 ("addExistingSubList", '"sub-list"', "this.openList()")):
        check(f"this.pickNative({what}" in bodies.get(flow, "")
              and fallback in bodies.get(flow, ""),
              f"{flow} asks the system first and falls back on the page's dialog")
    for dialog, what in (("newProjectDialog", '"project-location"'),
                         ("newList", '"sub-list-location"')):
        check(f"this.pickNative({what}" in bodies.get(dialog, ""),
              f"{dialog} has a Browse… that opens the system's folder dialog")

    check("function liveListing(" in code, "one helper keeps a path box and its listing together")
    listing = code.split("function liveListing(", 1)[1].split("\n}", 1)[0]
    check('addEventListener("input"' in listing and "setTimeout(" in listing,
          "the listing follows the box as it is typed into, without Enter")
    for dialog in ("openProjectDialog", "newProjectDialog", "openList", "newList"):
        body = bodies.get(dialog, "")
        check("liveListing(" in body, f"{dialog} lists through it")
        check(f"this.{dialog}(" not in body, f"{dialog} is drawn once, not re-opened per step")

    index_html = (APP_DIR / "src" / "pl_gui" / "web" / "index.html").read_text(encoding="utf-8")
    check('id="dialog-veil"' in index_html, "the page is veiled while the system's dialog is up")


def test_only_a_project_file_opens(work: Path) -> None:
    """A JSON file that is not a project must not open as one.

    Nothing in a project file is mandatory, so an empty object used to load as
    "a project with all the defaults" - and any JSON file on the machine with
    it.  Opening one made ITS folder the project root, so the next Generate
    would have written the parameter list into somebody's home directory, and
    the only clue was a screenful of "unknown configuration section".
    """
    from pl_codegen.config import Config
    from pl_codegen.errors import CodeGeneratorError

    stranger = work / "not_a_project.json"
    stranger.write_text('{"editor": {"theme": "dark"}, "recent": []}',
                        encoding="utf-8")
    try:
        Config.load(stranger)
    except CodeGeneratorError as error:
        message = str(error)
        assert "not a project file" in message, message
        assert "editor" in message, f"it says what the file does have: {message}"
    else:
        raise AssertionError("a settings file opened as a project")

    # ...and one section is enough to be a project, because a real project file
    # may leave every other section out and take the defaults.
    thin = work / "thin.json"
    thin.write_text('{"project": {"name": "Thin"}}', encoding="utf-8")
    config = Config.load(thin)
    assert config.project.name == "Thin", config.project.name



def test_no_list_no_parameter(work: Path) -> None:
    """A new project has no parameter list, so it has nowhere to keep a parameter.

    Adding one used to work - into memory only.  Save then said "No file name
    given.", and Generate wrote every output file from a parameter that existed
    nowhere on disk, while the command line, reading the same project,
    generated nothing.  In both formats.
    """
    from pl_gui.workspace import Workspace

    for fmt in ("smart_data", "param_table"):
        workspace = Workspace(work / f"settings_{fmt}.json")
        project = workspace.create(work / fmt, "Empty", output_format=fmt)
        workspace.open(project)
        api = Api(workspace)
        document = workspace.document

        check(not document.has_list, f"{fmt}: a new project has a list open")
        equal(api.state({})["file"], "", f"{fmt}: the editor is told there is no list")

        answer = api.add({"parent": "", "kind": "primitive"})
        check(not answer["ok"], f"{fmt}: a parameter was added with no list")
        check("no parameter sub list" in (answer.get("message") or ""),
              f"{fmt}: the refusal says why: {answer}")
        equal(document.model.parameters, [], f"{fmt}: nothing was kept in memory")

        saved = api.save({})
        check(not saved["ok"] and "no parameter sub list" in saved["message"],
              f"{fmt}: save says there is no list: {saved}")

        made = api.new_type({"name": "sThing"})
        check(not made["ok"], f"{fmt}: a structure type was declared with no list")

        result = document.generate()
        check(not result["success"], f"{fmt}: a project with no list generated code")
        codes = [item["code"] for item in result["diagnostics"]]
        check("VAL002" in codes and "VAL001" not in codes,
              f"{fmt}: the build says there is no LIST, not an empty one: {codes}")
        check(not (work / fmt / "cg_parameter_list").exists(),
              f"{fmt}: and not one output file was written")


def test_opening_a_list_already_in_the_build(work: Path) -> None:
    """'Open a parameter list' opens one that is already in the build.  (Reported.)

    It was refused as "already part of the build" - after the dialog's own
    check had thrown "Cannot read properties of undefined (reading 'length')"
    for every real parameter list, because the page read a name, 'templates',
    that the check no longer sends.
    """
    document, api, _config = open_copy(work)
    build = list(document.config.inputs.model_files)
    power = next(path for path in build if path.name == "power.xml")
    folder_before = sorted(item.name for item in power.parent.iterdir())

    verdict = api.inspect_list({"path": str(power)})
    check(verdict["ok"], f"a list of the build is a parameter list: {verdict}")
    check(verdict.get("inBuild") is True, "and the check says it is in the build already")
    for key in ("values", "parameters", "structures", "types", "notes"):
        check(key in verdict, f"the check sends '{key}', which the dialog reads")

    answer = api.add_existing_list({"path": str(power)})
    check(answer["ok"], f"OK on a list already in the build opens it: {answer}")
    check(answer.get("alreadyInBuild") is True, "and says that it only opened it")
    equal(Path(answer["path"]), power, "the list itself, not a copy")
    equal(list(document.config.inputs.model_files), build, "the build is unchanged")
    equal(sorted(item.name for item in power.parent.iterdir()), folder_before,
          "and nothing was copied")


def test_the_merged_view_names_every_rows_list(work: Path) -> None:
    """Every row of the merged view says which list it came from.  (Reported.)

    The List column was blank: the grid gave a top-level row its PARENT's list,
    which a top-level row does not have.  The backend matched rows to lists by
    NAME as well, so the fixture's Airspeed - which is in all three lists -
    named main.xml three times.
    """
    document, api, _config = open_copy(work)
    equal([path.name for path in document.config.inputs.model_files],
          ["main.xml", "navigation.xml", "power.xml"], "the fixture's build")
    check(document.path is not None and document.path.name == "main.xml",
          f"main.xml is the open list: {document.path}")

    api.add({"parent": "", "kind": "primitive"})     # new and unsaved, in main.xml
    tree = api.state({"allLists": True})["tree"]
    equal([(node["path"], node["ownerList"]) for node in tree],
          [("Airspeed", "main.xml"), ("NewParameter", "main.xml"),
           ("Airspeed", "navigation.xml"), ("Airspeed", "power.xml")],
          "every top-level row names its own list - a name in three lists included")


def test_one_file_shape_for_both_formats(work: Path) -> None:
    """A smart-data list is saved with its Address, its userName and its size.

    One list has the same fields whatever project generates from it: the
    address a parameter table uses is in the file (0), the name the ground
    station shows is written userName, and the array size is written size.  A
    file carrying the older spellings - gsName, arraySize - reads exactly the
    same and is written the new way on its next save.
    """
    document, api, _config = open_copy(work)
    node = next(item for item in api.state({})["tree"] if item["path"] == "Airspeed")
    equal(node["userName"], "Airspeed", "the list's user name comes back")
    equal(node["address"], 0, "and an address of 0")

    document.save()
    text = document.path.read_text(encoding="utf-8")
    check('address="0"' in text, f"the address is in a smart-data project's file too: {text[:700]}")
    check('userName="Airspeed"' in text, "the user name is written userName")
    check("gsName" not in text, "and never gsName")
    check('size="1"' in text and "arraySize" not in text,
          f"the array size is written size: {text[:700]}")

    # A file written while those two had their older names opens unchanged.
    legacy = document.path.with_name("older_names.xml")
    legacy.write_text(_FIXTURE_LIST.replace('userName="Airspeed"', 'gsName="Airspeed"'),
                      encoding="utf-8")
    document.load(legacy)
    older = next(item for item in api.state({})["tree"] if item["path"] == "Airspeed")
    equal((older["userName"], older["arraySize"]), ("Airspeed", 1),
          "gsName and arraySize still read")


def test_the_output_names_lists_from_the_project_root(work: Path) -> None:
    """Generated files name their lists from the project's folder.  (Reported.)

    The banner of every generated file listed its input files with the full
    path of the machine that built them - C:\\Users\\... - so the same build
    made on two machines differed in every file, and a project kept in git
    changed each time somebody else generated it.  From the folder of
    pl_project.json a list is 'parameter_lists/main.xml' wherever the project is:
    in the banners, and in the full parameter list, both in <SourceFiles> and
    in every parameter's <Source>.  A list kept outside the folder is reached
    with '..'.
    """
    document, api, config_path = open_copy(work, empty=True)
    path = document.add_parameter("", "primitive")
    document.update(path, {"name": "Alpha", "user_name": "Alpha"})
    document.save()

    outside = work / "shared" / "outside.xml"
    outside.parent.mkdir(parents=True)
    outside.write_text("<?xml version='1.0' encoding='utf-8'?>\n"
                       '<ParameterListModel schemaVersion="1.0">\n'
                       "  <SourceFiles />\n  <Parameters />\n"
                       "</ParameterListModel>\n", encoding="utf-8")
    answer = api.select_lists({"paths": [str(item) for item in
                                         document.config.inputs.model_files]
                                        + [str(outside)]})
    check(answer["ok"], f"the list outside the project was not added: {answer}")

    result = api.generate({})
    check(result["success"], f"the build failed: {result.get('message')}")
    check(bool(result["files"]), "the build wrote no file")
    lists = ["parameter_lists/main.xml", "parameter_lists/navigation.xml",
             "parameter_lists/power.xml", "../shared/outside.xml"]
    machine = {str(config_path.parent), str(document.config.path.parent),
               document.config.path.parent.as_posix()}
    for item in result["files"]:
        text = Path(item).read_text(encoding="utf-8")
        banner = [line.strip(" *") for line in text.splitlines()[:40]]
        first = next((index for index, line in enumerate(banner)
                      if line.startswith("Input file(s)")), None)
        check(first is not None, f"{Path(item).name} has no 'Input file(s)' line")
        named = ([banner[first].split(":", 1)[1].strip()]
                 + banner[first + 1:first + len(lists)])
        equal(named, lists, f"the lists {Path(item).name} names")
        check(not any(folder in text for folder in machine),
              f"{Path(item).name} names this machine's folders")

    full_list = document.config.output.xml_file.read_text(encoding="utf-8")
    for name in lists:
        check(f'<SourceFile path="{name}" />' in full_list,
              f"the full parameter list names '{name}' from the project's folder")
    check('<Source file="parameter_lists/main.xml" />' in full_list,
          "and so does every parameter's <Source>")
    check(not any(folder in full_list for folder in machine),
          f"the full parameter list names this machine's folders: {full_list[:600]}")


def _as_the_form_sends(node: dict) -> dict:
    """Everything editor.js ``collect()`` sends when a box is left untouched.

    As the browser encodes it: a number goes through JavaScript and JSON, which
    write a whole one without its '.0' - so a limit read from the file as 0.0
    comes back as the int 0 - and a tag comes back as the text in its box.
    """
    def number(value):
        return int(value) if isinstance(value, float) and value.is_integer() else value

    tags = {key: value if value is None or isinstance(value, bool) else str(value)
            for key, value in node["tags"].items()}
    return {
        "name": node["name"], "user_name": node["userName"],
        "param_type": node["paramType"], "value_type_name": node["valueType"],
        "array_size": node["arraySize"], "unit": node["unit"], "enable": node["enable"],
        "default_value": number(node["defaultValue"]), "minimum": number(node["minimum"]),
        "maximum": number(node["maximum"]), "resolution": number(node["resolution"]),
        "log_id": node["logId"], "description": node["description"], "tags": tags,
    }


def test_the_unsaved_mark_means_different_from_the_file(work: Path) -> None:
    """The '*' is on exactly while the list differs from its file.  (Asked for.)

    Every edit used to mark a list modified - the one the form sends when a box
    is only left as well - and Undo back to what is on disk kept the mark, so a
    '*' would have called lists unsaved that nobody had changed.  The mark now
    compares the list with its file.
    """
    document, api, _config = open_copy(work)
    state = api.state({})
    equal((state["dirty"], state["fileShown"]), (False, "parameter_lists/main.xml"),
          "a list just opened is clean, and named from the project's folder")

    node = next(item for item in state["tree"] if item["path"] == "Airspeed")
    answer = api.update({"path": "Airspeed", "changes": _as_the_form_sends(node)})
    check(answer["ok"], f"the untouched form was refused: {answer.get('message')}")
    equal((document.dirty, document.can_undo), (False, False),
          "leaving a box untouched is no edit: no '*', nothing to undo")

    api.update({"path": "Airspeed", "changes": {"unit": "km/h"}})
    equal(api.state({})["dirty"], True, "a real edit marks the list")
    api.undo({})
    equal(document.dirty, False, "Undo back to what is on disk takes the mark away")
    api.redo({})
    equal(document.dirty, True, "and Redo puts it back")

    document.save()
    equal(document.dirty, False, "saving takes it away")
    api.undo({})
    equal(document.dirty, True, "Undo after a save is a change against the new file")
    api.redo({})
    equal(document.dirty, False, "and Redo is the file again")

    made = api.new_type({"name": "sMark", "fields": [{"name": "A", "valueType": "uint8_t"}]})
    check(made["ok"], f"the structure type was not declared: {made.get('message')}")
    equal(document.dirty, True, "a new structure type marks the list - its file changes")
    document.save()

    refused = api.update({"path": "Airspeed", "changes": {"value_type_name": "sMark"}})
    equal(refused["ok"], False, "a parameter cannot take a structure type")
    equal(document.dirty, False, "and a refused edit leaves the list as it was saved")

    document.model.defines = copy.deepcopy(document.model.defines)
    document.model.defines.values.setdefault("SYSTEM NAMES", []).append("SYS_MARK_TEST")
    equal(document.dirty, False,
          "the drop-down lists are the machine's, not part of the list's file")


def test_a_value_has_a_description_of_its_own(work: Path) -> None:
    """Each element of an array may say what IT means, and only that.  (Asked for.)

    Every element is the same kind of thing, ``[0]`` included.  The text they
    all fall back to is the DECLARATION's, edited on the row without brackets -
    and editing it there must not overwrite an element somebody has already
    written something for.  (The first version made ``[0]`` be the
    declaration's, which is what the report asked to change.)

    Everything else on the form belongs to the whole array - changing a unit on
    the eighth element changes all of them - and the log id keeps the one rule
    it has always had: the ids of one parameter run one after another.  Typing
    one on an element therefore MOVES the block, so that element gets the
    number typed.
    """
    document, api, _config = open_copy(work)
    api.update({"path": "Airspeed", "changes": {"array_size": 10, "log_id": 45}})
    declaration = document.find("Airspeed")

    # -- the description of one element ------------------------------------
    answer = api.update({"path": "Airspeed[3]",
                         "changes": {"description": "Only the fourth one."}})
    check(answer["ok"], f"the element was refused: {answer.get('message')}")
    equal(answer.get("selected"), "Airspeed[3]",
          "the editor goes on pointing at the element it was on")
    equal(declaration.element_descriptions, {"3": "Only the fourth one."},
          "one override, on the element that was edited")
    said = {leaf.name: leaf.description for leaf in document.model.flatten()}
    equal(said["Airspeed[3]"], "Only the fourth one.", "the fourth value says so")
    equal(said["Airspeed[4]"], "How fast the air is going past.",
          "and the fifth still reads the parameter's")

    # -- [0] is an element like any other ----------------------------------
    api.update({"path": "Airspeed[0]", "changes": {"description": "The first one."}})
    equal(declaration.description, "How fast the air is going past.",
          "editing [0] does NOT write the parameter's description")
    equal(sorted(declaration.element_descriptions), ["0", "3"],
          "it is an override like any other")
    said = {leaf.name: leaf.description for leaf in document.model.flatten()}
    equal(said["Airspeed[1]"], "How fast the air is going past.",
          "so the second value is untouched")

    # -- the parameter's own row is where they all change ------------------
    api.update({"path": "Airspeed", "changes": {"description": "Air speed, per wheel."}})
    said = {leaf.name: leaf.description for leaf in document.model.flatten()}
    equal(said["Airspeed[9]"], "Air speed, per wheel.",
          "editing the declaration reaches every element with nothing of its own")
    equal((said["Airspeed[0]"], said["Airspeed[3]"]),
          ("The first one.", "Only the fourth one."),
          "and leaves the two that were written by hand exactly as they were")

    # -- and saying the same thing hands it back ---------------------------
    api.update({"path": "Airspeed[3]", "changes": {"description": "Air speed, per wheel."}})
    api.update({"path": "Airspeed[0]", "changes": {"description": ""}})
    equal(declaration.element_descriptions, {},
          "a description equal to the parameter's, or an empty one, is no override")

    # -- every other field reaches the whole array -------------------------
    api.update({"path": "Airspeed[7]", "changes": {"unit": "km/h"}})
    equal(declaration.unit, "km/h", "a unit typed on one element is the array's")
    equal({leaf.unit for leaf in document.model.flatten()}, {"km/h"},
          "so all ten values carry it")

    # -- the log id moves the block ----------------------------------------
    answer = api.update({"path": "Airspeed[7]", "changes": {"log_id": 57}})
    check(answer["ok"], f"the log id was refused: {answer.get('message')}")
    equal(declaration.log_id, 50, "57 on the eighth value starts the block at 50")
    ids = [leaf.log_id for leaf in document.model.flatten()]
    equal(ids, list(range(50, 60)), "and the ids of the parameter are consecutive")

    refused = api.update({"path": "Airspeed[7]", "changes": {"log_id": 3}})
    equal(refused["ok"], False, "a block that would start below zero is refused")
    check("7" in (refused.get("message") or ""),
          f"and the message says what the value needs: {refused.get('message')!r}")
    equal(declaration.log_id, 50, "a refused edit changes nothing")


def _texts_agree(api, document) -> None:
    """What the grid shows for every value is what flatten() gives it."""
    generated = {leaf.name: (leaf.user_name or "", leaf.description or "")
                 for leaf in document.model.flatten()}
    shown = {}

    def walk(node):
        for value in node["values"]:
            key = ".".join(re.findall(r"\[(\d+)\]", value["name"]))
            texts = node["rowTexts"][key]
            shown[value["name"]] = (texts["userName"], texts["description"])
        for child in node["children"]:
            walk(child)

    for node in api.state({})["tree"]:
        walk(node)
    equal(shown, generated, "every row of the grid shows what its value is generated with")


def test_a_field_of_a_struct_array_too(work: Path) -> None:
    """A row reaches what is under it, and nothing else.  (Asked for.)

    Wheels[0].Speed and Wheels[1].Speed may read differently, and so may the
    rows above values: Wheels[1] describes everything of the rear wheel and
    nothing of the front one, Wheels[0].Samples the samples of the front wheel
    and no other wheel's, and Wheels all of it.  The nearest row that says
    something wins, so a text written by hand is never overwritten from above.
    The User Name is read the same way (test_a_value_has_a_user_name_of_its_own).

    Every other box on the form belongs to the field, which belongs to the
    structure type and therefore to every element of the array.
    """
    document, api, _config = open_copy(work, empty=True)
    added = api.add_structure({"name": "Wheels", "type": "sWheel",
                               "fields": [{"name": "Speed", "valueType": "float32_t"},
                                          {"name": "Samples", "valueType": "int16_t",
                                           "arraySize": 2}]})
    check(added["ok"], f"the structure was not added: {added.get('message')}")
    path = added["selected"]
    api.update({"path": path, "changes": {"array_size": 2,
                                          "description": "One wheel."}})

    def said():
        return {leaf.name: leaf.description for leaf in document.model.flatten()}

    equal(set(said().values()), {"One wheel."},
          "a field with nothing of its own reads its structure's")

    answer = api.update({"path": f"{path}[1]", "changes": {"description": "The rear wheel."}})
    check(answer["ok"], f"one element of the structure was refused: {answer.get('message')}")
    equal(answer.get("selected"), f"{path}[1]", "the editor stays on that row")
    equal((said()[f"{path}[0].Speed"], said()[f"{path}[1].Speed"],
           said()[f"{path}[1].Samples[1]"]),
          ("One wheel.", "The rear wheel.", "The rear wheel."),
          "one element of the structure describes what is inside it, and nothing else")

    api.update({"path": f"{path}[0].Samples", "changes": {"description": "Front samples."}})
    equal((said()[f"{path}[0].Samples[0]"], said()[f"{path}[0].Samples[1]"],
           said()[f"{path}[1].Samples[0]"], said()[f"{path}[0].Speed"]),
          ("Front samples.", "Front samples.", "The rear wheel.", "One wheel."),
          "the samples of one wheel reach the samples of that wheel only")

    api.update({"path": f"{path}[1].Speed", "changes": {"description": "The rear one."}})
    api.update({"path": path, "changes": {"description": "A wheel."}})
    equal((said()[f"{path}[0].Speed"], said()[f"{path}[1].Speed"],
           said()[f"{path}[1].Samples[0]"], said()[f"{path}[0].Samples[0]"]),
          ("A wheel.", "The rear one.", "The rear wheel.", "Front samples."),
          "the structure reaches what says nothing itself, and nothing written by hand")
    _texts_agree(api, document)

    speed = document.find(f"{path}.Speed")
    api.update({"path": f"{path}[0].Speed", "changes": {"description": "A wheel."}})
    equal(speed.element_descriptions, {"1": "The rear one."},
          "typing what a row reads anyway writes nothing")
    api.update({"path": f"{path}[1].Speed", "changes": {"description": ""}})
    equal(said()[f"{path}[1].Speed"], "The rear wheel.",
          "emptied, the rear speed reads its wheel again")

    api.update({"path": f"{path}[1].Speed", "changes": {"unit": "rpm"}})
    equal({leaf.unit for leaf in document.model.flatten() if leaf.name.endswith("Speed")},
          {"rpm"}, "while a unit typed there belongs to the field, so both wheels take it")

    # The form of a row above values sends every box - the log id among them,
    # which it shows as the structure's own - and that must move nothing.
    wheels = document.find(path)
    wheels.tags["Loggable"], wheels.log_id = True, 40
    before = [leaf.log_id for leaf in document.model.flatten()]
    api.update({"path": f"{path}[1]", "changes": {"log_id": 40, "user_name": "",
                                                   "description": "The rear wheel."}})
    equal(([leaf.log_id for leaf in document.model.flatten()], wheels.log_id),
          (before, 40), "the log ids stay where they were")


def test_an_old_shared_text_goes_onto_every_row(work: Path) -> None:
    """A list written before rows had texts of their own reads the same.  (Asked for.)

    A field of an array of structures used to hold one User Name and one
    description for every element at once.  No row reaches that far any more,
    so on opening the list it goes onto the row of each element - except one
    that already has its own - where it can be seen and changed one by one.
    Every value reads what it read before, so nothing generated changes, and
    opening the list does not mark it modified.
    """
    document, api, _config = open_copy(work, empty=True)
    added = api.add_structure({"name": "Wheels", "type": "sWheel",
                               "fields": [{"name": "Speed", "valueType": "float32_t"},
                                          {"name": "Samples", "valueType": "int16_t",
                                           "arraySize": 2}]})
    path = added["selected"]
    api.update({"path": path, "changes": {"array_size": 3}})
    # what an older editor wrote: one text on the field, for every wheel
    speed = document.find(f"{path}.Speed")
    speed.user_name, speed.description = "Wheel speed", "How fast it turns."
    speed.element_user_names["2"] = "Spare wheel speed"
    document.find(f"{path}.Samples").user_name = "Sample"
    document.save()
    old = {leaf.name: (leaf.user_name, leaf.description)
           for leaf in read_xml(document.path, DiagnosticCollector()).flatten()}

    document.load()
    speed = document.find(f"{path}.Speed")
    equal((speed.user_name, speed.description), (None, None),
          "the field no longer holds a text for every wheel")
    equal(speed.element_user_names,
          {"0": "Wheel speed", "1": "Wheel speed", "2": "Spare wheel speed"},
          "each wheel's row has it, and the one named by hand keeps its own")
    equal(document.find(f"{path}.Samples").element_user_names,
          {"0": "Sample", "1": "Sample", "2": "Sample"},
          "an array field: its row in every wheel")
    equal({leaf.name: (leaf.user_name, leaf.description)
           for leaf in document.model.flatten()}, old,
          "every value reads exactly what it read before")
    check(not api.state({})["dirty"], "and opening the list does not mark it modified")
    _texts_agree(api, document)

    api.update({"path": f"{path}[1].Speed", "changes": {"user_name": "Rear wheel speed"}})
    names = {leaf.name: leaf.user_name for leaf in document.model.flatten()}
    equal((names[f"{path}[0].Speed"], names[f"{path}[1].Speed"]),
          ("Wheel speed", "Rear wheel speed"), "now one wheel's row changes alone")
    document.save()
    document.load()
    equal({leaf.name: leaf.user_name for leaf in document.model.flatten()}, names,
          "and the file keeps it so")

    # A structure that becomes an array hands its fields' texts to each element
    # at once, not only the next time the list is opened.
    added = api.add_structure({"name": "Pose", "type": "sPose",
                               "fields": [{"name": "Lat", "valueType": "float32_t"}]})
    api.update({"path": "Pose.Lat", "changes": {"user_name": "Latitude"}})
    api.update({"path": "Pose", "changes": {"array_size": 2}})
    lat = document.find("Pose.Lat")
    equal((lat.user_name, lat.element_user_names), (None, {"0": "Latitude", "1": "Latitude"}),
          "each element's Lat is called Latitude, one row at a time")


def test_a_value_has_a_user_name_of_its_own(work: Path) -> None:
    """Each value may be called something of its own; written once, it names all.  (Asked for.)

    The User Name follows the description's rule.  The declaration's - the row
    without brackets - is what every element without one of its own reads, so
    writing it once names them all and nothing complains; any element may have
    its own; emptying it, or typing the name it would read anyway, hands it
    back.  A field with no User Name reads its structure's, so a loggable
    structure named once raises no TAG011 per field.  What each value is really
    called reaches the file, the editor and the generated pUserName.
    """
    document, api, _config = open_copy(work, empty=True)

    def names():
        return {leaf.name: leaf.user_name for leaf in document.model.flatten()}

    # -- an array, named once ------------------------------------------------
    api.add({"parent": "", "kind": "primitive"})
    api.update({"path": "NewParameter",
                "changes": {"name": "Cell", "array_size": 4, "user_name": "Cell voltage"}})
    cell = document.find("Cell")
    cell.tags["Loggable"], cell.log_id = True, 10
    equal(set(names().values()), {"Cell voltage"}, "written once, every element reads it")
    equal(document.validate_codes("TAG011"), 0, "and nothing asks for a name per element")

    # -- one element of its own ----------------------------------------------
    answer = api.update({"path": "Cell[2]", "changes": {"user_name": "Cell three"}})
    check(answer["ok"], f"the element's name was refused: {answer.get('message')}")
    equal(answer.get("selected"), "Cell[2]", "the editor stays on the element")
    equal(cell.element_user_names, {"2": "Cell three"}, "one override, on that element")
    equal((names()["Cell[2]"], names()["Cell[3]"]), ("Cell three", "Cell voltage"),
          "it is called its own name, the next one the shared name")
    equal(cell.user_name, "Cell voltage", "and the declaration's name did not change")

    api.update({"path": "Cell[2]", "changes": {"user_name": "Cell voltage"}})
    equal(cell.element_user_names, {}, "typing the shared name hands the element back")
    api.update({"path": "Cell[2]", "changes": {"user_name": "Cell three"}})

    api.update({"path": "Cell", "changes": {"user_name": "Battery cell"}})
    equal((names()["Cell[0]"], names()["Cell[2]"]), ("Battery cell", "Cell three"),
          "renaming the declaration reaches every element but the one named by hand")

    api.update({"path": "Cell", "changes": {"user_name": ""}})
    problems = [item for item in document.validate() if item["code"] == "TAG011"]
    equal(len(problems), 1, "three unnamed loggable elements are ONE problem")
    check("3 of its values" in problems[0]["message"],
          f"which says how many: {problems[0]['message']}")
    api.update({"path": "Cell", "changes": {"user_name": "Battery cell"}})

    # -- a structure names its fields ----------------------------------------
    added = api.add_structure({"name": "Pose", "type": "sPose",
                               "fields": [{"name": "Lat", "valueType": "float32_t"},
                                          {"name": "Lon", "valueType": "float32_t"}]})
    check(added["ok"], f"the structure was not added: {added.get('message')}")
    api.update({"path": "Pose", "changes": {"user_name": "Home position"}})
    pose = document.find("Pose")
    pose.tags["Loggable"], pose.log_id = True, 20
    equal((names()["Pose.Lat"], names()["Pose.Lon"]), ("Home position", "Home position"),
          "a field with no name reads its structure's")
    equal(document.validate_codes("TAG011"), 0, "so a loggable structure named once is enough")

    api.update({"path": "Pose.Lat", "changes": {"user_name": "Latitude"}})
    equal((names()["Pose.Lat"], names()["Pose.Lon"]), ("Latitude", "Home position"),
          "and a field may have its own")

    # -- an array of structures: one value of one element --------------------
    api.update({"path": "Pose", "changes": {"array_size": 2}})
    answer = api.update({"path": "Pose[1].Lon", "changes": {"user_name": "Rear longitude"}})
    check(answer["ok"], f"a field of one element was refused: {answer.get('message')}")
    equal((names()["Pose[0].Lon"], names()["Pose[1].Lon"]),
          ("Home position", "Rear longitude"), "one element's field is called its own name")
    equal(document.find("Pose.Lon").element_user_names, {"1": "Rear longitude"},
          "kept on the field, under that element")
    api.update({"path": "Pose[0].Lon", "changes": {"user_name": "Home position"}})
    equal(document.find("Pose.Lon").element_user_names, {"1": "Rear longitude"},
          "typing the structure's name on a field adds nothing")

    # -- the editor shows each value's own -----------------------------------
    tree = {node["path"]: node for node in api.state({})["tree"]}
    equal([value["userName"] for value in tree["Cell"]["values"]],
          ["Battery cell", "Battery cell", "Cell three", "Battery cell"],
          "every value comes with the name it really has")
    equal((tree["Cell"]["elementUserNames"], tree["Cell"]["sharedUserName"]),
          ({"2": "Cell three"}, "Battery cell"), "and the form knows which are its own")
    lon = next(child for child in tree["Pose"]["children"] if child["name"] == "Lon")
    equal((lon["userName"], lon["sharedUserName"], lon["inheritedUserName"]),
          (None, "Home position", "Home position"),
          "a field with none is told the structure's")

    # -- the file keeps it, and reads it back --------------------------------
    before = names()
    document.save()
    text = document.path.read_text(encoding="utf-8")
    check('<Element at="2" userName="Cell three" />' in text,
          f"an element's own name is saved beside its description: {text[:1500]}")
    document.load()
    equal(names(), before, "and every value is called the same after reading it back")

    # -- and the generated table carries it ----------------------------------
    result = document.generate()
    check(result["success"], f"Generate works: {result.get('message')}")
    code = (document.config.output.code_directory / "cg_parameter_list.c").read_text(
        encoding="utf-8")
    for name in ("Cell three", "Battery cell", "Rear longitude", "Home position", "Latitude"):
        check(f'.pUserName = "{name}",' in code, f"pUserName '{name}' is in the table")
    header = (APP_DIR.parent / "parameter_descriptor" / "parameter_descriptor.h").read_text(
        encoding="utf-8")
    check(header.index("pName;") < header.index("pUserName;")
          < header.index("eParameterType Type;"),
          "the field sits after pName, in the order the initialiser writes it")


def test_the_grid_selects_one_value(_project: Path) -> None:
    """A row that IS a value selects the value; the form knows which one.

    Read out of the sources, because the click that proves it lives in the
    browser.  Three halves have to agree: the row says what it selects, the
    application resolves a value path to the declaration behind it, and the
    form is told which value it is showing.
    """
    web = APP_DIR / "src" / "pl_gui" / "web"
    grid_js = (web / "grid.js").read_text(encoding="utf-8")
    app_js = (web / "app.js").read_text(encoding="utf-8")
    editor_js = (web / "editor.js").read_text(encoding="utf-8")

    check("select: path," in grid_js,
          "every row selects itself - a value, and a row above values such as "
          "Wheels[1] or Wheels[1].Samples, whose texts reach only what is under it")
    check("(node.rowTexts || {})[rowKey(path)]" in grid_js
          and "userName: texts.userName" in grid_js and "desc: texts.description" in grid_js,
          "and shows the texts the backend worked out for that row")
    check("firstRowPath(state.tree, this.selected)" in app_js
          and "valuesUnder(node)" in app_js,
          "a declaration with no row of its own opens its first row, and a row "
          "above values stays selected while a value under it exists")
    check("return row ? `row ${row.dataset.select}` : \"\";" in grid_js
          and "else this.onSelect(value);" in grid_js,
          "and clicking it sends that, not the declaration")
    check('data-select="${escapeHtml(row.select)}"' in grid_js,
          "the row carries it, so reveal() and the highlight can read it")
    check('element.dataset.select === path' in grid_js,
          "reveal() finds an element's own row")

    check("declarationPath" in app_js and "selectedNode(state)" in app_js,
          "the application resolves a value path to its declaration")
    check("editorView.show(node, state, this.selected)" in app_js,
          "and tells the form which value is selected")
    check("btn-duplicate" in app_js and "const element = !!node" in app_js,
          "Duplicate, Delete and Move are switched off on an element")

    check("valueShown(node, selected)" in editor_js,
          "the form works out which value it is showing")
    check('this.area("description", "Description", this.value.description,' in editor_js
          and "this.descriptionField(node)" in editor_js,
          "the Description box holds that row's text, in both forms")
    check("this.value.logId" in editor_js,
          "and the log id box the id that value really got")
    # Reported: the paragraph that used to sit above the form said in five
    # lines what the form already shows, on every single element.
    check("elementNote" not in editor_js and "element-note" not in editor_js,
          "and no banner is pasted above the form")
    # There is no text for the same field of EVERY element any more - a row
    # reaches only what is under it (asked for) - so no button leads to one.
    check("btn-describe-all" not in editor_js,
          "no button leads from an element to a text every element shares")
    check("this.value && this.value.isValue" in editor_js,
          "a row above values shows the structure's log id, not an empty one")


def test_the_dialogs_offer_the_drives(_project: Path) -> None:
    """All three folder dialogs show the drives, and New takes a typed folder."""
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")

    check("function driveRow(" in app_js, "one helper draws the row of drives")
    for dialog in ("open-project-drives", "new-project-drives", "open-list-drives"):
        check(dialog in app_js, f"the dialog using '{dialog}' shows them")
        check(f"#{dialog} [data-drive]" in app_js, f"and '{dialog}' is clickable")

    check('id="new-project-where"' in app_js,
          "New project has a box for a folder that was never walked to")
    check('document.getElementById("new-project-where").value.trim()' in app_js
          and "folderFor(where, name)" in app_js,
          "and what is typed there is where the project is made")
    check("C:\\\\work\\\\my_project" not in app_js,
          "no placeholder implies the work must be on C:")


def test_a_row_put_somewhere_new_is_brought_into_sight(_project: Path) -> None:
    """An action that moves the selection scrolls its row into sight.  (Reported.)

    The grid puts its scroll back after every redraw, which is right for an
    edit and was wrong for '+ Add': a new parameter goes to the end of the
    list, so in a long list it was selected below the visible rows, with the
    form beside it describing a row nobody could see.  Adding, adding a
    structure, duplicating and moving all put the selection somewhere new, so
    each one has to reveal it.  Read from the source, like the redraw rule.
    """
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", app_js, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    methods = re.split(r"\n  (?=(?:async )?[A-Za-z_]\w*\s*\()", code)

    movers = ("api.add(", "api.addStructure(", "api.duplicate(", "api.move(")
    blind = []
    for body in methods:
        name = re.match(r"(?:async )?([A-Za-z_]\w*)\s*\(", body)
        if name and any(call in body for call in movers) \
                and "gridView.reveal(" not in body:
            blind.append(name.group(1))
    equal(blind, [], "methods that put the selection somewhere new and leave it out of sight")

    grid_js = (APP_DIR / "src" / "pl_gui" / "web" / "grid.js").read_text(encoding="utf-8")
    check(re.search(r"\n  reveal\(path\) \{", grid_js) is not None,
          "grid.js has the reveal(path) those methods call")


def test_the_shortcuts_are_bound_to_the_key(_project: Path) -> None:
    """A shortcut is the KEY, not the letter it types.  (Reported.)

    Every shortcut was read off ``event.key``, which is the letter: on a
    Persian layout the S key reports 'س', so Ctrl+S and every other one
    silently did nothing until the layout was switched back.  ``event.code``
    is the key itself and says the same thing on every layout.  Read from the
    source, the way the redraw rule above is.
    """
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    check("event.key.toLowerCase()" not in app_js,
          "a shortcut is still bound to the letter a key types")

    table = re.search(r"SHORTCUTS: \{(.*?)\}", app_js, re.S)
    check(table is not None, "app.js has one table of shortcuts")
    for code in ("KeyS", "KeyG", "KeyN", "KeyD", "KeyZ", "KeyY"):
        check(code in table.group(1), f"{code} is in that table")

    handler = app_js.split("bindShortcuts()", 1)[1].split("async runShortcut", 1)[0]
    check("this.SHORTCUTS[event.code]" in handler, "the handler reads event.code")
    check('classList.contains("hidden")' in handler,
          "a dialog in front of the page takes the keyboard")
    check('typing && (command === "undo"' in handler,
          "undo and redo are left to the box being typed in")
    check("await this.pendingEdit" in app_js,
          "Ctrl+S waits for the box it just left to be sent")
    check("editorView.commit()" in app_js,
          "and asks the form for what it holds, rather than trusting the blur")


def test_the_empty_form_names_the_add_button(_project: Path) -> None:
    """A sentence that points at a button names it the way it is labelled.  (Reported.)

    The empty form said '+ Add' while the button reads '+ Add variable', which
    sends the reader looking for something that is not on screen.  Every
    '+ Add…' the page writes in bold has to be the label of a real button.
    """
    web = APP_DIR / "src" / "pl_gui" / "web"
    index_html = (web / "index.html").read_text(encoding="utf-8")
    app_js = (web / "app.js").read_text(encoding="utf-8")
    editor_js = (web / "editor.js").read_text(encoding="utf-8")

    button = re.search(r'id="btn-add-menu"[^>]*>\s*([^<]*?)\s*▾\s*</button>', index_html)
    check(button is not None, "index.html has the Add button")
    label = button.group(1)
    labels = {label} | set(re.findall(r"<button[^>]*>(\+ Add[^<]*)</button>", app_js))

    for name, text in (("index.html", index_html), ("editor.js", editor_js)):
        for named in re.findall(r"<b>(\+ Add[^<]*)</b>", text):
            check(named in labels,
                  f"{name} points at '{named}', which no button is labelled; "
                  f"the buttons are {sorted(labels)}")
    check(f"<b>{label}</b>" in editor_js, f"the empty form names '{label}'")


def test_a_hint_names_a_button_the_editor_has(_project: Path) -> None:
    """A message that says "press '+ Something'" names a real button.  (Reported.)

    TYPE001 said "make it a structure with '+ Add'" and TYPE002 "build it with
    '+ Structure'", and neither button exists: a structure is added with
    '+ Add variable' > 'User defined…'.  Every '+ …' a message of the tool
    quotes has to be the label of a button the page really draws.
    """
    web = APP_DIR / "src" / "pl_gui" / "web"
    page = "".join((web / name).read_text(encoding="utf-8")
                   for name in ("index.html", "app.js"))
    labels = set(re.findall(r">\s*(\+ [^<▾]*?)\s*▾?\s*</button>", page))
    check("+ Add variable" in labels, f"the buttons are readable: {sorted(labels)}")
    check(">User defined…</button>" in page, "the Add menu still offers 'User defined…'")

    # The messages are read as Python reads them, so a sentence split over two
    # string literals is checked as the one sentence it is.
    for path in sorted((APP_DIR / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            for named in re.findall(r"'(\+ [^']+)'", node.value):
                check(named in labels,
                      f"{path.name} tells the reader to press '{named}', which no "
                      f"button is labelled; the buttons are {sorted(labels)}")


def test_every_door_asks_for_the_same_python(_project: Path) -> None:
    """run.bat, run.sh and the environment check agree on the oldest Python.

    The floor is Python 3.11, and it is written in three places: the two
    launchers and setup_environment.py.  One left behind lets an older Python
    through that door, where the tool then fails with an error that says
    nothing about the version.
    """
    import setup_environment

    floor = setup_environment.MINIMUM_PYTHON
    equal(floor, (3, 11), "the oldest Python the tool supports")
    # On Windows the Python is found by bin\find_python.bat - the first one that
    # really starts, not the first 'python' on the PATH, which can be a broken
    # shortcut (asked for) - and both .bat files use it rather than their own.
    for name in ("bin/find_python.bat", "run.sh"):
        text = (APP_DIR / name).read_text(encoding="utf-8")
        check(f"sys.version_info < ({floor[0]}, {floor[1]})" in text,
              f"{name} refuses a Python older than {floor[0]}.{floor[1]}")
        said = set(re.findall(r"Python (3\.\d+) or newer", text))
        equal(said, {f"{floor[0]}.{floor[1]}"}, f"the Python {name} tells people to install")
    for name in ("run.bat", "bin/set_version.bat"):
        text = (APP_DIR / name).read_text(encoding="utf-8")
        check("find_python.bat" in text, f"{name} finds its Python with find_python.bat")
        bare = [line for line in text.splitlines()
                if re.match(r"\s*python(\.exe)?\s", line, re.IGNORECASE)]
        equal(bare, [], f"{name} never runs a bare 'python'")


def test_an_old_python_is_told_in_red(_project: Path) -> None:
    """'Check this PC' says, in red, that a Python older than 3.11 cannot run the tool.

    It used to be one plain line among the [ok]s, easy to read past - and an old
    Python is the one finding that means nothing at all will work.  So it is
    red, and nothing after it is checked.  The machine running this test is new
    enough, so the floor is raised above it for the length of the test.
    """
    import contextlib
    import io

    import setup_environment
    from pl_codegen.logging_utils import BRIGHT_RED, RESET

    floor = setup_environment.MINIMUM_PYTHON
    checked: List[str] = []
    real_modules = setup_environment.check_standard_modules
    real_argv = sys.argv
    setup_environment.MINIMUM_PYTHON = (sys.version_info[0], sys.version_info[1] + 1)
    setup_environment.check_standard_modules = lambda: checked.append("modules") or True
    try:
        shown = io.StringIO()
        with contextlib.redirect_stdout(shown):
            ok = setup_environment.check_python_version(colour=True)
        lines = [line for line in shown.getvalue().splitlines() if line.strip()]
        check(not ok, "a Python below the floor is refused")
        check(lines and "ERROR: Python" in lines[0], f"and it says so: {lines}")
        equal([line for line in lines if BRIGHT_RED not in line or not line.endswith(RESET)],
              [], "every line of the refusal is red")

        plain = io.StringIO()
        with contextlib.redirect_stdout(plain):
            setup_environment.check_python_version(colour=False)
        check("\033[" not in plain.getvalue(), "no escape codes where there is no console")

        sys.argv = ["run_setup.py"]
        with contextlib.redirect_stdout(io.StringIO()):
            code = setup_environment.main()
        check(code != 0, "the check ends in failure")
        equal(checked, [], "and nothing after the version is checked")
    finally:
        setup_environment.MINIMUM_PYTHON = floor
        setup_environment.check_standard_modules = real_modules
        sys.argv = real_argv


def test_the_sub_lists_are_numbered_from_one(_project: Path) -> None:
    """The 'Parameter sub lists' dialog numbers the build from #1.  (Reported.)

    It showed #0 for the first sub list - an index, where a person counts.
    Only the number shown changes: the arrows still work on the 0-based index.
    """
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    check('<span class="count">#${index + 1}</span>' in app_js,
          "the first sub list in the build is shown as #1")
    check('<span class="count">#${index}</span>' not in app_js, "and none as #0")
    check('data-up ${index === 0 ? "disabled" : ""}' in app_js,
          "while the arrows keep working on the 0-based index")


def test_the_address_column_comes_before_the_description(_project: Path) -> None:
    """The Address column sits after the tags, and a hidden column stays hidden.

    Both reported together: Address had been dropped in the middle of the tag
    columns, and the Description heading had another one drawn on top of it.
    The second was a 0px column - List outside the merged view, Address outside
    a parameter table - whose HEADING was not clipped, so it spilled over the
    next one and made the whole header look reordered.
    """
    grid_js = (APP_DIR / "src" / "pl_gui" / "web" / "grid.js").read_text(encoding="utf-8")
    block = grid_js.split("columns: [", 1)[1].split("  ],", 1)[0]
    keys = re.findall(r'\{ key: "(\w+)"', block)
    check("address" in keys and "desc" in keys, f"the columns are readable: {keys}")
    equal(keys[keys.index("address") + 1], "desc",
          f"Address is the column before Description: {keys}")
    equal([key for key in keys if key.startswith(("system", "mode", "reset", "log", "crypt"))
           and keys.index(key) > keys.index("address")], [],
          "and every tag column is before it, not around it")

    style = (APP_DIR / "src" / "pl_gui" / "web" / "style.css").read_text(encoding="utf-8")
    heading = style.split(".grid-head {", 1)[1].split("}", 1)[0]
    check("overflow: hidden" in heading,
          "a 0px column's heading is clipped, or it paints over the next column")
    check('column.width !== "0px"' in grid_js,
          "and a 0px column is left out of the table, padding and all")
    check("kind" not in keys,
          f"what a variable holds is ONE column, not Kind plus Value type: {keys}")


def test_a_project_file_with_the_old_name_still_opens(work: Path) -> None:
    """A project written before the rename opens exactly as it did.  (Asked for.)

    The project file is called ``pl_project.json`` now: inside a firmware tree
    full of other people's files, ``project.json`` said nothing about whose
    project it was.  Everything that turns a FOLDER into a project file takes
    either name, so a project nobody has renamed still opens - from the editor
    and from the command line - and a folder holding both takes the new one.
    """
    config_path = _a_project(work / "old")
    _build_from_the_list_folder(config_path)
    legacy = config_path.with_name(LEGACY_PROJECT_FILE_NAME)
    config_path.rename(legacy)

    found = project_file_in(legacy.parent)
    equal(found.name, LEGACY_PROJECT_FILE_NAME, "the folder's old project file is found")
    document = Document(Config.load(found))
    document.load()
    _empty_the_other_lists(document)
    check(document.generate()["success"], "and the project still generates")
    equal(resolve_config_path(legacy.parent).name, LEGACY_PROJECT_FILE_NAME,
          "the command line finds it too")

    # A folder holding both is a project that has been renamed and still has
    # its old file: the new name is the one that counts.
    legacy.with_name(PROJECT_FILE_NAME).write_text(legacy.read_text(encoding="utf-8"),
                                                   encoding="utf-8")
    equal(project_file_in(legacy.parent).name, PROJECT_FILE_NAME,
          "with both there, the new name wins")
    equal(resolve_config_path(legacy.parent).name, PROJECT_FILE_NAME,
          "for the command line as well")


def test_nothing_replaces_the_open_list_in_silence(_project: Path) -> None:
    """Opening something else asks first, while the list has unsaved changes.

    Switching to another list, opening another project, reloading, making a
    list, adding an existing one: each replaces what is open, and each of them
    threw unsaved work away without a word.  They ask through one helper now.
    Read from the source, like the other rules here.

    'removeList' is the exception, on purpose: what it reopens something after
    is the list that has just been deleted, so there is nothing left to save.
    """
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", app_js, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    methods = re.split(r"\n  (?=(?:async )?[A-Za-z_]\w*\s*\()", code)

    opens = ("api.open(", "api.openProject(", "api.closeProject(", "api.newList(")
    silent = []
    for body in methods:
        name = re.match(r"(?:async )?([A-Za-z_]\w*)\s*\(", body)
        if not name or name.group(1) == "removeList":
            continue
        if any(call in body for call in opens) and "mayLeaveTheList(" not in body:
            silent.append(name.group(1))
    equal(silent, [],
          "methods that replace the open list without asking about unsaved work")
    check("confirm(" in app_js.split("mayLeaveTheList(question)", 1)[1][:400],
          "and that one helper is the thing that asks")


def test_a_problem_in_another_list_can_be_reached(_project: Path) -> None:
    """A problem row opens the list it belongs to.  (Reported.)

    The check runs over every list of the build at once, so the panel shows
    what is wrong in lists that are not open - and clicking one of those did
    nothing at all, because the parameter it names is not in the list on
    screen.  Each row now carries the file it came from, and the click opens
    that list (asking first, like everything else that replaces what is open)
    and selects the row there.
    """
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    check("data-file=" in app_js, "a problem row says which file it is in")
    check("async goToProblem(" in app_js, "and there is something to take you there")

    handler = app_js.split("async goToProblem(", 1)[1].split("\n  },", 1)[0]
    for wanted in ("api.open(", "mayLeaveTheList(", "gridView.reveal("):
        check(wanted in handler, f"opening the other list goes through {wanted}")
    check("samePath(" in handler,
          "and two spellings of one path count as the same file")


def test_the_messages_name_this_machines_launcher(work: Path) -> None:
    """Whatever tells somebody how to start the tool names the launcher they have.

    run.bat on Windows, ./run.sh everywhere else.  The environment check told a
    Linux user to double-click run.bat and to type 'python run.py' - which only
    works from inside bin/, and on most Linux machines not at all: they have
    python3.  Both systems are tried here, whichever one this is.
    """
    import contextlib
    import io
    import subprocess

    import pl_codegen.app_home as app_home
    import setup_environment

    for launcher, other in (("run.bat", "./run.sh"), ("./run.sh", "run.bat")):
        shipped, app_home.LAUNCHER = app_home.LAUNCHER, launcher
        try:
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                setup_environment._print_footer()
        finally:
            app_home.LAUNCHER = shipped
        text = said.getvalue()
        check(f"{launcher} editor" in text, f"the check names {launcher}:\n{text}")
        check(other not in text and "python run.py" not in text,
              f"and nothing a {launcher} machine cannot run:\n{text}")

    # the launcher this machine is told about is one the app ships ...
    check((APP_DIR / Path(app_home.LAUNCHER).name).is_file(),
          f"{app_home.LAUNCHER} is in the app folder")
    # ... the menu's own --help says it ...
    shown = subprocess.run([sys.executable, str(APP_DIR / "bin" / "run.py"), "--help"],
                           capture_output=True, text=True).stdout
    check(f"{app_home.LAUNCHER} generate --check" in shown
          and "python run.py" not in shown, f"run.py --help names the launcher:\n{shown}")
    # ... and the editor's page is told it rather than naming one itself
    _document, api, _config = open_copy(work)
    equal(api.state({})["tool"]["launcher"], app_home.LAUNCHER,
          "the launcher the page is told")
    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", app_js, flags=re.S)
    check("run.bat" not in code and "run.sh" not in code,
          "app.js names no launcher of its own; it shows state.tool.launcher")


def test_every_browser_path_can_exist(_project: Path) -> None:
    """Every place the editor looks for a browser is a place a browser can be.

    The three macOS paths once read "Google Chrome.pl_app/...": renaming the
    tool's own "app" folder to "pl_app" swept through them too, so a Mac never
    found a browser and the editor always opened as a plain tab.  A macOS
    program is a bundle whose name ends in ".app", and no browser's path has
    anything to do with this tool's folders.
    """
    from pl_gui.browser import BROWSER_PATHS

    wrong = [path for path in BROWSER_PATHS["darwin"]
             if not re.fullmatch(r"/Applications/[^/]+\.app/Contents/MacOS/[^/]+", path)]
    wrong += [path for paths in BROWSER_PATHS.values() for path in paths
              if "pl_app" in path]
    equal(wrong, [], "browser paths that no machine has")


def test_the_browser_can_always_write_its_errors(work: Path) -> None:
    """A browser that writes a lot of errors never hangs the editor's window.

    Its error output went to a pipe that nothing read once the window was up.
    A pipe holds 64 KB on Linux, and Chrome on Linux writes to stderr freely:
    past that, its next write blocked, and the window with it.  A stand-in
    browser here writes 300 KB of errors, then leaves a mark - it has to get
    that far, on either system.
    """
    import time

    import pl_gui.server as server

    mark = work / "wrote-everything"
    stand_in = ("import pathlib, sys, time\n"
                "time.sleep(2.5)\n"
                "sys.stderr.write('x' * 300 * 1024)\n"
                "sys.stderr.flush()\n"
                f"pathlib.Path({str(mark)!r}).write_text('done')\n"
                "time.sleep(1)\n")
    kept = server.find_browser, server.app_window_command
    server.find_browser = lambda: sys.executable
    server.app_window_command = lambda browser, url, profile: [browser, "-c", stand_in]
    try:
        gui = server.GuiServer(None, port=8765)
        check(gui._open_app_window(str(work)), "a browser still running counts as opened")
        give_up = time.time() + 20
        while not mark.exists() and time.time() < give_up:
            time.sleep(0.2)
    finally:
        server.find_browser, server.app_window_command = kept
    check(mark.exists(), "a browser writing 300 KB of errors was blocked")


def test_no_browser_says_so(work: Path) -> None:
    """With no browser to start, the editor says so and names the address.

    It said "opened in the default browser" whatever had happened, so on a
    machine with no browser at all (no desktop, WSL) the console claimed
    success while nothing appeared, and never said where the editor was.
    """
    import logging

    import pl_gui.server as server
    from pl_codegen.logging_utils import get_logger

    said: List[logging.LogRecord] = []
    catcher = logging.Handler()
    catcher.emit = said.append                     # type: ignore[assignment]
    logger = get_logger()
    level = logger.level
    kept = server.find_browser, server.webbrowser.open
    server.find_browser = lambda: None
    server.webbrowser.open = lambda url, *args, **kwargs: False
    logger.addHandler(catcher)
    logger.setLevel(logging.INFO)
    try:
        gui = server.GuiServer(None, port=8765)
        gui._open(True, str(work))
    finally:
        server.find_browser, server.webbrowser.open = kept
        logger.removeHandler(catcher)
        logger.setLevel(level)

    lines = [record.getMessage() for record in said]
    check(not any("opened in the default browser" in line for line in lines),
          f"it does not claim a browser it never started: {lines}")
    check(any(gui.url in record.getMessage() and record.levelno >= logging.WARNING
              for record in said),
          f"it names the address to open by hand: {lines}")


def test_a_workspace_keeps_to_its_own_settings_file(work: Path) -> None:
    """A workspace given a settings file of its own writes that one and no other.

    It took the file and used the app's anyway, so every test that opened a
    project wrote a temp folder into the user's paramgen/var/settings.json - and
    emptied their recent list whenever a project on it was not on disk.
    """
    import json

    from pl_codegen.app_home import SETTINGS_FILE, resolve_recent_entry

    before = SETTINGS_FILE.read_bytes() if SETTINGS_FILE.is_file() else None
    own = work / "own_settings.json"
    workspace = Workspace(own)
    project = workspace.create(work / "p", "P")
    workspace.open(project)
    workspace.recent()
    workspace.close()
    after = SETTINGS_FILE.read_bytes() if SETTINGS_FILE.is_file() else None
    recorded = json.loads(own.read_text(encoding="utf-8")).get("recent") if own.is_file() else []
    resolved = [str(resolve_recent_entry(item)) for item in (recorded or [])]
    check(str(project.resolve()) in resolved,
          f"the workspace's own file records the project: {recorded}")
    check(after == before, "and the app's settings file was not touched")


def test_a_recent_entry_works_on_any_system(work: Path) -> None:
    """The recent list names a project the same way on Windows and on Linux.

    The settings file goes into git with the app, so the entry one machine
    writes is read on the next.  It was written with Windows backslashes,
    which Linux reads as part of a file name: the project was never found
    there, and the entry was dropped from the list as a dead one.
    """
    import json

    own = work / "own_settings.json"
    workspace = Workspace(own)
    project = workspace.create(work / "p", "P")
    workspace.open(project)
    workspace.close()
    recorded = json.loads(own.read_text(encoding="utf-8"))["recent"]
    check(recorded and "\\" not in recorded[0],
          f"the entry is written with forward slashes: {recorded}")

    # What the app wrote on Windows before: the same entry, with backslashes.
    backslashed = recorded[0].replace("/", "\\")
    own.write_text(json.dumps({"recent": [backslashed], "current": backslashed}),
                   encoding="utf-8")
    again = Workspace(own)
    equal([row["path"] for row in again.recent()], [str(project.resolve())],
          "an entry written with backslashes still names the project")
    again.open(project)
    again.close()
    equal(json.loads(own.read_text(encoding="utf-8"))["recent"], recorded,
          "and opening the project again replaces that entry instead of adding one")


def test_the_project_file_is_plain_json(work: Path) -> None:
    """A project file the app writes opens in any JSON editor without an error.

    It used to be JSONC - a page of // comments and trailing commas, every one
    of them an error to a JSON editor - and the editor's own rewrite of the list
    array left a trailing comma behind even in a file with no comments at all.
    """
    import json

    def plain(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise Failure(f"{path.name} is not plain JSON: {error}")

    plain(PROJECT_TEMPLATE)
    workspace = Workspace(work / "settings.json")
    project = workspace.create(work / "p", "Plain")
    equal(plain(project)["project"]["name"], "Plain", "a new project is plain JSON")

    workspace.open(project)
    api = Api(workspace)
    for name in ("first", "second"):
        check(api.new_list({"name": name})["ok"], f"list {name} was not made")
    equal(plain(project)["inputs"]["model_files"], ["first.xml", "second.xml"],
          "and stays plain JSON when the editor writes the lists into it")

    table = workspace.create(work / "t", "Table", "param_table")
    equal(plain(table)["output"]["format"], "param_table",
          "a parameter-table project too, with its format set")


def test_a_free_tag_takes_a_number(work: Path) -> None:
    """A number typed into Tag1..Tag4 is a number, as it is read from the file.  (Asked for.)

    The box is text, so '7' arrived as the text '7', and the free-tag rule - a
    number or a C identifier - reported it as neither.  Only in the editor: the
    build read the saved file, got the number 7 and passed.
    """
    document, api, _config = open_copy(work)
    free = [spec.tag_id for spec in TAG_REGISTRY if spec.kind is TagKind.FREE]
    wanted = {tag_id: number for number, tag_id in enumerate(free, start=7)}

    def send(tag_id: str, text: str) -> None:
        node = next(item for item in api.state({})["tree"] if item["name"] == "Airspeed")
        changes = _as_the_form_sends(node)
        changes["tags"][tag_id] = text
        check(api.update({"path": "Airspeed", "changes": changes})["ok"],
              f"{tag_id} = {text!r} was refused")

    for tag_id, number in wanted.items():
        send(tag_id, str(number))
    problems = [item["message"] for item in api.state({})["diagnostics"]
                if item["code"] == "TAG005"]
    check(not problems, f"a number in a free tag is no problem: {problems}")
    equal({tag_id: document.find("Airspeed").tags[tag_id] for tag_id in free}, wanted,
          "the free tags hold numbers")

    api.save({})
    check(not api.state({})["dirty"], "saved, the list is not marked modified")
    read_back = read_xml(document.path, DiagnosticCollector()).parameters[0].tags
    equal({tag_id: read_back[tag_id] for tag_id in free}, wanted,
          "and the file gives the same numbers back")

    send("Tag1", "not one")
    check(any(item["code"] == "TAG005" for item in api.state({})["diagnostics"]),
          "text that is neither a number nor an identifier is still reported")


def test_the_grid_finds_a_rows_values_in_its_own_entry(_project: Path) -> None:
    """The Index cell reads the values of its own top level entry only.

    A name is unique in one sub list only, so the merged view may hold two
    'NewParameter's.  The grid used to gather the values of the whole tree and
    pick a row's by name - and the second one showed the first one's index.
    The backend's numbers are checked in run_paramtable_test.py; this is the
    half that lives in the browser.
    """
    grid_js = (APP_DIR / "src" / "pl_gui" / "web" / "grid.js").read_text(encoding="utf-8")
    rows = grid_js[grid_js.index("  rows(nodes) {"):grid_js.index("  matches(row) {")]
    check("this.valueIndex(nodes)" not in rows,
          "the rows no longer look a value up in the whole tree")
    check(re.search(r"for \(const node of nodes\) \{\s*all = this\.valueIndex\(\[node\]\);"
                    r"\s*walk\(node,", rows) is not None,
          "each top level entry is drawn with its own values")


def test_a_copy_is_named_like_a_copy(work: Path) -> None:
    """Duplicate names the copy the way a file manager does, in C: Name_Copy, Name_Copy2.

    It used to put a 2 on the end of whatever it copied, so copying Speed2 made
    Speed22, and copying that made Speed222.  A copy of a copy counts on from
    the same original instead.  (Asked for.)
    """
    document, api, _config = open_copy(work, empty=True)
    for name in ("Speed", "Motor1"):
        api.add({"parent": "", "kind": "primitive"})
        api.update({"path": "NewParameter", "changes": {"name": name}})

    def copy(path: str) -> str:
        answer = api.duplicate({"path": path})
        check(answer["ok"], f"{path} was not duplicated: {answer.get('message')}")
        return answer["selected"]

    equal(copy("Speed"), "Speed_Copy", "the first copy")
    equal(copy("Speed"), "Speed_Copy2", "the second copy of the same parameter")
    equal(copy("Speed_Copy"), "Speed_Copy3", "a copy of a copy counts on: not Speed_Copy_Copy")
    equal(copy("Speed_Copy3"), "Speed_Copy4", "and never piles numbers up: not Speed_Copy32")
    equal(copy("Motor1"), "Motor1_Copy", "a number in the name is part of the name")
    check(api.delete({"path": "Speed_Copy"})["ok"], "Speed_Copy was not deleted")
    equal(copy("Speed_Copy4"), "Speed_Copy", "a name that is free again is used again")
    equal(document.validate_codes("NAME001") + document.validate_codes("NAME003"), 0,
          "every copy has a valid name of its own")


def test_a_smart_data_project_has_no_param_mode(work: Path) -> None:
    """In a smart-data project the access mode is PARAM_MODE_NONE and cannot be changed.  (Asked for.)

    The form shows it read-only and the generated code writes it for every
    parameter - but the sub list keeps what it says, because a parameter-table
    project building the same list writes the mode into ADD_PARAM.
    """
    document, api, _config = open_copy(work)
    _empty_the_other_lists(document)
    state = api.state({})
    equal(state["fixedTags"], {"ParamMode": "PARAM_MODE_NONE"},
          "the page is told which tag is fixed")
    node = next(item for item in state["tree"] if item["name"] == "Airspeed")
    equal(node["tags"]["ParamMode"], "PARAM_MODE_NONE", "the grid and the form show NONE")
    equal(document.find("Airspeed").tags["ParamMode"], "PARAM_MODE_USER",
          "the list keeps its own mode")

    # the form sends no mode at all; a page left open from before might send one
    changes = _as_the_form_sends(node)
    changes["tags"].pop("ParamMode", None)
    check(api.update({"path": "Airspeed", "changes": changes})["ok"], "the edit was refused")
    equal(document.find("Airspeed").tags.get("ParamMode"), "PARAM_MODE_USER",
          "an edit without the mode keeps it")
    changes["tags"]["ParamMode"] = "PARAM_MODE_FACTORY"
    check(api.update({"path": "Airspeed", "changes": changes})["ok"], "the edit was refused")
    equal(document.find("Airspeed").tags.get("ParamMode"), "PARAM_MODE_USER",
          "and one that sends a mode cannot change it")

    api.add({"parent": "", "kind": "primitive"})
    equal(document.find("NewParameter").tags["ParamMode"], "PARAM_MODE_NONE",
          "a new parameter is saved with NONE")
    equal(document.validate_codes("TAG003") + document.validate_codes("TAG001"), 0,
          "NONE is a valid mode and nothing is missing")

    result = document.generate()
    check(result["success"], f"the build: {result['message']}")
    source = next(Path(path) for path in result["files"]
                  if Path(path).name == "cg_parameter_list.c")
    text = source.read_text(encoding="utf-8")
    equal(text.count(".TagParamMode = (uint32_t)PARAM_MODE_NONE,"), 2,
          "the code gives both parameters NONE")
    check("(uint32_t)PARAM_MODE_USER" not in text, "and nothing else")

    read_back = {item.name: item.tags.get("ParamMode")
                 for item in read_xml(document.path, DiagnosticCollector()).parameters}
    equal(read_back, {"Airspeed": "PARAM_MODE_USER", "NewParameter": "PARAM_MODE_NONE"},
          "the file keeps what each parameter said")


def test_the_lists_are_numbered_defines(work: Path) -> None:
    """System names and parameter modes are #defines with any number, written #ifndef.  (Asked for.)

    They were two enums, numbered by their place in the list - and the
    firmware defines SYS_NAV itself.  The dialog takes 'NAME = number'; a line
    without a number takes the one after the line above it.
    """
    import pl_codegen.choices as choices
    real = choices.CHOICES_FILE
    # the machine's own list is never written by a test
    choices.CHOICES_FILE = work / "choices.json"
    try:
        document, api, _config = open_copy(work)
        _empty_the_other_lists(document)
        answer = api.set_defines({"list": "systemNames", "values": [
            "SYS_UNKNOWN = 0", "SYS_NAV = 16", "SYS_NEXT", "SYS_ALL = 0xFF", "", "SYS_LAST"]})
        check(answer["ok"], f"the list was refused: {answer.get('message')}")
        equal(api.state({})["defineNumbers"]["systemNames"],
              [["SYS_UNKNOWN", 0], ["SYS_NAV", 16], ["SYS_NEXT", 17],
               ["SYS_ALL", 255], ["SYS_LAST", 256]],
              "a line without a number takes the one after the line above")
        equal(choices.load_choices().numbered("SYSTEM NAMES"),
              document.model.defines.numbered("SYSTEM NAMES"), "the file keeps the numbers")

        for line in ("SYS_BAD = abc", "= 5", "SYS_BAD = -2147483649", "SYS_BAD = -0x80000001",
                     "SYS_BAD = 0x100000000"):
            answer = api.set_defines({"list": "systemNames", "values": ["SYS_NAV", line]})
            check(not answer["ok"] and answer.get("message"), f"{line!r} was not refused")
        equal(document.model.defines.number_of("SYSTEM NAMES", "SYS_NAV"), 16,
              "a refused list changes nothing")

        result = document.generate()
        check(result["success"], f"the build: {result['message']}")
        header = next(Path(path) for path in result["files"]
                      if Path(path).name == "cg_parameter_list_defines.h"
                      ).read_text(encoding="utf-8")
        check("typedef enum" not in header and "eParameterListSystemName" not in header,
              "no enum is generated any more")
        check(re.search(r"#ifndef SYS_NAV\n#define SYS_NAV +\(16U\)\n#endif\n", header),
              "SYS_NAV is #defined as 16, only #ifndef")
        check(re.search(r"#define SYS_ALL +\(255U\)", header), "SYS_ALL is 255")
        check(re.search(r"#ifndef PARAM_MODE_NONE\n#define PARAM_MODE_NONE +\(0U\)", header),
              "the parameter modes are defines too")

        api.set_defines({"list": "systemNames", "values": [
            "SYS_UNKNOWN = 0", "SYS_NAV = 16", "SYS_GPS = 16"]})
        clash = [item["message"] for item in api.state({})["diagnostics"]
                 if item["code"] == "DEF005"]
        equal(len(clash), 1, "two names with one number are one error")
        check("SYS_NAV" in clash[0] and "SYS_GPS" in clash[0], f"it names both: {clash}")
        check(not document.generate()["success"], "and nothing is generated")
    finally:
        choices.CHOICES_FILE = real


def test_a_list_number_can_be_negative(work: Path) -> None:
    """A system name or a parameter mode may be given a negative number.  (Asked for.)

    The dialog refused anything below 0, because the tag holding it is a
    uint32_t.  A negative number fits those 32 bits as well - as far as an
    int32_t goes - and its #define says it as written: (-5).
    """
    import pl_codegen.choices as choices
    real = choices.CHOICES_FILE
    # the machine's own list is never written by a test
    choices.CHOICES_FILE = work / "choices.json"
    try:
        document, api, _config = open_copy(work)
        _empty_the_other_lists(document)
        answer = api.set_defines({"list": "systemNames", "values": [
            "SYS_UNKNOWN = 0", "SYS_TEST = -5", "SYS_NEXT", "SYS_LOW = -0x80000000",
            "SYS_NAV = 16"]})
        check(answer["ok"], f"the negative numbers were refused: {answer.get('message')}")
        answer = api.set_defines({"list": "paramModes", "values": [
            "PARAM_MODE_NONE = -1", "PARAM_MODE_USER = 1"]})
        check(answer["ok"], f"a negative mode was refused: {answer.get('message')}")
        equal(api.state({})["defineNumbers"]["systemNames"],
              [["SYS_UNKNOWN", 0], ["SYS_TEST", -5], ["SYS_NEXT", -4],
               ["SYS_LOW", -2147483648], ["SYS_NAV", 16]],
              "a line without a number takes the one after a negative one too")
        equal(choices.load_choices().numbered("PARAM MODES"),
              [("PARAM_MODE_NONE", -1), ("PARAM_MODE_USER", 1)],
              "the file keeps the negative numbers")
        equal(document.validate_codes("DEF006") + document.validate_codes("DEF005"), 0,
              "a negative number is valid")

        result = document.generate()
        check(result["success"], f"the build: {result['message']}")
        header = next(Path(path) for path in result["files"]
                      if Path(path).name == "cg_parameter_list_defines.h"
                      ).read_text(encoding="utf-8")
        check(re.search(r"#ifndef SYS_TEST\n#define SYS_TEST +\(-5\)\n#endif\n", header),
              "SYS_TEST is #defined as -5, no U")
        check(re.search(r"#define SYS_NEXT +\(-4\)\n", header), "SYS_NEXT is -4")
        check(re.search(r"#define SYS_LOW +\(-2147483647 - 1\)\n", header),
              "the smallest one is written so that it is an int")
        check(re.search(r"#define PARAM_MODE_NONE +\(-1\)\n", header), "a mode can be -1")
        check(re.search(r"#define SYS_NAV +\(16U\)\n", header), "the others are as before")

        # -1 and 0xFFFFFFFF are the same 32 bits in the tag
        api.set_defines({"list": "systemNames", "values": [
            "SYS_UNKNOWN = 0", "SYS_NAV = -1", "SYS_GPS = 0xFFFFFFFF"]})
        clash = [item["message"] for item in api.state({})["diagnostics"]
                 if item["code"] == "DEF005"]
        equal(len(clash), 1, "-1 and 0xFFFFFFFF clash")
        check("SYS_NAV" in clash[0] and "SYS_GPS" in clash[0] and "0xFFFFFFFF" in clash[0],
              f"it names both and says why: {clash}")
    finally:
        choices.CHOICES_FILE = real


def test_the_title_names_the_project_file(work: Path) -> None:
    """The window title is the project file's full path and the editor's name.  (Asked for.)

    It used to name the open sub list as well, worked out on the page from the
    list of sub lists, and with several sub lists it sometimes named another
    one.  Now it is what the server says the project file is - with a '*' in
    front while the open sub list is unsaved (asked for too) - and nothing else.
    """
    _document, api, config_path = open_copy(work)
    project = api.state({})["project"]
    check(Path(project["file"]).is_absolute(), f"a full path: {project['file']}")
    equal(Path(project["file"]).resolve(), config_path.resolve(), "the project file")

    app_js = (APP_DIR / "src" / "pl_gui" / "web" / "app.js").read_text(encoding="utf-8")
    body = re.search(r"\n  windowTitle\(state\) \{\n(.*?)\n  \},", app_js, re.DOTALL)
    check(body is not None, "app.js has windowTitle()")
    check("state.project.file" in body.group(1) and "APP_TITLE" in body.group(1),
          "the title is the project file and the editor's name")
    check('state.dirty ? "*"' in body.group(1), "with a '*' while unsaved")
    for guess in ("modules", "fileShown", "name"):
        check(guess not in body.group(1), f"the title does not use '{guess}'")


def test_a_renamed_project_file_opens(work: Path) -> None:
    """A project file may be called anything: it is a project by what it holds.  (Asked for.)

    Opening was tied to the NAME pl_project.json - the system's Open dialog
    showed only that name, a folder was opened through it, and so was
    'run.bat generate' run from a project folder.  Renaming the file lost the
    project to all three.
    """
    from pl_codegen.app_home import is_project_file
    from pl_gui.api import CHOICES
    from pl_codegen.errors import CodeGeneratorError

    _document, api, config_path = open_copy(work)
    folder = config_path.parent
    renamed = folder / "flight_computer.json"
    config_path.rename(renamed)
    (folder / "notes.json").write_text('{"todo": []}', encoding="utf-8")

    check(is_project_file(renamed), "a renamed project file is a project file")
    check(not is_project_file(folder / "notes.json"), "a JSON file of something else is not")

    workspace = Workspace(work / "settings.json")
    equal(workspace.open(renamed).config.path, renamed.resolve(), "it opens by its file")
    equal(workspace.open(folder).config.path, renamed.resolve(),
          "and by its folder - the one project file there")
    equal(resolve_config_path(folder), renamed, "the command line finds it too")

    patterns = [pattern for _label, found in CHOICES["project"][2] for pattern in found]
    equal(patterns, ["*.json"], "the system's Open dialog shows every JSON file")

    listing = api.browse_projects({"directory": str(folder), "for": "open"})
    marked = {item["name"]: item["isProject"] for item in listing["files"]}
    equal((marked.get("flight_computer.json"), marked.get("notes.json")), (True, False),
          "the page's dialog marks the project file by what it holds")
    above = api.browse_projects({"directory": str(folder.parent), "for": "open"})
    check(any(item["isProject"] for item in above["folders"]
              if item["name"] == folder.name), "and the folder as holding a project")

    shutil.copy(renamed, folder / "second.json")
    try:
        workspace.open(folder)
    except CodeGeneratorError as error:
        check("flight_computer.json" in str(error) and "second.json" in str(error),
              f"two project files are both named: {error}")
    else:
        raise Failure("a folder with two project files opened one of them in silence")
    try:
        workspace.create(folder, "Again")
    except FileExistsError as error:
        check("flight_computer.json" in str(error), f"it names what is there: {error}")
    else:
        raise Failure("'New' wrote another project into a project's folder")
    check(not (folder / "pl_project.json").exists(), "and nothing was written")


CASES: List[Tuple[str, Callable[[Path], None]]] = [
    ("structure types (the template library)", test_structure_types),
    ("arrays of structures", test_structure_arrays),
    ("the parameter lists of the project", test_parameter_lists),
    ("odd list selections", test_list_selection_edge_cases),
    ("a type belongs to its own list", test_a_type_belongs_to_its_list),
    ("the memory layout warning", test_layout_warning),
    ("no external dependency", test_no_external_dependency),
    ("every pane redraws after a change", test_every_pane_redraws),
    ("one name for one thing", test_one_name_for_one_thing),
    ("a drop-down opens the first time", test_a_drop_down_opens_the_first_time),
    ("the first click is never lost", test_the_first_click_is_never_lost),
    ("a new field starts with no warning", test_a_new_field_starts_with_no_warning),
    ("changing the value type", test_changing_the_value_type),
    ("a boolean keeps its shape", test_a_boolean_keeps_its_shape),
    ("only a project file opens", test_only_a_project_file_opens),
    ("no list, no parameter", test_no_list_no_parameter),
    ("opening a list already in the build", test_opening_a_list_already_in_the_build),
    ("the merged view names every row's list", test_the_merged_view_names_every_rows_list),
    ("one file shape for both formats", test_one_file_shape_for_both_formats),
    ("the output names lists from the project root",
     test_the_output_names_lists_from_the_project_root),
    ("the unsaved mark means different from the file",
     test_the_unsaved_mark_means_different_from_the_file),
    ("a row put somewhere new is brought into sight",
     test_a_row_put_somewhere_new_is_brought_into_sight),
    ("the shortcuts are bound to the key, not the letter",
     test_the_shortcuts_are_bound_to_the_key),
    ("the empty form names the Add button as it is labelled",
     test_the_empty_form_names_the_add_button),
    ("a hint names a button the editor has",
     test_a_hint_names_a_button_the_editor_has),
    ("every door asks for the same Python", test_every_door_asks_for_the_same_python),
    ("an old Python is told so, in red", test_an_old_python_is_told_in_red),
    ("the sub lists are numbered from 1", test_the_sub_lists_are_numbered_from_one),
    ("the Address column comes before the description",
     test_the_address_column_comes_before_the_description),
    ("a project file with the old name still opens",
     test_a_project_file_with_the_old_name_still_opens),
    ("nothing replaces the open list in silence",
     test_nothing_replaces_the_open_list_in_silence),
    ("a problem in another list can be reached",
     test_a_problem_in_another_list_can_be_reached),
    ("a value has a description of its own",
     test_a_value_has_a_description_of_its_own),
    ("a field of a struct array too", test_a_field_of_a_struct_array_too),
    ("an old shared text goes onto every row", test_an_old_shared_text_goes_onto_every_row),
    ("a value has a user name of its own", test_a_value_has_a_user_name_of_its_own),
    ("the grid selects one value", test_the_grid_selects_one_value),
    ("the grid finds a row's values in its own entry",
     test_the_grid_finds_a_rows_values_in_its_own_entry),
    ("the messages name this machine's launcher",
     test_the_messages_name_this_machines_launcher),
    ("every browser path can exist", test_every_browser_path_can_exist),
    ("the browser can always write its errors",
     test_the_browser_can_always_write_its_errors),
    ("no browser says so", test_no_browser_says_so),
    ("a workspace keeps to its own settings file",
     test_a_workspace_keeps_to_its_own_settings_file),
    ("a recent entry works on any system", test_a_recent_entry_works_on_any_system),
    ("the project file is plain JSON", test_the_project_file_is_plain_json),
    ("a free tag takes a number", test_a_free_tag_takes_a_number),
    ("a copy is named like a copy", test_a_copy_is_named_like_a_copy),
    ("a smart-data project has no param mode", test_a_smart_data_project_has_no_param_mode),
    ("the lists are numbered defines", test_the_lists_are_numbered_defines),
    ("a list number can be negative", test_a_list_number_can_be_negative),
    ("the title names the project file", test_the_title_names_the_project_file),
    ("a renamed project file opens", test_a_renamed_project_file_opens),
    ("every drive can be reached", test_every_drive_can_be_reached),
    ("the dialogs start where the project is", test_the_dialogs_start_where_the_project_is),
    ("a typed path is listed at once", test_a_typed_path_is_listed_at_once),
    ("the system's own dialog", test_the_systems_own_dialog),
    ("the dialogs try the system's first", test_the_dialogs_try_the_system_first),
    ("the dialogs offer the drives", test_the_dialogs_offer_the_drives),
]


def main() -> int:
    failures = 0
    width = max(len(name) for name, _case in CASES)
    for name, case in CASES:
        with tempfile.TemporaryDirectory(prefix="pl_editor_test_") as raw:
            try:
                case(Path(raw))
            except Failure as error:
                print(f"  [{paint('FAIL', BOLD + BRIGHT_RED)}] "
                      f"{name.ljust(width)}  {paint(str(error), BRIGHT_RED)}")
                failures += 1
                continue
            except Exception as error:               # noqa: BLE001 - report and go on
                print(f"  [ERROR] {name.ljust(width)}  {type(error).__name__}: {error}")
                failures += 1
                continue
        print(f"  [{paint('PASS', GREEN)}] {name}")

    print()
    if failures:
        print(paint(f"{failures} of {len(CASES)} editor case(s) FAILED.",
                    BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} editor cases passed.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
