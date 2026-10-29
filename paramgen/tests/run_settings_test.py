# -*- coding: utf-8 -*-
"""Does every setting in a project file actually DO something?

One throwaway project, and for each key: change it, generate, and look at what
came out.  A setting that is read but never acted on is the worst kind of bug -
the user changes it, nothing happens, and there is nothing anywhere to say why.
``codegen.emit_unit`` was in exactly that state when this file was written: it
reached the comments and not the unit string that goes into the firmware.

Run it with::

    python tests/run_settings_test.py
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

APP = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "src"))

from pl_codegen.app_home import (PROJECT_FILE_NAME,             # noqa: E402
                                 copy_lib_into)
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,  # noqa: E402
                                      colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils               # noqa: E402

_logging_utils._colour_enabled = colour_supported()

LIST_XML = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Defines>
    <DefineGroup name="TYPE"><Value value="MONITORING" /></DefineGroup>
    <DefineGroup name="PARAM MODES"><Value value="PARAM_MODE_USER" /></DefineGroup>
    <DefineGroup name="SYSTEM NAMES"><Value value="SYS_NAV" /></DefineGroup>
    <DefineGroup name="VALUE TYPES">
      <Value value="float32_t" /><Value value="int16_t" />
    </DefineGroup>
  </Defines>
  <Parameters>
    <Parameter name="Speed" kind="primitive" enable="true" userName="Speed"
               type="MONITORING" valueType="float32_t" arraySize="1" unit="m/s"
               logId="10">
      <Source />
      <Limits default="0" minimum="0" maximum="100" resolution="0.01" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Description>How fast.</Description>
    </Parameter>
    <Parameter name="Box" kind="struct" enable="true" userName="Box"
               type="MONITORING" arraySize="1" logId="20">
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Description>A box.</Description>
      <Fields>
        <Parameter name="Count" kind="primitive" enable="true" userName="Count"
                   valueType="int16_t" arraySize="1">
          <Source />
          <Limits default="0" minimum="0" maximum="500" resolution="1" />
          <Tags />
          <Description>How many.</Description>
        </Parameter>
      </Fields>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""


def make_project(root: pathlib.Path, settings: dict) -> pathlib.Path:
    """A project folder whose pl_project.json is exactly *settings*."""
    (root / "parameter_lists").mkdir(parents=True, exist_ok=True)
    (root / "parameter_lists" / "list.xml").write_text(LIST_XML, encoding="utf-8")
    copy_lib_into(root / "lib")
    (root / PROJECT_FILE_NAME).write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return root / PROJECT_FILE_NAME


BASE = {
    "project": {"name": "Settings probe", "description": "one key at a time"},
    "inputs": {"model_directory": "parameter_lists", "model_files": ["list.xml"]},
    "output": {"code_directory": "out", "last_build_file": "snap/model.xml",
               "file_prefix": "cg_", "base_name": "parameter_list"},
    "style": {"company": "FAS", "indent": "    "},
    "codegen": {}, "validation": {},
}


def generate(project_file: pathlib.Path):
    out = subprocess.run(
        [sys.executable, str(APP / "bin" / "run_generate.py"), "-c", str(project_file), "-q"],
        capture_output=True, text=True)
    return out.returncode, (out.stdout + out.stderr)


def deep(settings: dict, path: str, value) -> dict:
    """A copy of *settings* with ``"output.file_prefix"`` set to *value*."""
    copy = json.loads(json.dumps(settings))
    section, _, key = path.partition(".")
    if key:
        copy.setdefault(section, {})[key] = value
    else:
        copy[section] = value
    return copy


CASES = []


def case(key, value, check, why=""):
    CASES.append((key, value, check, why))


# ---- output ---------------------------------------------------------------
case("output.code_directory", "somewhere/else",
     lambda root, text: (root / "somewhere" / "else" / "cg_parameter_list.h").is_file(),
     "the generated files land where it says")
case("output.last_build_file", "elsewhere/previous.xml",
     lambda root, text: (root / "elsewhere" / "previous.xml").is_file(),
     "the last-build model lands where it says")
# The two names this key had before.  Set on their own - a project file that
# still uses one has not got the new one - so the fallback is really exercised.
case("output", {"code_directory": "out", "snapshot_file": "older_name/previous.xml",
                "file_prefix": "cg_", "base_name": "parameter_list"},
     lambda root, text: (root / "older_name" / "previous.xml").is_file(),
     "the previous spelling of the same key still works")
case("output", {"code_directory": "out", "xml_file": "oldest_name/previous.xml",
                "file_prefix": "cg_", "base_name": "parameter_list"},
     lambda root, text: (root / "oldest_name" / "previous.xml").is_file(),
     "and the oldest spelling too")
case("output.file_prefix", "fw_",
     lambda root, text: (root / "out" / "fw_parameter_list.h").is_file(),
     "every generated name starts with it")
case("output.base_name", "params",
     lambda root, text: (root / "out" / "cg_params.h").is_file(),
     "the middle of every generated name")

# ---- style ----------------------------------------------------------------
case("style.company", "ACME",
     lambda root, text: "ACME" in read(root, "out/cg_parameter_list.h"),
     "the banner of every generated file")
case("style.indent", "\t",
     lambda root, text: "\n\t" in read(root, "out/cg_parameter_list.c"),
     "what an indented line starts with")

# ---- codegen --------------------------------------------------------------
case("codegen.file_prefix_unknown_key", "x",
     lambda root, text: "Unknown configuration key" in text,
     "an unknown key is reported, not swallowed")
case("codegen.index_define_prefix", "IDX_",
     lambda root, text: "IDX_SPEED" in read(root, "out/cg_parameter_list_defines.h"),
     "the index macros")
case("codegen.offset_define_prefix", "OFS_",
     lambda root, text: "OFS_TAG_" in read(root, "out/cg_parameter_list_defines.h"),
     "the tag size macros")
case("codegen.smart_data_prefix", "Sd_",
     lambda root, text: "Sd_Speed" in read(root, "out/cg_smart_data.h"),
     "the smart-data object names")
case("codegen.struct_type_prefix", "tMy_",
     lambda root, text: "tMy_Box" in read(root, "out/cg_parameter_list_types.h"),
     "the generated struct typedefs")
case("codegen.descriptor_symbol", "TheTable",
     lambda root, text: "TheTable" in read(root, "out/cg_parameter_list.c"),
     "the name of the descriptor table")
case("codegen.quantity_define", "PARAM_COUNT",
     lambda root, text: "PARAM_COUNT" in read(root, "out/cg_parameter_list.h"),
     "the macro holding the number of parameters")
case("codegen.extra_includes", ["app_flags.h"],
     lambda root, text: "app_flags.h" in read(root, "out/cg_parameter_list.c"),
     "extra #include lines")
case("codegen.emit_description", False,
     lambda root, text: "How fast." not in read(root, "out/cg_parameter_list.c"),
     "descriptions kept out of the generated code")
case("codegen.emit_unit", False,
     lambda root, text: '"m/s"' not in read(root, "out/cg_smart_data.c"),
     "units kept out of the generated code")
case("codegen.emit_timestamp", False,
     lambda root, text: "Generated at" not in read(root, "out/cg_parameter_list.h"),
     "no timestamp, so two runs are byte-identical")
case("codegen.emit_generation_info", False,
     lambda root, text: "parameter_list_code_generator" not in
                        read(root, "out/cg_parameter_list.h").split("*/")[0],
     "no generator banner")

# ---- validation -----------------------------------------------------------
case("validation.require_unit", True,
     lambda root, text: "META002" in text,
     "an empty unit becomes an error")
case("validation.treat_warnings_as_errors", True,
     lambda root, text: "0 file(s)" in text or "Generated" not in text,
     "a warning stops the build")

# ---- inputs ---------------------------------------------------------------
case("inputs.model_directory", "lists_here",
     lambda root, text: (root / "out" / "cg_parameter_list.h").is_file(),
     "a bare name is looked up in this folder")
case("inputs.model_files", ["parameter_lists/list.xml"],
     lambda root, text: (root / "out" / "cg_parameter_list.h").is_file(),
     "a path with a folder in it is taken from the project file")


def read(root: pathlib.Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix="pl_settings_") as raw:
        work = pathlib.Path(raw)
        for index, (key, value, check, why) in enumerate(CASES):
            root = work / f"case{index:02d}"
            settings = deep(BASE, key, value)

            # two of the cases need the fixture moved to match the setting
            if key == "inputs.model_directory":
                project = make_project(root, settings)
                (root / "lists_here").mkdir(exist_ok=True)
                shutil.move(str(root / "parameter_lists" / "list.xml"),
                            str(root / "lists_here" / "list.xml"))
            else:
                project = make_project(root, settings)

            code, text = generate(project)
            try:
                ok = bool(check(root, text))
            except Exception as error:            # noqa: BLE001
                ok = False
                text += f"\ncheck blew up: {error}"

            mark = paint("PASS", GREEN) if ok else paint("FAIL", BOLD + BRIGHT_RED)
            print(f"  [{mark}] {key:<42} = {str(value)[:24]:<26} {why}")
            if not ok:
                failures += 1
                tail = "\n".join(line for line in text.splitlines()
                                 if line.strip())[-500:]
                print(f"         exit {code}; output tail:\n{tail}\n")

    print()
    if failures:
        print(paint(f"{failures} of {len(CASES)} setting(s) DO NOTHING.",
                    BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} settings behave as documented.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
