"""The Project settings dialog: the project file, read and changed from the editor.

The project file can be changed from three places - this dialog, the
Parameter sublists dialog and a text editor - so what is checked here is
mostly that they never disagree and never lose anything:

  * every setting is shown as the file has it, and a missing key as the value
    a build really uses;
  * Apply writes only what was changed, in place: every other key, every
    comment, the line endings and the layout stay as they were;
  * a change is refused - with nothing written - when the value cannot be used,
    when the file changed on disk after the dialog read it, or while the open
    sublist has unsaved changes;
  * Apply reloads the project from the file, so the editor, the generator and
    the sublists dialog all go on from the same text.

Run it with::

    python tests/run_project_settings_test.py
"""

import json
import pathlib
import shutil
import sys
import tempfile
import traceback

APP = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "src"))

from pl_codegen.app_home import PROJECT_TEMPLATE                     # noqa: E402
import pl_codegen.choices as choices                                 # noqa: E402
from pl_codegen.config import Config, load_jsonc                     # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,       # noqa: E402
                                      colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils                    # noqa: E402
from pl_gui.api import Api                                           # noqa: E402
from pl_gui.project_settings import SETTINGS                         # noqa: E402
from pl_gui.workspace import Workspace                               # noqa: E402
import pl_gui.workspace as workspace_module                          # noqa: E402

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

#: A project written by hand, the way older ones were: comments, a trailing
#: comma, the oldest spelling of the full-list key, no tag_descriptions and no
#: codegen section at all.
HAND_WRITTEN = """{
  // the flight computer's lists
  "project": {
    "name": "Hand",
    "description": "",
  },
  "inputs": {
    // in build order
    "model_files": [
      // the navigation unit first
      "nav.xml",
      "gs.xml",
    ],
    "model_directory": "parameter_lists",
  },
  "output": {
    "format": "smart_data",
    "code_directory": "out",
    // the oldest spelling of full_parameter_list_file
    "xml_file": "merged/all.xml",
  },
  "validation": {
    "treat_warnings_as_errors": false,
  },
}
"""


def project(work, text=None, lists=("nav", "gs"), output_format="smart_data"):
    """A project in *work*/proj with empty lists; returns (api, project file)."""
    workspace = Workspace(settings_file=work / "settings.json")
    if text is None:
        path = workspace.create(work / "proj", "Demo", output_format=output_format)
        workspace.open(path)
        for name in lists:
            workspace.document.create_list(name)
    else:
        root = work / "proj"
        (root / "parameter_lists").mkdir(parents=True)
        for name in lists:
            (root / "parameter_lists" / f"{name}.xml").write_text(EMPTY_LIST, encoding="utf-8")
        path = root / "pl_project.json"
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        workspace.open(path)
    document = workspace.document
    if document.config.inputs.model_files:
        document.load(document.config.inputs.model_files[0])
    return Api(workspace), path


def apply(api, changes, fingerprint=None):
    if fingerprint is None:
        fingerprint = api.project_settings({})["fingerprint"]
    return api.set_project_settings({"fingerprint": fingerprint, "changes": changes})


def without(data, dotted):
    """*data* with one key taken out - to compare everything else."""
    copy = json.loads(json.dumps(data))
    section, _, key = dotted.partition(".")
    copy.get(section, {}).pop(key, None)
    if copy.get(section) == {}:
        del copy[section]       # a section that held only that key: as if never there
    return copy


# -- what the dialog shows ------------------------------------------------------
def test_it_shows_the_file(work):
    api, path = project(work)
    answer = api.project_settings({})
    true(answer["ok"], f"read: {answer}")
    equal(answer["file"], str(path), "the project file it read")
    equal(set(answer["values"]), {setting.key for setting in SETTINGS}, "every setting")
    data = load_jsonc(path)
    for setting in SETTINGS:
        section, _, key = setting.key.partition(".")
        if key in data.get(section, {}):
            equal(answer["values"][setting.key], data[section][key], setting.key)
            true(answer["present"][setting.key], f"{setting.key} is in the file")
    equal(answer["values"]["inputs.model_files"], ["nav.xml", "gs.xml"], "the sublists")
    equal(answer["listsFound"], {"nav.xml": True, "gs.xml": True}, "both lists exist")
    true(not answer["dirty"], "nothing unsaved")


def test_a_missing_key_shows_what_a_build_uses(work):
    api, path = project(work, HAND_WRITTEN)
    answer = api.project_settings({})
    values, present = answer["values"], answer["present"]
    equal(values["output.full_parameter_list_file"], "merged/all.xml",
          "the oldest spelling is read")
    true(present["output.full_parameter_list_file"], "and counts as present")
    config = Config.load(path)
    equal(values["codegen.descriptor_symbol"], config.codegen.descriptor_symbol,
          "a missing codegen key: what Config.load uses")
    true(not present["codegen.descriptor_symbol"], "and it says it is missing")
    equal(values["output.file_prefix"], config.output.file_prefix, "file prefix")
    equal(values["tag_descriptions.Tag1"], "", "an old project describes no tag")
    true(not present["tag_descriptions.Tag1"], "and has no such section")
    equal(answer["firstList"], "nav", "what an empty base name becomes")


def test_the_single_model_file_spelling(work):
    text = HAND_WRITTEN.replace('"model_files": [\n      // the navigation unit first\n'
                                '      "nav.xml",\n      "gs.xml",\n    ],',
                                '"model_file": "nav.xml",')
    api, path = project(work, text)
    equal(api.project_settings({})["values"]["inputs.model_files"], ["nav.xml"],
          "one list read as a list of one")
    answer = apply(api, {"inputs.model_files": ["nav.xml", "gs.xml"]})
    true(answer["ok"], f"apply: {answer}")
    data = load_jsonc(path)
    equal(data["inputs"].get("model_files"), ["nav.xml", "gs.xml"], "it grew into the list")
    true("model_file" not in data["inputs"], "and the single spelling is gone")
    equal(len(api.document.config.inputs.model_files), 2, "the build has both")


# -- writing ----------------------------------------------------------------------
#: one new value for every setting that can be changed
NEW_VALUES = {
    "project.name": "Renamed",
    "project.description": "What it builds",
    "output.code_directory": "generated/here",
    "output.full_parameter_list_file": "merged/everything.xml",
    "output.file_prefix": "fw_",
    "output.base_name": "flight",
    "inputs.model_directory": "parameter_lists",
    "inputs.model_files": ["gs.xml", "nav.xml"],
    "style.company": "ACME",
    "style.indent": "\t",
    "codegen.emit_description": False,
    "codegen.emit_unit": False,
    "codegen.emit_generation_info": False,
    "codegen.emit_timestamp": False,
    "codegen.index_define_prefix": "IDX_",
    "codegen.offset_define_prefix": "OFS_",
    "codegen.smart_data_prefix": "Sd_",
    "codegen.struct_type_prefix": "tMy_",
    "codegen.descriptor_symbol": "TheTable",
    "codegen.quantity_define": "PARAM_COUNT",
    "codegen.extra_includes": ["app_flags.h", "<stdint.h>"],
    "validation.treat_warnings_as_errors": True,
    "validation.require_unit": True,
    "tag_descriptions.Tag1": "Saveable",
    "tag_descriptions.Tag2": "ذخیره در حافظه",
    "tag_descriptions.Tag3": "Ground station",
    "tag_descriptions.Tag4": "Reserved",
}


def test_each_setting_changes_only_itself(work):
    """For every setting: Apply changes that one value, and nothing else in the file."""
    equal(set(NEW_VALUES) | {"output.format"}, {setting.key for setting in SETTINGS},
          "every setting has a case")
    for number, (key, value) in enumerate(NEW_VALUES.items()):
        here = work / f"case{number}"
        here.mkdir()
        api, path = project(here)
        before = load_jsonc(path)
        old_lines = path.read_text(encoding="utf-8").splitlines()
        answer = apply(api, {key: value})
        true(answer["ok"], f"{key}: {answer}")
        after = load_jsonc(path)
        section, _, name = key.partition(".")
        equal(after[section][name], value, f"{key} is written")
        equal(without(after, key), without(before, key), f"{key} touches nothing else")
        new_lines = path.read_text(encoding="utf-8").splitlines()
        changed = [line for line in old_lines if line not in new_lines]
        # one line for one value; a list rewrites its own lines only
        allowed = max(1, len(value)) if isinstance(value, list) else 1
        true(len(changed) <= allowed, f"{key}: {allowed} line(s) changed, not {changed}")
        equal(api.project_settings({})["values"][key], value, f"{key} reads back")


def test_comments_and_layout_survive(work):
    api, path = project(work, HAND_WRITTEN)
    answer = apply(api, {"project.name": "Still hand written",
                         "output.full_parameter_list_file": "merged/new.xml",
                         "codegen.emit_unit": False,
                         "tag_descriptions.Tag1": "Saveable"})
    true(answer["ok"], f"apply: {answer}")
    text = path.read_text(encoding="utf-8")
    for comment in ("// the flight computer's lists", "// in build order",
                    "// the navigation unit first", "// the oldest spelling of"):
        true(comment in text, f"the comment '{comment}' is still there")
    data = load_jsonc(path)
    equal(data["output"].get("xml_file"), "merged/new.xml",
          "the key keeps the spelling the file uses")
    true("full_parameter_list_file" not in data["output"], "no second spelling is added")
    equal(data["codegen"], {"emit_unit": False}, "a missing section gets just the one key")
    equal(data["tag_descriptions"], {"Tag1": "Saveable"}, "and so does a new one")
    equal(data["inputs"]["model_files"], ["nav.xml", "gs.xml"], "the rest is untouched")
    config = Config.load(path)
    equal(config.output.xml_file.name, "new.xml", "the build reads it")


def test_line_endings_and_bom_survive(work):
    text = "﻿" + HAND_WRITTEN.replace("\n", "\r\n")
    api, path = project(work, text.encode("utf-8"))
    true(apply(api, {"style.company": "ACME"})["ok"], "apply")
    raw = path.read_bytes()
    true(raw.startswith(b"\xef\xbb\xbf"), "the byte-order mark stays")
    body = raw.decode("utf-8-sig")
    equal(body.count("\r\n"), body.count("\n"), "every line still ends in CRLF")
    equal(load_jsonc(path)["style"], {"company": "ACME"}, "and the value is there")


def test_nothing_changed_writes_nothing(work):
    api, path = project(work, HAND_WRITTEN)
    before = path.read_bytes()
    answer = apply(api, {})
    true(answer["ok"], f"apply with no change: {answer}")
    equal(path.read_bytes(), before, "an old project is not rewritten by opening it, "
                                     "reading its settings or applying nothing")


# -- refusals ---------------------------------------------------------------------
BAD_VALUES = [
    ("codegen.descriptor_symbol", "int", "a C keyword"),
    ("codegen.descriptor_symbol", "", "an empty table name"),
    ("codegen.quantity_define", "2COUNT", "a name starting with a digit"),
    ("codegen.smart_data_prefix", "Sd-", "a '-' in a prefix"),
    ("output.base_name", "my list", "a space in a file name"),
    ("output.file_prefix", "1_", "a file prefix starting with a digit"),
    ("project.name", "  ", "an empty name"),
    ("project.description", "two\nlines", "a description on two lines"),
    ("style.indent", "", "an empty indent"),
    ("style.indent", "--", "an indent that is not whitespace"),
    ("codegen.emit_unit", "yes", "a switch given a word"),
    ("inputs.model_files", ["nav.xml", ""], "an empty sublist line"),
    ("inputs.model_files", ["nav.xml", "nav.xml"], "the same sublist twice"),
    ("inputs.model_directory", "", "no sublist folder"),
    ("codegen.extra_includes", ["<app.h"], "a broken include"),
    ("output.format", "param_table", "the format"),
    ("output.no_such_key", "x", "a key that is no setting"),
    ("tag_descriptions.Tag5", "x", "a tag that does not exist"),
]


def test_a_bad_value_writes_nothing(work):
    api, path = project(work)
    before = path.read_bytes()
    for key, value, what in BAD_VALUES:
        # with a good change beside it, which must not be written either
        answer = apply(api, {key: value, "style.company": "fine"})
        true(not answer["ok"], f"{what} was not refused")
        true(answer.get("message"), f"{what}: it says why")
        equal(answer.get("field"), key, f"{what}: it names the setting")
        equal(path.read_bytes(), before, f"{what}: the file is unchanged")


def test_a_file_changed_on_disk_is_not_overwritten(work):
    api, path = project(work)
    seen = api.project_settings({})
    # somebody edits the file by hand while the dialog is open
    path.write_text(path.read_text(encoding="utf-8").replace('"FAS"', '"BY HAND"'),
                    encoding="utf-8")
    edited = path.read_bytes()
    answer = apply(api, {"project.name": "Mine"}, seen["fingerprint"])
    true(not answer["ok"], "the stale dialog was not refused")
    true("changed outside" in answer["message"], f"it says why: {answer['message']}")
    equal(path.read_bytes(), edited, "the hand edit is kept")
    equal(answer["settings"]["values"]["style.company"], "BY HAND",
          "the dialog gets the file as it is now")
    answer = apply(api, {"project.name": "Mine"}, answer["settings"]["fingerprint"])
    true(answer["ok"], f"applying again works: {answer}")
    equal(load_jsonc(path)["style"]["company"], "BY HAND", "with the hand edit in it")


def test_unsaved_changes_are_never_thrown_away(work):
    api, path = project(work)
    before = path.read_bytes()
    api.add({"parent": "", "kind": "primitive"})
    true(api.document.dirty, "the list has an unsaved parameter")
    read = api.project_settings({})
    true(read["dirty"], "the dialog is told when it opens")
    answer = apply(api, {"project.name": "Mine"})
    true(not answer["ok"] and answer.get("dirty"), f"refused: {answer}")
    equal(path.read_bytes(), before, "nothing written")
    true(api.document.find("NewParameter") is not None, "the parameter is still there")
    api.document.save()
    true(apply(api, {"project.name": "Mine"})["ok"], "once saved, it applies")
    true(api.document.find("NewParameter") is not None, "and the reload kept it")


# -- after Apply ------------------------------------------------------------------
def test_apply_reloads_the_project(work):
    api, path = project(work)
    document = api.document
    nav, gs = document.config.inputs.model_files
    document.load(gs)
    answer = apply(api, {"codegen.descriptor_symbol": "TheTable",
                         "output.base_name": "flight",
                         "tag_descriptions.Tag1": "Saveable"})
    true(answer["ok"], f"apply: {answer}")
    equal(api.document.config.codegen.descriptor_symbol, "TheTable", "the new setting is used")
    equal(api.document.path.resolve(), gs.resolve(), "the open list stays open")
    labels = {spec["id"]: spec["label"] for spec in api.state({})["tagSpecs"]}
    equal(labels["Tag1"], "Tag1 : Saveable", "the form names Tag1 by its meaning")
    equal(labels["Tag2"], "Tag2", "an undescribed tag is its name")

    api.add({"parent": "", "kind": "primitive"})
    api.document.save()
    result = api.document.generate()
    true(result["success"], f"generate: {result['message']}")
    header = (path.parent / "cg_parameter_list" / "cg_flight.h").read_text(encoding="utf-8")
    true("TheTable" in header, "the generator used the new name")
    true("Tag1 : Saveable" in header and "Tag2 :" not in header,
         "the header says what Tag1 means, and only Tag1")

    # the open list taken out of the build: the build's first list opens
    answer = apply(api, {"inputs.model_files": ["nav.xml"]})
    true(answer["ok"], f"apply: {answer}")
    equal(api.document.path.resolve(), nav.resolve(), "the first list of the new build")


def test_it_agrees_with_the_sublists_dialog(work):
    api, path = project(work)
    # a list typed by hand: the sublists dialog shows it
    answer = apply(api, {"inputs.model_files": ["nav.xml", "gs.xml", "more/extra.xml"]})
    true(answer["ok"], f"apply: {answer}")
    equal(load_jsonc(path)["inputs"]["model_files"], ["nav.xml", "gs.xml", "more/extra.xml"],
          "written exactly as typed")
    shown = {item["file"]: item for item in api.lists({})["lists"]}
    true("extra.xml" in shown and shown["extra.xml"]["selected"],
         f"the sublists dialog has it in the build: {sorted(shown)}")
    equal(shown["extra.xml"]["order"], 2, "third (#3), as typed")
    true(not shown["extra.xml"]["exists"], "and it says the file is not there")
    equal(api.project_settings({})["listsFound"]["more/extra.xml"], False,
          "and both say it does not exist yet")

    # the sublists dialog changes the build: this dialog reads it, and an
    # older reading of the file is refused rather than written over it
    stale = api.project_settings({})["fingerprint"]
    gs = path.parent / "parameter_lists" / "gs.xml"
    true(api.select_lists({"paths": [str(gs)]})["ok"], "the sublists dialog")
    equal(api.project_settings({})["values"]["inputs.model_files"], ["gs.xml"],
          "this dialog shows what the other one wrote")
    true(not apply(api, {"project.name": "X"}, stale)["ok"],
         "a reading from before that change is refused")


def test_a_table_takes_only_lists_it_can_build(work):
    api, path = project(work, lists=(), output_format="param_table")
    api.document.create_list("sys_nav_paramTable")
    before = path.read_bytes()
    answer = apply(api, {"inputs.model_files": ["sys_nav_paramTable.xml", "notes.xml"]})
    true(not answer["ok"], "a list named after no sub-system was taken")
    equal(answer.get("field"), "inputs.model_files", "the sublists are named")
    equal(path.read_bytes(), before, "nothing written")
    equal(api.project_settings({})["values"]["output.format"], "param_table",
          "the format is shown")


# -- the templates ----------------------------------------------------------------
def test_a_new_project_starts_from_the_template(work):
    """The template has a place for every tag's description; a new project gets
    only the ones written there.  (Asked for.)"""
    template = load_jsonc(PROJECT_TEMPLATE)
    equal(template.get("tag_descriptions"), {"Tag1": "", "Tag2": "", "Tag3": "", "Tag4": ""},
          "the template has the four tags, to be written in")
    (work / "empty").mkdir()
    (work / "described").mkdir()
    api, path = project(work / "empty")
    true("tag_descriptions" not in load_jsonc(path),
         "a new project gets none of the empty ones")
    equal(api.project_settings({})["present"]["tag_descriptions.Tag1"], False,
          "and the dialog says Tag1 is not in the file")

    written = work / "template.json"
    written.write_text(PROJECT_TEMPLATE.read_text(encoding="utf-8").replace(
        '"Tag1": ""', '"Tag1": "Saveable"'), encoding="utf-8")
    real = workspace_module.PROJECT_TEMPLATE
    workspace_module.PROJECT_TEMPLATE = written
    try:
        _api, path = project(work / "described")
    finally:
        workspace_module.PROJECT_TEMPLATE = real
    equal(load_jsonc(path)["tag_descriptions"], {"Tag1": "Saveable"},
          "one written in the template: every new project has it, and only it")


def test_an_emptied_tag_description_leaves_the_file(work):
    """An emptied description is taken out, not kept as "".  (Asked for.)"""
    api, path = project(work)
    true(apply(api, {"tag_descriptions.Tag1": "Saveable",
                     "tag_descriptions.Tag2": "Ground station"})["ok"], "two described")
    equal(load_jsonc(path)["tag_descriptions"],
          {"Tag1": "Saveable", "Tag2": "Ground station"}, "both in the file")

    true(apply(api, {"tag_descriptions.Tag1": ""})["ok"], "Tag1 emptied")
    equal(load_jsonc(path)["tag_descriptions"], {"Tag2": "Ground station"},
          "Tag1 is gone from the file, Tag2 stays")
    shown = api.project_settings({})
    equal((shown["values"]["tag_descriptions.Tag1"], shown["present"]["tag_descriptions.Tag1"]),
          ("", False), "and the dialog says it is not in the file")

    before = load_jsonc(path)
    true(apply(api, {"tag_descriptions.Tag2": ""})["ok"], "the last one emptied")
    after = load_jsonc(path)
    true("tag_descriptions" not in after, "the section goes with the last of them")
    before.pop("tag_descriptions")
    equal(after, before, "and nothing else changed")
    labels = {spec["id"]: spec["label"] for spec in api.state({})["tagSpecs"]}
    equal(labels["Tag2"], "Tag2", "the form names the tag plainly again")


def test_an_empty_one_from_before_is_taken_out(work):
    """A file that already has "Tag1": "" - as Apply wrote it before.  (Reported.)"""
    text = HAND_WRITTEN.replace('''  "validation": {
    "treat_warnings_as_errors": false,
  },''', '''  "validation": {
    "treat_warnings_as_errors": false,
  },
  "tag_descriptions": {
    "Tag1": "",
    "Tag3": "Saveable"
  },''')
    api, path = project(work, text)
    shown = api.project_settings({})
    equal(shown["present"]["tag_descriptions.Tag1"], False, "shown as not in the file")
    true(shown["present"]["tag_descriptions.Tag3"], "a written one is in the file")
    true(apply(api, {})["ok"], "Apply with nothing changed")
    data = load_jsonc(path)
    equal(data["tag_descriptions"], {"Tag3": "Saveable"}, "the empty one is taken out")
    true("// the navigation unit first" in path.read_text(encoding="utf-8"),
         "and the comments stay")
    before = path.read_bytes()
    true(apply(api, {})["ok"], "Apply again")
    equal(path.read_bytes(), before, "then there is nothing left to take out")


CASES = [
    ("it shows the file", test_it_shows_the_file),
    ("a missing key shows what a build uses", test_a_missing_key_shows_what_a_build_uses),
    ("the single model_file spelling", test_the_single_model_file_spelling),
    ("each setting changes only itself", test_each_setting_changes_only_itself),
    ("comments and layout survive", test_comments_and_layout_survive),
    ("line endings and a BOM survive", test_line_endings_and_bom_survive),
    ("nothing changed writes nothing", test_nothing_changed_writes_nothing),
    ("a bad value writes nothing", test_a_bad_value_writes_nothing),
    ("a file changed on disk is not overwritten",
     test_a_file_changed_on_disk_is_not_overwritten),
    ("unsaved changes are never thrown away", test_unsaved_changes_are_never_thrown_away),
    ("apply reloads the project", test_apply_reloads_the_project),
    ("it agrees with the sublists dialog", test_it_agrees_with_the_sublists_dialog),
    ("a table takes only lists it can build", test_a_table_takes_only_lists_it_can_build),
    ("a new project starts from the template", test_a_new_project_starts_from_the_template),
    ("an emptied tag description leaves the file",
     test_an_emptied_tag_description_leaves_the_file),
    ("an empty one from before is taken out", test_an_empty_one_from_before_is_taken_out),
]


def main() -> int:
    failures = 0
    real = choices.CHOICES_FILE
    for title, case in CASES:
        with tempfile.TemporaryDirectory(prefix="pl_settings_") as raw:
            work = pathlib.Path(raw)
            # the machine's own lists are never written by a test
            choices.CHOICES_FILE = work / "choices.json"
            shutil.copy(choices.CHOICES_TEMPLATE, choices.CHOICES_FILE)
            try:
                case(work)
            except Failure as error:
                failures += 1
                print(f"  [{paint('FAIL', BOLD + BRIGHT_RED)}] {title}\n         {error}")
                continue
            except Exception:                              # noqa: BLE001
                failures += 1
                print(f"  [{paint('ERROR', BOLD + BRIGHT_RED)}] {title}")
                print("         " + traceback.format_exc().replace("\n", "\n         "))
                continue
            finally:
                choices.CHOICES_FILE = real
        print(f"  [{paint('PASS', GREEN)}] {title}")

    print()
    if failures:
        print(paint(f"{failures} of {len(CASES)} project-settings case(s) FAILED.",
                    BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} project-settings cases passed.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
