"""End-to-end test: generate the code and compile it with a real C/C++ compiler.

The test
  1. runs the generator on ``parameter_list.xml`` into a temporary folder,
  2. compiles the generated files together with ``smart_data.c`` as **C99** and
     compiles the generated headers as **C++**,
  3. links and runs a small program that calls ``fParameterList_Init()``,
     walks the descriptor table and exercises the usage example.

Run it with::

    python tests/run_compile_test.py

It needs ``gcc`` and ``g++`` on the PATH; on Windows a MinGW or WSL toolchain
works.  The test never touches the files under ``cg_parameter_list`` of the
project: everything is generated into a temporary folder.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

#: The app folder.  The usage example and the templates ship with the app, so
#: they are found from here; the C library lives beside the app instead (see
#: SMART_DATA_DIR / PARAMETER_DESCRIPTOR_DIR below).  A *project* is somewhere
#: else entirely and this test makes its own.
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen.app_home import (DOCS_DIR, PARAMETER_DESCRIPTOR_DIR,  # noqa: E402
                                 PROJECT_FILE_NAME, SMART_DATA_DIR, SNIPPET_FILE)
from pl_codegen.cli import main as generator_main  # noqa: E402
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, CYAN,  # noqa: E402
                                            GREEN, YELLOW, colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils  # noqa: E402

_logging_utils._colour_enabled = colour_supported()

C_COMPILER = "gcc"
CXX_COMPILER = "g++"

def _run(command: List[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


def have_compiler(name: str) -> bool:
    return shutil.which(name) is not None



#: A parameter table, as the older firmware wants it.  Two sub-systems, so the
#: generated header has two #if blocks and the indices restart - and every type
#: the format supports, because a table is exactly where a bad literal hides.
_PARAM_TABLE_XML = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Parameters>
    <Parameter name="PR_GSM_TABLE_NUM" kind="primitive" enable="true"
               gsName="GSM_TABLE_NUM" type="SETTING" valueType="uint8_t" arraySize="1"
               address="400">
      <Source />
      <Limits default="31" minimum="0" maximum="255" resolution="1" />
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
    <Parameter name="PR_GSM_PINOUT_TYPE" kind="primitive" enable="true"
               gsName="GSM_PINOUT_TYPE" type="SETTING" valueType="int8_t" arraySize="1">
      <Source />
      <Limits default="-1" minimum="-1" maximum="100" resolution="1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_READ_ONLY" />
      </Tags>
      <Description>-1: Unknown, 2:GSV2, 3:GSV3R1</Description>
    </Parameter>
    <Parameter name="PR_GSM_INITIAL_LOCK_SIZE" kind="primitive" enable="true"
               gsName="INITIAL_LOCK_SIZE" type="SETTING" valueType="float32_t" arraySize="1">
      <Source />
      <Limits default="0.04" minimum="0.01" maximum="0.3" resolution="0.01" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Description>Lock Box Size Parameter</Description>
    </Parameter>
    <Parameter name="PR_GSM_VIRTUAL_CORRUPTION" kind="primitive" enable="true"
               gsName="Virtual Corruption" type="SETTING" valueType="uint64_t" arraySize="1">
      <Source />
      <Limits default="0" minimum="0" maximum="0" resolution="1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_GS_MANAGER" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_FACTORY" />
      </Tags>
      <Description>NO_VC:0
LOW_FREQUENCY:1</Description>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""

_PARAM_TABLE_RHS_XML = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Parameters>
    <Parameter name="PR_RHS_GAIN" kind="primitive" enable="true" gsName="RHS_GAIN"
               type="SETTING" valueType="float64_t" arraySize="1">
      <Source />
      <Limits default="1.5" minimum="0" maximum="10" resolution="0.001" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_RHS" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_CALIB" />
      </Tags>
      <Description>loop gain</Description>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""

#: What the firmware does with the table: define ADD_PARAM, pick a sub-system,
#: include the header.  Counting the rows proves the macro really expanded.
_PARAM_TABLE_MAIN = """
#include <stdio.h>
#include <stdint.h>

#define SYS_GS_MANAGER 2
#define SYS_RHS        19
#define SYS_ALL        255
#define DESIRED_SUB_SYSTEM SYS_ALL

/* The generated names, after the firmware's own: a name defined above keeps
   its value and draws no redefinition warning (-Werror), the rest are defined
   by the file. */
#include "nsrSystemNames.h"
#if SYS_GS_MANAGER != 2
#error "nsrSystemNames.h replaced the firmware's own SYS_GS_MANAGER"
#endif
#ifndef SYS_NAV
#error "nsrSystemNames.h did not define SYS_NAV"
#endif

typedef enum {
    TYPE_UINT8, TYPE_INT8, TYPE_UINT16, TYPE_INT16,
    TYPE_UINT32, TYPE_INT32, TYPE_UINT64, TYPE_INT64,
    TYPE_FLOAT, TYPE_DOUBLE
} eParamType;

static int gRows = 0;
static int gAddress = 0;

#define ADD_PARAM(type_, enum_, name_, gs_, sys_, index_, def_, min_, max_, \
                  res_, mode_, addr_, note_)                                \
    do {                                                                     \
        type_ value_ = (type_)(def_);                                        \
        eParamType kind_ = enum_;                                            \
        const char *shown_ = (gs_);                                          \
        const char *why_ = (note_);                                          \
        (void)value_; (void)kind_; (void)shown_; (void)why_;                 \
        (void)(min_); (void)(max_); (void)(res_); (void)(mode_);             \
        (void)(sys_); (void)(index_);                                        \
        if ((addr_) != 0) { gAddress = (addr_); }                            \
        gRows++;                                                             \
    } while (0);

int main(void)
{
#include "nsrParamTables.h"

    printf("rows=%d address=%d\\n", gRows, gAddress);
    if (gRows != 5) {
        printf("expected 5 rows\\n");
        return 1;
    }
    if (gAddress != 400) {
        printf("the address column did not arrive\\n");
        return 1;
    }
    return 0;
}
"""


def write_config(work_dir: Path, inputs: dict, name: str = PROJECT_FILE_NAME,
                 output_format: str = "smart_data") -> Path:
    """Write a configuration that generates into *work_dir*."""
    config = {
        "project": {"name": "compile test"},
        "inputs": inputs,
        "output": {
            "format": output_format,
            "code_directory": str(work_dir / "generated"),
            "xml_file": str(work_dir / "model.xml"),
            "file_prefix": "cg_",
            "base_name": "parameter_list",
        },
        "style": {"snippet_file": str(SNIPPET_FILE), "company": "FAS",
                  "indent": "    "},
        "codegen": {"emit_description": True, "emit_unit": True,
                    "emit_generation_info": True, "emit_timestamp": False},
        "validation": {"treat_warnings_as_errors": False},
    }
    path = work_dir / name
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


#: The three ways a project can feed the generator; all three must compile.
def input_variants() -> List[dict]:
    # The project's own lists, taken from its configuration rather than from
    # hard coded paths: the editor is free to add lists and to reorder them, and
    # the test has to keep testing whatever the project actually builds.
    project = [path for path in _project_lists() if path.is_file()]

    # The usage example is written against the demo parameters (Airspeed,
    # Position.Samples, RezaSaeedi.CoffeeCupsPerDay), so it only compiles
    # against the list that actually holds them.  Picking "the first list in the
    # configuration" instead would make this test fail the moment somebody
    # reorders the build in the editor - which is a supported thing to do, and
    # not a reason to call the tool broken.
    single = _list_holding_the_example(project)

    variants: List[dict] = []
    if single is not None:
        variants.append(
            {"label": f"one parameter list ({single.name})",
             "inputs": {"model_files": [str(single)]}})
    elif project:
        variants.append(
            {"label": f"one parameter list ({project[0].name}, without the example)",
             "inputs": {"model_files": [str(project[0])]},
             "with_example": False})
    if len(project) > 1:
        # The merged build needs the same guard as the single one.  It used to
        # compile the example unconditionally, on the assumption that merging
        # every list can only ever ADD parameters - true of the set, but not of
        # the configuration: the moment somebody unticks the demo list in the
        # editor, the merged model no longer holds the example's parameters and the
        # suite failed with a wall of "undeclared identifier" that said nothing
        # about the real cause.  Unticking a list is a supported thing to do.
        merged_names = _names_in(project)
        variants.append(
            {"label": f"{len(project)} parameter lists, merged",
             "inputs": {"model_files": [str(path) for path in project]},
             "with_example": all(needed in merged_names for needed in _EXAMPLE_NEEDS)})

    # The usage example, against a model of its own.  It is a shipped
    # deliverable and the reference for how firmware uses the generated code, so
    # it is compiled and run on every test run rather than only when the
    # project's configuration happens to hold the parameters it names.
    variants.append(
        {"label": "the usage example",
         "fixture": _EXAMPLE_XML,
         "with_example": True,
         "extra_checks": _EXAMPLE_FIXTURE_CHECKS})

    # A fixture the editor could have written, kept small on purpose: it is the
    # only place where an array of structures - and an array *inside* one - is
    # compiled and run, so the generated strides are checked by the compiler
    # rather than by eye.
    variants.append(
        {"label": "an array of structures",
         "fixture": _STRUCT_ARRAY_XML,
         "with_example": False,
         "extra_checks": _STRUCT_ARRAY_CHECKS})

    # A model whose ONLY array is a structure array, and nothing else.  It
    # exists because of a bug it would have caught: the init function declared
    # its loop counter whenever the model "had an array", but a struct array is
    # expanded field by field and needs no loop - so the counter sat there
    # unused and the generated file failed the company's own -Werror.  Every
    # other fixture happens to hold a primitive array too, which is exactly why
    # nothing noticed.
    variants.append(
        {"label": "a structure array and no other array",
         "fixture": _STRUCT_ONLY_XML,
         "with_example": False})

    # One structure type used by two parameters - the reported case.  They are
    # two instances of ONE typedef, and the check would not even compile if the
    # generator went back to giving each parameter a copy of its own.
    variants.append(
        {"label": "one structure type, two parameters",
         "fixture": _ONE_TYPE_TWO_USES_XML,
         "structures": _ONE_TYPE_TWO_USES_TYPES,
         "with_example": False,
         "extra_checks": _ONE_TYPE_TWO_USES_CHECKS})

    # The other output format: one header of ADD_PARAM lines, compiled with a
    # macro of the test's own.  Nothing about smart data is involved.
    variants.append(
        {"label": "the parameter table (two sub-systems)",
         "format": "param_table",
         "files": {"sys_gs_manager_paramTable.xml": _PARAM_TABLE_XML,
                   "sys_rhs_paramTable.xml": _PARAM_TABLE_RHS_XML}})

    return variants


#: The values example/parameter_list_usage_example.c reaches for by name.  A
#: list that has all of them can compile the example; any other cannot.
_EXAMPLE_NEEDS = ("Airspeed", "Position", "RezaSaeedi")


def _names_in(paths: List[Path]) -> set:
    """Every top level parameter name across *paths*, skipping unreadable ones."""
    from pl_codegen.errors import DiagnosticCollector
    from pl_codegen.xml_model.xml_reader import read_xml

    names = set()
    for path in paths:
        try:
            model = read_xml(path, DiagnosticCollector())
        except Exception:                 # a list that will not even parse
            continue
        names.update(parameter.name for parameter in model.parameters)
    return names


def _list_holding_the_example(candidates: List[Path]) -> Optional[Path]:
    """The project list the usage example fits, or ``None`` if no list does."""
    for path in candidates:
        if all(needed in _names_in([path]) for needed in _EXAMPLE_NEEDS):
            return path
    return None


def _project_lists() -> List[Path]:
    """The parameter sub lists of a real project to build as well: none.

    Kept, and kept empty, so the variants built from a project's own lists
    below have one place to be switched back on from.
    """
    # Deliberately nothing.  This used to build whatever project the user had
    # open last, which made the result depend on somebody's working state and
    # let a test reach into their files.  The fixtures below are the whole of
    # what this suite needs, and they are written from scratch every run.
    return []



#: One structure array, one scalar, and not a single primitive array.
_STRUCT_ONLY_XML = """<?xml version='1.0' encoding='utf-8'?>
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
    <Parameter name="Azimuth" kind="primitive" enable="true" gsName="Azimuth"
               type="MONITORING" valueType="float32_t" arraySize="1" unit="deg"
               logId="700">
      <Description>A plain scalar.</Description>
      <Source />
      <Limits default="0" minimum="-180" maximum="180" resolution="0.01" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
    </Parameter>
    <Parameter name="Motor" kind="struct" enable="true" gsName="Motor"
               type="MONITORING" arraySize="2" logId="710">
      <Description>Both motors.</Description>
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Fields>
        <Parameter name="Rpm" kind="primitive" enable="true" gsName="Rpm"
                   valueType="int16_t" arraySize="1" unit="rpm"
                  >
          <Description>Speed of one motor.</Description>
          <Source />
          <Limits default="0" minimum="-5000" maximum="5000" resolution="1" />
          <Tags />
        </Parameter>
      </Fields>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""

#: The model the usage example is written against.  It holds exactly the
#: parameters the example names and nothing else, so a change to the example
#: and a change to this fixture stay next to each other.
_EXAMPLE_XML = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Defines>
    <DefineGroup name="TYPE"><Value value="MONITORING" /></DefineGroup>
    <DefineGroup name="PARAM MODES"><Value value="PARAM_MODE_USER" /></DefineGroup>
    <DefineGroup name="SYSTEM NAMES"><Value value="SYS_NAV" /></DefineGroup>
    <DefineGroup name="VALUE TYPES">
      <Value value="float32_t" /><Value value="float64_t" /><Value value="int16_t" />
      <Value value="uint8_t" /><Value value="uint16_t" /><Value value="uint32_t" />
    </DefineGroup>
  </Defines>
  <Parameters>
    <Parameter name="Airspeed" kind="primitive" enable="true" gsName="Airspeed"
               type="MONITORING" valueType="float32_t" arraySize="1" unit="m/s"
               logId="100">
      <Description>Indicated airspeed.</Description>
      <Source />
      <Limits default="0" minimum="0" maximum="120" resolution="0.1" />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
    </Parameter>
    <Parameter name="Position" kind="struct" enable="true" gsName="Position"
               type="MONITORING" arraySize="1" logId="200">
      <Description>Where it is.</Description>
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Fields>
        <Parameter name="Home" kind="struct" enable="true" gsName="Home"
                   arraySize="1">
          <Description>The home point.</Description>
          <Source /><Limits /><Tags />
          <Fields>
            <Parameter name="Lat" kind="primitive" enable="true" gsName="Lat"
                       valueType="float64_t" arraySize="1" unit="deg">
              <Source />
              <Limits default="0" minimum="-90" maximum="90" resolution="0.0000001" />
              <Tags />
              <Description>Latitude of the home point.</Description>
            </Parameter>
            <Parameter name="Lon" kind="primitive" enable="true" gsName="Lon"
                       valueType="float64_t" arraySize="1" unit="deg">
              <Source />
              <Limits default="0" minimum="-180" maximum="180" resolution="0.0000001" />
              <Tags />
              <Description>Longitude of the home point.</Description>
            </Parameter>
          </Fields>
        </Parameter>
        <Parameter name="Alt" kind="primitive" enable="true" gsName="Alt"
                   valueType="float32_t" arraySize="1" unit="m">
          <Source />
          <Limits default="0" minimum="-500" maximum="10000" resolution="0.01" />
          <Tags />
          <Description>Altitude.</Description>
        </Parameter>
        <Parameter name="Samples" kind="primitive" enable="true" gsName="Samples"
                   valueType="int16_t" arraySize="8">
          <Source />
          <Limits default="0" minimum="-100" maximum="100" resolution="1" />
          <Tags />
          <Description>One raw sample.</Description>
        </Parameter>
        <Parameter name="Heading" kind="primitive" enable="true" gsName="Heading"
                   valueType="float32_t" arraySize="1" unit="deg">
          <Source />
          <Limits default="0" minimum="0" maximum="360" resolution="0.01" />
          <Tags />
          <Description>Where it points.</Description>
        </Parameter>
      </Fields>
    </Parameter>
    <Parameter name="RezaSaeedi" kind="struct" enable="true" gsName="RezaSaeedi"
               type="MONITORING" arraySize="1">
      <Description>The one behind the tool, as a structure: one fact per field.</Description>
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Fields>
        <Parameter name="BirthYear" kind="primitive" enable="true" gsName="BirthYear"
                   valueType="uint16_t" arraySize="1">
          <Source />
          <Limits default="2000" minimum="1900" maximum="2100" resolution="1" />
          <Tags />
          <Description>Year of birth - the default is a placeholder.</Description>
        </Parameter>
        <Parameter name="CoffeeCupsPerDay" kind="primitive" enable="true"
                   gsName="CoffeeCupsPerDay" valueType="uint8_t" arraySize="1" unit="cup">
          <Source />
          <Limits default="3" minimum="0" maximum="20" resolution="1" />
          <Tags />
          <Description>Cups of coffee a day. Even this parameter stops at 20.</Description>
        </Parameter>
        <Parameter name="BugsFixedToday" kind="primitive" enable="true"
                   gsName="BugsFixedToday" valueType="uint32_t" arraySize="1">
          <Source />
          <Limits default="0" minimum="0" maximum="4294967295" resolution="1" />
          <Tags />
          <Description>Bugs fixed today. It only ever counts up.</Description>
        </Parameter>
        <Parameter name="SleepHours" kind="primitive" enable="true" gsName="SleepHours"
                   valueType="float32_t" arraySize="1" unit="h">
          <Source />
          <Limits default="4.5" minimum="0" maximum="24" resolution="0.5" />
          <Tags />
          <Description>Hours of sleep last night - usually near the minimum.</Description>
        </Parameter>
      </Fields>
    </Parameter>
  </Parameters>
  <StructTemplates />
</ParameterListModel>
"""

#: A parameter list with a struct array whose elements hold an array field.
_STRUCT_ARRAY_XML = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListModel schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <SourceFiles />
  <Defines>
    <DefineGroup name="TYPE"><Value value="MONITORING" /></DefineGroup>
    <DefineGroup name="PARAM MODES"><Value value="PARAM_MODE_USER" /></DefineGroup>
    <DefineGroup name="SYSTEM NAMES"><Value value="SYS_NAV" /></DefineGroup>
    <DefineGroup name="VALUE TYPES">
      <Value value="float32_t" /><Value value="int16_t" /><Value value="uint32_t" />
    </DefineGroup>
  </Defines>
  <Parameters>
    <Parameter name="Car" kind="struct" enable="true" gsName="Car"
               type="MONITORING" arraySize="1" logId="600">
      <Description>One vehicle.</Description>
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="true" />
        <Tag id="Loggable" kind="boolean" value="true" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Fields>
        <Parameter name="Wheels" kind="struct" enable="true" gsName="Wheels"
                   arraySize="2">
          <Description>One entry per wheel.</Description>
          <Source /><Limits /><Tags />
          <Fields>
            <Parameter name="Speed" kind="primitive" enable="true" gsName="Speed"
                       valueType="float32_t" arraySize="1" unit="m/s">
              <Source />
              <Limits default="0" minimum="0" maximum="120" resolution="0.001" />
              <Tags />
              <Description>How fast a wheel turns.</Description>
              <!-- One VALUE saying what it means, instead of what the field
                   does: 'at' is the index of every array on the way to it, so
                   "1" is Wheels[1].Speed.  It is called something of its own
                   too: a User Name belongs to the value, like the description. -->
              <Elements>
                <Element at="1" userName="Rear wheel speed">How fast the REAR wheel turns.</Element>
              </Elements>
            </Parameter>
            <Parameter name="Samples" kind="primitive" enable="true" gsName="Samples"
                       valueType="int16_t" arraySize="4">
              <Source />
              <Limits default="0" minimum="0" maximum="0" resolution="1" />
              <Tags />
              <Description>One sample.</Description>
              <!-- a name and no description of its own: the value is still
                   described the way every sample is -->
              <Elements>
                <Element at="0.2">The third sample of the front wheel.</Element>
                <Element at="1.0" userName="First rear sample" />
              </Elements>
            </Parameter>
          </Fields>
        </Parameter>
        <!-- No User Name of its own: it reads its structure's, "Car". -->
        <Parameter name="Vin" kind="primitive" enable="true"
                   valueType="uint32_t" arraySize="1">
          <Source />
          <Limits default="7" minimum="0" maximum="0" resolution="1" />
          <Tags />
          <Description>Vehicle number - it has no unit on purpose.</Description>
        </Parameter>
      </Fields>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""

#: The reported case, as the editor writes it: two parameters of ONE structure
#: type.  Its types file travels beside it, the way every list's does.
_ONE_TYPE_TWO_USES_XML = """<?xml version='1.0' encoding='utf-8'?>
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
  <Parameters>
    <Parameter name="MyStr" kind="struct" enable="true" gsName="MyStr" type="MONITORING"
               valueType="Stest" arraySize="1">
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Fields>
        <Parameter name="collor" kind="primitive" enable="true" gsName="Co"
                   valueType="int16_t" arraySize="1" unit="rgb">
          <Source /><Limits default="0" minimum="0" maximum="0" resolution="1" /><Tags />
          <Description>no data</Description>
        </Parameter>
        <Parameter name="alive" kind="primitive" enable="true" gsName="Alive"
                   valueType="bool_t" arraySize="2">
          <Source /><Limits /><Tags />
        </Parameter>
      </Fields>
    </Parameter>
    <Parameter name="MyStr2" kind="struct" enable="true" gsName="MyStr2" type="MONITORING"
               valueType="Stest" arraySize="1">
      <Source /><Limits />
      <Tags>
        <Tag id="SystemName" kind="enum" value="SYS_NAV" />
        <Tag id="ResetProof" kind="boolean" value="false" />
        <Tag id="Loggable" kind="boolean" value="false" />
        <Tag id="LogEncryption" kind="boolean" value="false" />
        <Tag id="ParamMode" kind="enum" value="PARAM_MODE_USER" />
      </Tags>
      <Fields>
        <Parameter name="collor" kind="primitive" enable="true" gsName="Co"
                   valueType="int16_t" arraySize="1">
          <Source /><Limits default="1" minimum="1" maximum="100" resolution="1" /><Tags />
        </Parameter>
        <Parameter name="alive" kind="primitive" enable="true" gsName="Alive"
                   valueType="bool_t" arraySize="2">
          <Source /><Limits /><Tags />
        </Parameter>
      </Fields>
    </Parameter>
  </Parameters>
</ParameterListModel>
"""

_ONE_TYPE_TWO_USES_TYPES = """<?xml version='1.0' encoding='utf-8'?>
<ParameterListTypes schemaVersion="1.0" generator="parameter_list_code_generator"
                    generatorVersion="1.0.0">
  <StructType name="Stest">
    <Field name="collor" valueType="int16_t" />
    <Field name="alive" valueType="bool_t" arraySize="2" />
  </StructType>
</ParameterListTypes>
"""

#: Both parameters are instances of ONE type.  This does not even compile if
#: the generator goes back to giving each parameter a typedef of its own.
_ONE_TYPE_TWO_USES_CHECKS = """
    /* Two parameters of one structure type are two instances of ONE type. */
    {
        sCgStruct_Stest *first = &Cg_SmartData_MyStr;
        sCgStruct_Stest *second = &Cg_SmartData_MyStr2;
        if ((void *)first == (void *)second || STEST_ALIVE_ARRAY_SIZE != 2U) {
            printf("the two instances of Stest are wrong\\n");
            return 1;
        }
    }
#ifdef MY_STR_ALIVE_ARRAY_SIZE
    printf("a per-parameter array size macro is still generated\\n");
    return 1;
#endif
"""

#: What the struct array must produce, checked by the compiler and at run time.
_STRUCT_ARRAY_CHECKS = """
    /* An array field's size belongs to the TYPE that declares it: 'Wheels' is a
       field of type 'Car', 'Samples' a field of type 'Wheels'. */
    if (CAR_WHEELS_ARRAY_SIZE != 2U || WHEELS_SAMPLES_ARRAY_SIZE != 4U) {
        printf("array size macros are wrong\\n");
        return 1;
    }
    /* Two elements of one struct array are two separate values. */
    if ((void *)&Cg_SmartData_Car.Wheels[0].Speed
        == (void *)&Cg_SmartData_Car.Wheels[1].Speed) {
        printf("the elements of the struct array alias each other\\n");
        return 1;
    }
    /* Each element has its own row, pointing inside that element. */
    if (ParameterList[CAR_WHEELS_1_SPEED].pSmartData
        != (void *)&Cg_SmartData_Car.Wheels[1].Speed) {
        printf("the descriptor does not point at the element\\n");
        return 1;
    }
    /* One row per VALUE: Samples[4] is four rows, not one row of four, and the
       four of them are consecutive indices starting at the element-0 macro. */
    if (CAR_WHEELS_0_SAMPLES_1 != CAR_WHEELS_0_SAMPLES_0 + 1
        || CAR_WHEELS_0_SAMPLES_3 != CAR_WHEELS_0_SAMPLES_0 + 3
        || CAR_WHEELS_1_SPEED != CAR_WHEELS_0_SAMPLES_3 + 1) {
        printf("the elements of an array are not consecutive rows\\n");
        return 1;
    }
    /* Each of those rows points at its own element of the one C array. */
    if (ParameterList[CAR_WHEELS_0_SAMPLES_2].pSmartData
        != (void *)&Cg_SmartData_Car.Wheels[0].Samples[2]) {
        printf("an array element row does not point at its element\\n");
        return 1;
    }
    /* A log id counts values, never bytes: Samples[4] takes four of them.
       It is a plain uint16_t field and not a tag - it carries no classification
       of its own, so it is not one of the TagXxx fields below. */
    if (ParameterList[CAR_WHEELS_0_SPEED].LogId != 600U
        || ParameterList[CAR_WHEELS_0_SAMPLES_0].LogId != 601U
        || ParameterList[CAR_WHEELS_0_SAMPLES_3].LogId != 604U
        || ParameterList[CAR_WHEELS_1_SPEED].LogId != 605U
        || ParameterList[CAR_VIN].LogId != 610U) {
        printf("the log ids of the struct array are wrong\\n");
        return 1;
    }
    /* A description belongs to the VALUE.  Two elements of one field read
       differently here, and every other element reads the field's own - which
       is what element [0] of an array shows and edits in the editor. */
    if (strcmp(ParameterList[CAR_WHEELS_1_SPEED].pDescription,
               "How fast the REAR wheel turns.") != 0
        || strcmp(ParameterList[CAR_WHEELS_0_SPEED].pDescription,
                  "How fast a wheel turns.") != 0) {
        printf("an element's own description did not reach the table\\n");
        return 1;
    }
    if (strcmp(ParameterList[CAR_WHEELS_0_SAMPLES_2].pDescription,
               "The third sample of the front wheel.") != 0
        || strcmp(ParameterList[CAR_WHEELS_0_SAMPLES_3].pDescription,
                  "One sample.") != 0
        || strcmp(ParameterList[CAR_WHEELS_1_SAMPLES_2].pDescription,
                  "One sample.") != 0) {
        printf("an element path names the wrong value\\n");
        return 1;
    }
    /* So does the User Name, in pUserName: an element may have its own, the
       rest read the field's, and a field with none reads its structure's. */
    if (strcmp(ParameterList[CAR_WHEELS_1_SPEED].pUserName, "Rear wheel speed") != 0
        || strcmp(ParameterList[CAR_WHEELS_0_SPEED].pUserName, "Speed") != 0
        || strcmp(ParameterList[CAR_WHEELS_1_SAMPLES_0].pUserName, "First rear sample") != 0
        || strcmp(ParameterList[CAR_WHEELS_1_SAMPLES_1].pUserName, "Samples") != 0
        || strcmp(ParameterList[CAR_WHEELS_1_SAMPLES_0].pDescription, "One sample.") != 0
        || strcmp(ParameterList[CAR_VIN].pUserName, "Car") != 0) {
        printf("a value's User Name did not reach the table\\n");
        return 1;
    }
    /* The unit lives on the smart data object, not on the descriptor. */
    if (Cg_SmartData_Car.Wheels[0].Speed.pUnit == NULL
        || strcmp(Cg_SmartData_Car.Wheels[0].Speed.pUnit, "m/s") != 0) {
        printf("the unit did not reach the smart data object\\n");
        return 1;
    }
    if (Cg_SmartData_Car.Vin.pUnit == NULL
        || Cg_SmartData_Car.Vin.pUnit[0] != '\\0') {
        printf("a value with no unit should carry nothing\\n");
        return 1;
    }
    /* Writing one element leaves its neighbour alone.  There is one Read and
       one Write per type; nothing is reached through a vtable any more. */
    {
        float32_t written = 12.5F;
        float32_t readBack = 1.0F;
        if (fSmartData_F32_Write(&Cg_SmartData_Car.Wheels[1].Speed, &written)
            != eSMART_DATA_OK) {
            printf("writing an element of the struct array failed\\n");
            return 1;
        }
        (void)fSmartData_F32_Read(&Cg_SmartData_Car.Wheels[0].Speed, &readBack);
        if (readBack != 0.0F) {
            printf("writing one element disturbed its neighbour\\n");
            return 1;
        }
        (void)fSmartData_F32_Read(&Cg_SmartData_Car.Wheels[1].Speed, &readBack);
        if (readBack != 12.5F) {
            printf("the element did not keep the value that was written\\n");
            return 1;
        }
    }

    /* A write tells EVERY reader there is something new; each reader consumes
       that notification on its own, without affecting the others. */
    {
        float32_t value = 1.0F;
        float32_t got = 0.0F;

        (void)fSmartData_F32_Write(&Cg_SmartData_Car.Wheels[0].Speed, &value);

        if (fSmartData_F32_ReadIfIsNewForId(&Cg_SmartData_Car.Wheels[0].Speed,
                                            &got, eSMART_DATA_USER_ID_1)
            != eSMART_DATA_OK || got != 1.0F) {
            printf("the first reader did not get the new value\\n");
            return 1;
        }
        if (fSmartData_F32_ReadIfIsNewForId(&Cg_SmartData_Car.Wheels[0].Speed,
                                            &got, eSMART_DATA_USER_ID_1)
            != eSMART_DATA_ERROR_NO_NEW_DATA) {
            printf("a reader was told twice about one write\\n");
            return 1;
        }
        if (fSmartData_F32_ReadIfIsNewForId(&Cg_SmartData_Car.Wheels[0].Speed,
                                            &got, eSMART_DATA_USER_ID_2)
            != eSMART_DATA_OK) {
            printf("one reader consumed another reader notification\\n");
            return 1;
        }

        /* A write the range check refuses changes nothing at all - not the
           value, and not the readers. */
        value = -1.0F;
        if (fSmartData_F32_Write(&Cg_SmartData_Car.Wheels[0].Speed, &value)
            == eSMART_DATA_OK) {
            printf("an out of range write was accepted\\n");
            return 1;
        }
        (void)fSmartData_F32_Read(&Cg_SmartData_Car.Wheels[0].Speed, &got);
        if (got != 1.0F) {
            printf("a refused write changed the value anyway\\n");
            return 1;
        }
        if (fSmartData_F32_ReadIfIsNewForId(&Cg_SmartData_Car.Wheels[0].Speed,
                                            &got, eSMART_DATA_USER_ID_3)
            != eSMART_DATA_OK) {
            printf("a refused write consumed a reader notification\\n");
            return 1;
        }
    }

    /* The second way to write: through the descriptor, which does the same
       range checked write and THEN raises the change event. */
    {
        float32_t got = 0.0F;
        sParameterDescriptor *pRow =
            (sParameterDescriptor *)fParameterList_GetByIndex(CAR_WHEELS_0_SPEED);

        gWriteEventCount = 0U;
        if (fParameterDescriptor_WriteF32(pRow, 7.5F) != ePARAMETER_DESCRIPTOR_OK) {
            printf("the descriptor write failed\\n");
            return 1;
        }
        (void)fSmartData_F32_Read(&Cg_SmartData_Car.Wheels[0].Speed, &got);
        if (got != 7.5F) {
            printf("the descriptor write did not reach the smart data\\n");
            return 1;
        }
        if (gWriteEventCount != 1U) {
            printf("the descriptor write did not raise the change event\\n");
            return 1;
        }

        /* A refused write must report the failure AND leave the event
           unraised: nothing changed, so nobody is told. */
        if (fParameterDescriptor_WriteF32(pRow, -1.0F) == ePARAMETER_DESCRIPTOR_OK) {
            printf("the descriptor accepted an out of range write\\n");
            return 1;
        }
        if (gWriteEventCount != 1U) {
            printf("a refused descriptor write still raised the event\\n");
            return 1;
        }
        (void)fSmartData_F32_Read(&Cg_SmartData_Car.Wheels[0].Speed, &got);
        if (got != 7.5F) {
            printf("a refused descriptor write changed the value\\n");
            return 1;
        }
    }

"""


# smart_data.c includes the project's chrono.h. When the firmware's real
# chrono module is not reachable from here, this stub stands in for it; the
# stub folder is searched LAST, so a real chrono.h always wins.
_CHRONO_STUB_H = """
#ifndef CHRONO_H
#define CHRONO_H
#include <stdint.h>
static uint64_t fChrono_GetContinuousTickUs(void) { return 0U; }
#endif
"""

def compile_c(work_dir: Path, includes: List[str], with_example: bool = True) -> bool:
    """The example uses the demo parameters, so it only fits the XML model."""
    sources = [
        SMART_DATA_DIR / "smart_data.c",
        # the second write path - the one that raises the change event - lives
        # here, so it belongs in every build the test makes
        PARAMETER_DESCRIPTOR_DIR / "parameter_descriptor.c",
        work_dir / "generated" / "cg_smart_data.c",
        work_dir / "generated" / "cg_parameter_list.c",
    ]
    if with_example:
        sources.append(DOCS_DIR / "example" / "parameter_list_usage_example.c")
    sources.append(work_dir / "main.c")
    command = [C_COMPILER, "-std=c99", "-Wall", "-Wextra", "-Wpedantic",
               *includes, *[str(path) for path in sources],
               "-o", str(work_dir / "parameter_list_test")]
    result = _run(command)
    if result.returncode != 0:
        print(paint("C compilation FAILED:", BOLD + BRIGHT_RED) + "\n" + result.stderr)
        return False
    if result.stderr.strip():
        print("C compiler warnings:\n" + result.stderr)
    return True


def compile_cxx(work_dir: Path, includes: List[str]) -> bool:
    """The generated headers must be usable from C++ as well."""
    source = work_dir / "cxx_include_test.cpp"
    source.write_text(
        '#include "cg_parameter_list.h"\n'
        '#include "cg_smart_data.h"\n'
        '#include "cg_parameter_list_defines.h"\n'
        '#include "cg_parameter_list_table.h"\n'
        '#include "cg_parameter_list_types.h"\n'
        "int main() { return ParameterList[0].pSmartData == 0; }\n",
        encoding="utf-8")
    command = [CXX_COMPILER, "-std=c++11", "-Wall", "-Wextra", "-c",
               *includes, str(source), "-o", str(work_dir / "cxx_include_test.o")]
    result = _run(command)
    if result.returncode != 0:
        print(paint("C++ compilation FAILED:", BOLD + BRIGHT_RED) + "\n" + result.stderr)
        return False
    return True


def compile_firmware_defines(work_dir: Path, includes: List[str]) -> bool:
    """A system name the firmware has defined already keeps the firmware's value.

    The system names and the parameter modes are written ``#ifndef`` - the
    firmware may define SYS_NAV itself - so including the header after the
    firmware's own define must neither warn about a redefinition (-Werror) nor
    change the value.  (Asked for.)
    """
    header = (work_dir / "generated" / "cg_parameter_list_defines.h").read_text(
        encoding="utf-8")
    if "typedef enum" in header:
        print(paint("  FAILED: the system names / parameter modes are still an enum.",
                    BOLD + BRIGHT_RED))
        return False
    found = re.search(r"^#ifndef (SYS_\w+)$", header, re.MULTILINE)
    if found is None:
        print(paint("  FAILED: no '#ifndef SYS_...' define in the header.",
                    BOLD + BRIGHT_RED))
        return False
    name = found.group(1)
    source = work_dir / "firmware_defines_first.c"
    source.write_text(
        f"#define {name} 4000000000U   /* the firmware's own */\n"
        '#include "cg_parameter_list_defines.h"\n'
        f"typedef char firmware_value_kept[({name} == 4000000000U) ? 1 : -1];\n"
        "int main(void) { return (int)sizeof(firmware_value_kept) - 1; }\n",
        encoding="utf-8")
    command = [C_COMPILER, "-std=c99", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
               "-c", *includes, str(source), "-o", str(work_dir / "firmware_defines.o")]
    result = _run(command)
    if result.returncode != 0:
        print(paint(f"  FAILED: defining {name} before the header broke it:",
                    BOLD + BRIGHT_RED) + "\n" + result.stderr)
        return False
    return True


_MAIN_HEAD = """
#include <stdio.h>
#include <string.h>
#include "cg_parameter_list.h"
#include "cg_smart_data.h"
#include "cg_parameter_list_table.h"
#include "parameter_descriptor.h"

/* The change event is a weak callback, so the test overrides it and counts the
   calls. That is the only way to prove it fires on an accepted write and stays
   quiet on a refused one. Its signature is the one parameter_descriptor.h
   declares - the library is the firmware's, so the test follows it. */
static unsigned gWriteEventCount = 0U;
void fParameterDescriptor_ParameterWriteCompletedCallback(const sParameterDescriptor *sender,
                                                          void *pEv) {
    (void)sender;
    (void)pEv;
    gWriteEventCount++;
}
"""

_MAIN_HEAD_WITH_EXAMPLE = _MAIN_HEAD + '#include "parameter_list_usage_example.h"\n'

_MAIN_BODY = """
int main(void) {
    uint16_t index = 0U;
    uint8_t result = fParameterList_Init();
    if (result != 0U) {
        printf("fParameterList_Init failed with %u\\n", (unsigned)result);
        return 1;
    }
    if (fParameterList_GetQuantity() != PARAMETER_LIST_QTY) {
        printf("wrong quantity\\n");
        return 1;
    }
    for (index = 0U; index < PARAMETER_LIST_QTY; index++) {
        const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);
        if (pDescriptor == NULL || pDescriptor->pName == NULL) {
            printf("descriptor %u is broken\\n", (unsigned)index);
            return 1;
        }
        if (fParameterList_GetByName(pDescriptor->pName) != pDescriptor) {
            printf("lookup by name failed for %s\\n", pDescriptor->pName);
            return 1;
        }
        if (pDescriptor->pSmartData == NULL) {
            printf("no smart data for %s\\n", pDescriptor->pName);
            return 1;
        }
        /* Every row carries a User Name - "" at worst, never NULL - so a
           printf("%s") of it is always safe. */
        if (pDescriptor->pUserName == NULL || pDescriptor->pDescription == NULL) {
            printf("a string of %s is NULL\\n", pDescriptor->pName);
            return 1;
        }
    }
    if (fParameterList_GetByIndex(PARAMETER_LIST_QTY) != NULL) {
        printf("out of range index was accepted\\n");
        return 1;
    }
    EXAMPLE_CALLS
    EXTRA_CHECKS
    printf("OK: %u parameters initialised and verified" EXAMPLE_NOTE "\\n",
           (unsigned)PARAMETER_LIST_QTY);
    return 0;
}
"""

#: What the usage example must do on ANY model that holds the parameters it
#: names, so nothing here depends on a limit or a default.
_EXAMPLE_CALLS = """
    /* The usage example must work as well. */
    {
        float32_t airspeed = 0.0f;
        uint8_t cups = 0U;
        uint16_t loggable = 0U;

        /* use up this reader's "new" flag: only a real start-up brings it back */
        (void)fExample_ReadIfNew(&airspeed);
        if (fExample_Start() != 0U) {
            printf("fExample_Start failed\\n");
            return 1;
        }
        /* straight after start-up every reader is told once, then it is quiet */
        if (fExample_ReadIfNew(&airspeed) != TRUE || fExample_ReadIfNew(&airspeed) != FALSE) {
            printf("fExample_ReadIfNew failed\\n");
            return 1;
        }
        if (fExample_Read(&airspeed) != eSMART_DATA_OK) {
            printf("fExample_Read failed\\n");
            return 1;
        }
        if (fExample_StructAccess(&cups) != eSMART_DATA_OK) {
            printf("fExample_StructAccess failed\\n");
            return 1;
        }
        if (fExample_ArrayAccess() != POSITION_SAMPLES_ARRAY_SIZE) {
            printf("fExample_ArrayAccess failed\\n");
            return 1;
        }
        for (index = 0U; index < PARAMETER_LIST_QTY; index++) {
            if (ParameterList[index].TagLoggable != 0U) {
                loggable++;
            }
        }
        if (fExample_WalkTable() != loggable) {
            printf("fExample_WalkTable counted %u, not %u\\n",
                   (unsigned)fExample_WalkTable(), (unsigned)loggable);
            return 1;
        }
    }
"""

#: The two ways to write, against the limits of Airspeed in the example's own
#: model (0 .. 120).  Only that model can be asked for these numbers.
_EXAMPLE_FIXTURE_CHECKS = """
    {
        float32_t airspeed = 0.0f;
        unsigned events = gWriteEventCount;

        if (fExample_Write(50.0f) != eSMART_DATA_OK) {
            printf("fExample_Write refused a value in range\\n");
            return 1;
        }
        if (fExample_Write(500.0f) != eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE) {
            printf("fExample_Write accepted a value out of range\\n");
            return 1;
        }
        (void)fExample_Read(&airspeed);
        if (airspeed != 50.0f) {
            printf("a refused write changed the value\\n");
            return 1;
        }
        if (gWriteEventCount != events) {
            printf("the quiet write raised the change event\\n");
            return 1;
        }
        if (fExample_WriteAndNotify(60.0f) != ePARAMETER_DESCRIPTOR_OK
            || gWriteEventCount != events + 1U) {
            printf("fExample_WriteAndNotify did not raise the event\\n");
            return 1;
        }
        if (fExample_WriteAndNotify(500.0f) != ePARAMETER_DESCRIPTOR_ERROR_WRITE
            || gWriteEventCount != events + 1U) {
            printf("a refused fExample_WriteAndNotify raised the event\\n");
            return 1;
        }
    }
    {
        /* the field of the structure the example reads: its default, 3 cups */
        uint8_t cups = 0U;

        if (fExample_StructAccess(&cups) != eSMART_DATA_OK || cups != 3U) {
            printf("fExample_StructAccess read %u cups, not the default 3\\n",
                   (unsigned)cups);
            return 1;
        }
    }
    {
        /* read and write by index, one pair for every data type: the same
           objects the names reach, refused when the index or the type is wrong */
        uint8_t cups = 0U;
        uint8_t seven = 7U;
        uint8_t thirty = 30U;
        uint16_t year = 0U;
        uint32_t bugs = 4000000000U;
        float32_t airspeed = 0.0f;
        float64_t lat = 35.7;
        float64_t tooFar = 100.0;
        float64_t f64 = 0.0;
        int16_t sample = -5;
        int16_t i16 = 0;
        bool_t flag = FALSE;
        int8_t i8 = 0;
        int32_t i32 = 0;
        uint64_t u64 = 0U;
        int64_t i64 = 0;

        if (fSmartData_U8_ReadByIndex(REZA_SAEEDI_COFFEE_CUPS_PER_DAY, &cups) != eSMART_DATA_OK
            || cups != 3U) {
            printf("fSmartData_U8_ReadByIndex read %u cups, not the default 3\\n",
                   (unsigned)cups);
            return 1;
        }
        if (fSmartData_U8_WriteByIndex(REZA_SAEEDI_COFFEE_CUPS_PER_DAY, &seven) != eSMART_DATA_OK
            || fSmartData_U8_Read(&Cg_SmartData_RezaSaeedi.CoffeeCupsPerDay, &cups) != eSMART_DATA_OK
            || cups != 7U) {
            printf("fSmartData_U8_WriteByIndex did not write the object the name reaches\\n");
            return 1;
        }
        if (fSmartData_U8_WriteByIndex(REZA_SAEEDI_COFFEE_CUPS_PER_DAY, &thirty)
                != eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE
            || fSmartData_U8_ReadByIndex(REZA_SAEEDI_COFFEE_CUPS_PER_DAY, &cups) != eSMART_DATA_OK
            || cups != 7U) {
            printf("fSmartData_U8_WriteByIndex took 30 cups (maximum 20)\\n");
            return 1;
        }
        if (fSmartData_U16_ReadByIndex(REZA_SAEEDI_BIRTH_YEAR, &year) != eSMART_DATA_OK
            || year != 2000U) {
            printf("fSmartData_U16_ReadByIndex read %u, not the default 2000\\n",
                   (unsigned)year);
            return 1;
        }
        if (fSmartData_U32_WriteByIndex(REZA_SAEEDI_BUGS_FIXED_TODAY, &bugs) != eSMART_DATA_OK) {
            printf("fSmartData_U32_WriteByIndex refused a value in range\\n");
            return 1;
        }
        bugs = 0U;
        if (fSmartData_U32_ReadByIndex(REZA_SAEEDI_BUGS_FIXED_TODAY, &bugs) != eSMART_DATA_OK
            || bugs != 4000000000U) {
            printf("fSmartData_U32_ReadByIndex did not read back what was written\\n");
            return 1;
        }
        if (fSmartData_F64_WriteByIndex(POSITION_HOME_LAT, &lat) != eSMART_DATA_OK
            || fSmartData_F64_WriteByIndex(POSITION_HOME_LAT, &tooFar)
                != eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE
            || fSmartData_F64_Read(&Cg_SmartData_Position.Home.Lat, &f64) != eSMART_DATA_OK
            || f64 != 35.7) {
            printf("fSmartData_F64_WriteByIndex wrote the wrong value or object\\n");
            return 1;
        }
        if (fSmartData_I16_WriteByIndex(POSITION_SAMPLES_2, &sample) != eSMART_DATA_OK
            || fSmartData_I16_Read(&Cg_SmartData_Position.Samples[2], &i16) != eSMART_DATA_OK
            || i16 != -5
            || fSmartData_I16_Read(&Cg_SmartData_Position.Samples[1], &i16) != eSMART_DATA_OK
            || i16 != 0) {
            printf("fSmartData_I16_WriteByIndex wrote the wrong element of the array\\n");
            return 1;
        }
        /* Airspeed is a float32_t: every other type is refused, and leaves it alone */
        if (fSmartData_B8_ReadByIndex(AIRSPEED, &flag) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_B8_WriteByIndex(AIRSPEED, &flag) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_U8_WriteByIndex(AIRSPEED, &seven) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_I8_ReadByIndex(AIRSPEED, &i8) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_U16_WriteByIndex(AIRSPEED, &year) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_I16_ReadByIndex(AIRSPEED, &i16) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_U32_WriteByIndex(AIRSPEED, &bugs) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_I32_WriteByIndex(AIRSPEED, &i32) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_U64_ReadByIndex(AIRSPEED, &u64) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_I64_WriteByIndex(AIRSPEED, &i64) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_F64_WriteByIndex(AIRSPEED, &f64) != eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED
            || fSmartData_F32_ReadByIndex(AIRSPEED, &airspeed) != eSMART_DATA_OK
            || airspeed != 60.0f) {
            printf("a by-index function of the wrong type was not refused\\n");
            return 1;
        }
        if (fSmartData_F32_ReadByIndex((uint16_t)PARAMETER_LIST_QTY, &airspeed)
                != eSMART_DATA_ERROR_NULL_POINTER
            || fSmartData_F32_WriteByIndex((uint16_t)PARAMETER_LIST_QTY, &airspeed)
                != eSMART_DATA_ERROR_NULL_POINTER
            || fSmartData_F32_ReadByIndex(AIRSPEED, NULL) != eSMART_DATA_ERROR_NULL_POINTER) {
            printf("an index past the end or a NULL pointer was not refused\\n");
            return 1;
        }
    }
"""


def main_source(with_example: bool, extra_checks: str = "") -> str:
    head = _MAIN_HEAD_WITH_EXAMPLE if with_example else _MAIN_HEAD
    calls = _EXAMPLE_CALLS if with_example else ""
    note = '", usage example runs"' if with_example else '""'
    return (head + f"#define EXAMPLE_NOTE {note}\n"
            + _MAIN_BODY.replace("    EXAMPLE_CALLS", calls)
                        .replace("    EXTRA_CHECKS", extra_checks))


def _check_param_table(variant: dict, work_dir: Path) -> bool:
    """Generate the ADD_PARAM table, compile it, run it.

    The firmware defines what ADD_PARAM means and includes the header inside a
    function, so that is what the test does.  Counting the rows it expanded is
    what proves the file is really C and not merely the right shape.
    """
    lists = work_dir / "lists"
    lists.mkdir(exist_ok=True)
    for name, text in variant["files"].items():
        (lists / name).write_text(text, encoding="utf-8")

    print("  1/3 generating the table ...")
    config_path = write_config(
        work_dir, {"model_files": [str(lists / name) for name in variant["files"]]},
        output_format="param_table")
    exit_code = generator_main(["--config", str(config_path), "--quiet"])
    if exit_code != 0:
        print(f"  FAILED: the generator returned {exit_code} on the test's own "
              f"fixture, so the tool is at fault.")
        return False

    header = work_dir / "generated" / "nsrParamTables.h"
    if not header.is_file():
        print(f"  FAILED: no {header.name} was written.")
        return False

    (work_dir / "table_main.c").write_text(_PARAM_TABLE_MAIN, encoding="utf-8")

    print("  2/3 compiling as C99 ...")
    binary = work_dir / "param_table_test"
    result = _run([C_COMPILER, "-std=c99", "-Wall", "-Wextra", "-Werror",
                   f"-I{work_dir / 'generated'}",
                   str(work_dir / "table_main.c"), "-o", str(binary)])
    if result.returncode != 0:
        print("  FAILED: the generated table does not compile.")
        print(result.stderr.strip()[:2000])
        return False

    print("  3/3 running it ...")
    result = _run([str(binary)])
    if result.returncode != 0:
        print("  FAILED: the table did not expand as expected.")
        print((result.stdout + result.stderr).strip()[:1000])
        return False
    print(f"        OK: {result.stdout.strip()}")
    return True


def main() -> int:
    for compiler in (C_COMPILER, CXX_COMPILER):
        if not have_compiler(compiler):
            print(paint(f"SKIPPED: '{compiler}' was not found on the PATH.", YELLOW))
            return 0

    variants = input_variants()
    print(f"Checking {len(variants)} input variant(s).\n")

    for number, variant in enumerate(variants, start=1):
        label = variant["label"]
        with_example = variant.get("with_example", True)
        print(paint(f"=== {number}/{len(variants)}  {label} ===", CYAN))
        if not check_one(variant, with_example):
            return 1
        print()

    print(paint("All checks passed.", GREEN))
    return 0


def check_one(variant: dict, with_example: bool) -> bool:
    """Generate from *variant*, compile the result and run it."""
    with tempfile.TemporaryDirectory(prefix="pl_codegen_test_") as raw_dir:
        work_dir = Path(raw_dir)

        # A variant either points at a file of the project or brings its own
        # model along; a fixture keeps the test independent of what the user
        # happens to have in the editor.
        if variant.get("format") == "param_table":
            return _check_param_table(variant, work_dir)

        inputs = variant.get("inputs")
        if inputs is None:
            fixture = work_dir / "fixture.xml"
            fixture.write_text(variant["fixture"], encoding="utf-8")
            if variant.get("structures"):
                # the types file lives beside its list, named after it
                (work_dir / "fixture_types.xml").write_text(
                    variant["structures"], encoding="utf-8")
            inputs = {"model_files": [str(fixture)]}

        print("  1/5 generating the code ...")
        config_path = write_config(work_dir, inputs)
        exit_code = generator_main(["--config", str(config_path), "--quiet"])
        if exit_code != 0:
            # Two very different things end up here and they need different
            # answers from the reader, so the message says which one it is: the
            # tool may be broken, or this project's own parameter lists may
            # simply not be valid right now.  Only the second is fixed in the
            # editor rather than in the code.
            if variant.get("inputs") is not None:
                print(f"  FAILED: the generator refused this project's parameter "
                      f"list(s) (exit {exit_code}).\n"
                      f"          The diagnostics above are about the MODEL, not "
                      f"about the tool - fix them in the editor and run again.")
            else:
                print(f"  FAILED: the generator returned {exit_code} on the "
                      f"test's own fixture, so the tool is at fault.")
            return False

        (work_dir / "main.c").write_text(
            main_source(with_example, variant.get("extra_checks", "")),
            encoding="utf-8")
        stub_dir = work_dir / "stubs"
        stub_dir.mkdir(exist_ok=True)
        (stub_dir / "chrono.h").write_text(_CHRONO_STUB_H, encoding="utf-8")
        includes = [f"-I{DOCS_DIR / 'example'}",
                    f"-I{SMART_DATA_DIR}",
                    f"-I{PARAMETER_DESCRIPTOR_DIR}",
                    f"-I{work_dir / 'generated'}",
                    f"-I{stub_dir}"]

        print("  2/5 compiling as C99 ...")
        if not compile_c(work_dir, includes, with_example):
            return False

        print("  3/5 compiling the headers as C++ ...")
        if not compile_cxx(work_dir, includes):
            return False

        print("  4/5 a system name the firmware defines first ...")
        if not compile_firmware_defines(work_dir, includes):
            return False

        print("  5/5 running the generated parameter list ...")
        result = _run([str(work_dir / "parameter_list_test")])
        print("        " + result.stdout.strip())
        if result.returncode != 0:
            print(paint("  FAILED: the test program returned a non-zero exit code.",
                        BOLD + BRIGHT_RED))
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
