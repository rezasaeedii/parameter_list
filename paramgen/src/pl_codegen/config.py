"""Loading and validating a project file.

**The project file is the project.**  The folder it sits in is the project
root, and every relative path inside it is resolved from there - which is what
lets a project be moved, copied to another machine or handed to somebody else
and still work.  The editor and the generator are somewhere else entirely
(``paramgen/``), installed once per machine and shared by every project.

The one thing a project file may point *outside* itself with is a parameter
list: two projects that share a list both name the same file, and each keeps
its own build order, its own output folder and its own settings around it.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .app_home import (PROJECT_FILE_NAME, PROJECT_FILES, default_snippet_file,
                       project_files_in)
from .errors import CodeGeneratorError
from .logging_utils import get_logger
from .model.tags import optional_tags

#: What a generated file name / include guard may be made of.
_NAME_SAFE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: An indent string may only be made of spaces and tabs.  Anything else is put
#: at the start of generated C lines and simply does not compile.
_INDENT_SAFE = re.compile(r"[ \t]+")

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)


def load_jsonc(path: Path) -> Dict[str, Any]:
    """Load a JSON file that may contain ``//`` comments and trailing commas.

    The company's ``c.json`` snippet file uses the VS Code JSON-with-comments
    dialect, and it is convenient to allow the same in our own config file.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise CodeGeneratorError(f"Cannot read '{path}': {exc}") from exc

    text = _LINE_COMMENT.sub("", text)
    text = _TRAILING_COMMA.sub(r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodeGeneratorError(f"'{path}' is not valid JSON: {exc}") from exc


def relative_to_root(path: Union[str, Path], root: Path) -> str:
    """*path* the way a project names a file: from its root, with ``/``.

    ``C:\\Users\\me\\projects\\RHS\\parameter_lists\\core.xml`` in the project
    ``C:\\Users\\me\\projects\\RHS`` is ``parameter_lists/core.xml``.  That is
    how ``pl_project.json`` names its lists, and how a generated file has to name
    them too: a full path is one machine's folders, so the same build made on
    two machines differed in every file it wrote, and a project kept in git
    changed each time somebody else generated it.

    A file outside the root is reached with ``..``; one on another drive has no
    relative path at all and keeps its full one.  A path that is already
    relative is taken as relative to the root.
    """
    candidate = Path(str(path)).expanduser()
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        pass
    try:
        return Path(os.path.relpath(candidate, root)).as_posix()
    except ValueError:                  # another drive: no way there from the root
        return candidate.as_posix()


@dataclass
class ProjectConfig:
    """Who this project is.

    The name is what the editor puts in its title bar and what the log calls
    the build, so somebody with four projects open in four windows can tell
    which is which.  It is deliberately not derived from the folder name: a
    folder is renamed by accident, a name in the file is not.
    """

    name: str = ""
    description: str = ""


@dataclass
class InputConfig:
    """Where the parameter list comes from.

    A project is usually split over several units, each owned by a different
    team.  All of their lists live in one folder and this says which of them
    take part in a build and in what order; the generator merges them into one
    list, exactly as if they had been one file.
    """

    #: the XML models, in order.  The first one is the one the editor opens by
    #: default; every one of them is a parameter sublist of the project.
    model_files: List[Path] = field(default_factory=list)
    #: The folder that holds the parameter lists of the project.  A bare file
    #: name in ``model_files`` is looked up here, so a project keeps all of its
    #: lists in one place and the configuration only says which of them take
    #: part and in what order.  A path with a folder in it still works, so a
    #: sub-module that insists on keeping its list next to its own code can.
    model_directory: Path = Path("parameter_lists")

    @property
    def model_file(self) -> Optional[Path]:
        """The first model file, or ``None`` for a project with no list yet.

        A project created a moment ago has an empty ``model_files``, and that
        is an ordinary state the editor has to be able to show - so this
        answers ``None`` rather than raising, and the callers say what an
        empty project looks like on screen.
        """
        return self.model_files[0] if self.model_files else None


#: The two shapes the generated code can take.  ``smart_data`` is the current
#: firmware library - one object per value, a descriptor table, seven files.
#: ``param_table`` is the older firmware, which has none of that: one header
#: full of ADD_PARAM() lines and nothing else.
FORMAT_SMART_DATA = "smart_data"
FORMAT_PARAM_TABLE = "param_table"
OUTPUT_FORMATS = (FORMAT_SMART_DATA, FORMAT_PARAM_TABLE)


@dataclass
class OutputConfig:
    #: Which of the two the project wants.  It decides what is generated, and
    #: also what is *legal*: the older format has no structures and no arrays,
    #: so a list using them is an error here and perfectly fine in the other.
    format: str = FORMAT_SMART_DATA
    #: Where the generated ``.c`` / ``.h`` files go.  **This is the one to
    #: change** to write straight into a firmware tree.
    code_directory: Path = Path("cg_parameter_list")
    #: A copy of the merged model, written after every run.  It is not
    #: generated code: it is what the next run compares against to see whether
    #: the memory layout moved, and it is never written over a list the editor
    #: owns.  Spelled ``full_parameter_list_file`` in a project file;
    #: ``last_build_file``, ``snapshot_file`` and ``xml_file`` are older names
    #: and still work.
    xml_file: Path = Path("full_parameter_list/parameter_list.xml")
    file_prefix: str = "cg_"
    base_name: str = "parameter_list"


@dataclass
class StyleConfig:
    snippet_file: Optional[Path] = None
    company: str = "FAS"
    indent: str = "    "


@dataclass
class CodegenConfig:
    emit_description: bool = True
    emit_unit: bool = True
    emit_generation_info: bool = True
    emit_timestamp: bool = True
    index_define_prefix: str = ""
    offset_define_prefix: str = "PARAMETER_LIST_"
    smart_data_prefix: str = "Cg_SmartData_"
    struct_type_prefix: str = "sCgStruct_"
    descriptor_symbol: str = "ParameterList"
    quantity_define: str = "PARAMETER_LIST_QTY"
    #: extra ``#include`` lines for the generated .c file.  A free tag
    #: (Tag1..Tag4) may hold an application constant such as ``APP_FLAG_X``;
    #: without the header that declares it the generated file will not compile.
    extra_includes: List[str] = field(default_factory=list)


@dataclass
class ValidationConfig:
    treat_warnings_as_errors: bool = False
    require_unit: bool = False


@dataclass
class Config:
    """Fully resolved configuration."""

    path: Path
    project: ProjectConfig = field(default_factory=ProjectConfig)
    inputs: InputConfig = field(default_factory=InputConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    style: StyleConfig = field(default_factory=StyleConfig)
    codegen: CodegenConfig = field(default_factory=CodegenConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    #: What each free tag means in this project - ``{"Tag1": "Saveable"}`` -
    #: shown beside the tag in the editor and above the table in the code.
    #: A tag with no text is simply "Tag2", as it always was.  (Asked for.)
    tag_descriptions: Dict[str, str] = field(default_factory=dict)

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls, config_path: Union[str, Path]) -> "Config":
        # A plain string is what a caller reaches for first, and the bare
        # AttributeError it used to raise said nothing about the file at all.
        config_path = Path(config_path).expanduser().resolve()
        if not config_path.is_file():
            # "Configuration file ... does not exist" was true and unhelpful:
            # the reader has usually pointed at a FOLDER, and what they need to
            # hear is that the folder is not a project.  But only when it IS a
            # folder - naming one that is not there at all came back as
            # "'projects' is not a project: it has no demo in it", which takes a
            # moment to work out and says the wrong thing once you have.
            if config_path.name in PROJECT_FILES and config_path.parent.is_dir():
                several = project_files_in(config_path.parent)
                if len(several) > 1:
                    raise CodeGeneratorError(
                        f"'{config_path.parent}' holds {len(several)} project files "
                        f"({', '.join(item.name for item in several)}).\n"
                        f"Name the one you mean.")
                raise CodeGeneratorError(
                    f"'{config_path.parent}' is not a project: there is no "
                    f"{PROJECT_FILE_NAME} in it.\n"
                    f"Make one with the editor ('Project > New'), or name an "
                    f"existing project's folder.")
            raise CodeGeneratorError(
                f"'{config_path}' does not exist.\n"
                f"Name a project's folder, or its {PROJECT_FILE_NAME}.")

        data = load_jsonc(config_path)
        _refuse_a_file_that_is_not_a_project(config_path, data)
        root = config_path.parent

        def resolve(value: str) -> Path:
            candidate = Path(str(value)).expanduser()
            return candidate if candidate.is_absolute() else (root / candidate).resolve()

        _warn_unknown_sections(data)

        raw_project = data.get("project", {}) or {}
        _warn_unknown_keys("project", raw_project, {"name", "description"})
        project = ProjectConfig(
            # A project file with no name is still a project; falling back to
            # the folder it lives in beats an empty title bar.
            name=str(raw_project.get("name", "") or config_path.parent.name),
            description=str(raw_project.get("description", "") or ""))

        raw_inputs = data.get("inputs", {}) or {}
        _warn_unknown_keys("inputs", raw_inputs,
                           {"model_files", "model_file", "model_directory"})

        # 'model_files' is the list; 'model_file' is the one-file spelling of
        # the same thing, kept so a single-list config stays short.
        model_entries = raw_inputs.get("model_files") or []
        if not model_entries and raw_inputs.get("model_file"):
            model_entries = [raw_inputs["model_file"]]

        # A bare name such as "navigation.xml" means "the one in the project's
        # parameter-list folder"; anything with a folder in it keeps meaning
        # what it always meant, relative to this configuration file.
        model_directory = resolve(raw_inputs.get("model_directory", "parameter_lists"))

        def resolve_model(entry: str) -> Path:
            candidate = Path(str(entry)).expanduser()
            if candidate.is_absolute() or candidate.parent != Path("."):
                return resolve(entry)
            return (model_directory / candidate).resolve()

        inputs = InputConfig(
            model_files=[resolve_model(entry) for entry in model_entries],
            model_directory=model_directory,
        )

        raw_output = data.get("output", {}) or {}
        _warn_unknown_keys("output", raw_output,
                           {"format", "code_directory", "full_parameter_list_file",
                            "last_build_file", "snapshot_file", "xml_file",
                            "file_prefix", "base_name"})

        output_format = str(raw_output.get("format", FORMAT_SMART_DATA)).strip()
        if output_format not in OUTPUT_FORMATS:
            suggestion = _closest(output_format, OUTPUT_FORMATS)
            raise CodeGeneratorError(
                f"output.format is '{output_format}'."
                + (f" Did you mean '{suggestion}'?" if suggestion else "")
                + f"\nIt must be one of: {', '.join(OUTPUT_FORMATS)}.")

        # This key has had three names.  'xml_file' read like "where my
        # generated files go" - the one thing it is not.  'snapshot_file' said
        # nothing about what was in it.  'last_build_file' read as the embedded
        # build system.  What it really holds is every parameter of the system
        # merged into one XML, so that is what it is called; all three older
        # spellings still work, because project files in the field use them.
        _OLDER = ("last_build_file", "snapshot_file", "xml_file")
        snapshot = raw_output.get("full_parameter_list_file")
        for older in _OLDER:
            if snapshot is None:
                snapshot = raw_output.get(older)
        given = [key for key in ("full_parameter_list_file", *_OLDER)
                 if key in raw_output]
        if len(given) > 1:
            get_logger().warning(
                "output.%s are all set - '%s' is used; delete the others.",
                " and ".join(given), given[0])
        # An empty code_directory means the project's own folder.  Resolving
        # "" the ordinary way gives the folder the project file is in anyway,
        # but only by accident of how paths join - saying it here is what makes
        # it a promise rather than a coincidence.
        raw_code_directory = str(raw_output.get("code_directory", "cg_parameter_list"))
        code_directory = (root if not raw_code_directory.strip()
                          else resolve(raw_code_directory))

        output = OutputConfig(
            format=output_format,
            code_directory=code_directory,
            xml_file=resolve(snapshot or "full_parameter_list/parameter_list.xml"),
            file_prefix=str(raw_output.get("file_prefix", "cg_")),
            # The generated file names follow the first list only when nothing
            # was asked for; an empty project has no first list, and
            # 'parameter_list' is the name every project started with anyway.
            base_name=str(raw_output.get("base_name", "")
                          or (inputs.model_file.stem if inputs.model_file
                              else "parameter_list")),
        )

        raw_style = data.get("style", {}) or {}
        _warn_unknown_keys("style", raw_style, {"snippet_file", "company", "indent"})
        # The company's C template is the app's, not the project's: it is the
        # same file for every project on the machine, and a project that had
        # to point at it with '../../paramgen/templates/c.json' would stop working
        # the moment it was moved.  A project may still name one of its own.
        snippet = raw_style.get("snippet_file")
        style = StyleConfig(
            snippet_file=resolve(snippet) if snippet else default_snippet_file(),
            company=str(raw_style.get("company", "FAS")),
            indent=str(raw_style.get("indent", "    ")),
        )

        codegen = _dataclass_from_dict(CodegenConfig, data.get("codegen") or {}, "codegen")
        validation = _dataclass_from_dict(ValidationConfig, data.get("validation") or {},
                                          "validation")
        codegen.extra_includes = [str(entry) for entry in (codegen.extra_includes or [])]

        config = cls(path=config_path, project=project, inputs=inputs, output=output,
                     style=style, codegen=codegen, validation=validation,
                     tag_descriptions=_tag_descriptions(data.get("tag_descriptions")))
        config.validate()
        return config

    # -- checks ----------------------------------------------------------
    def validate(self) -> None:
        if self.style.snippet_file is not None and not self.style.snippet_file.is_file():
            raise CodeGeneratorError(
                f"Style snippet file '{self.style.snippet_file}' does not exist.")

        # 'indent' is written at the start of every indented line of generated
        # C.  Anything that is not whitespace turns into a syntax error in a
        # file the user never wrote, so it is refused here where the message can
        # still say which setting is at fault.
        if not self.style.indent or not _INDENT_SAFE.fullmatch(self.style.indent):
            shown = self.style.indent.replace("\t", "\\t")
            raise CodeGeneratorError(
                f"style.indent is '{shown}'. It is put at the start of every indented "
                f"line of the generated C code, so it may contain only spaces and tabs.\n"
                f"Set 'indent' in the 'style' section of {self.path.name} to spaces "
                f"(for example four of them) or to a tab.")

        # The file names become C include guards and #include lines, so they
        # have to survive being turned into identifiers.
        for key, value in (("output.base_name", self.output.base_name),
                           ("output.file_prefix", self.output.file_prefix)):
            if value and not _NAME_SAFE.fullmatch(value):
                raise CodeGeneratorError(
                    f"{key} is '{value}'. It becomes part of a file name and of a C "
                    f"include guard, so it may hold only letters, digits and '_'.\n"
                    f"Set '{key.split('.')[1]}' in the 'output' section of "
                    f"{self.path.name} to a plain name.")

    # -- helpers ---------------------------------------------------------
    def generated_file_name(self, suffix: str, extension: str) -> str:
        """``suffix='defines', extension='h'`` -> ``cg_parameter_list_defines.h``."""
        stem = f"{self.output.file_prefix}{self.output.base_name}"
        if suffix:
            stem = f"{stem}_{suffix}"
        return f"{stem}.{extension}"

    def smart_data_file_name(self, extension: str) -> str:
        return f"{self.output.file_prefix}smart_data.{extension}"


def _closest(key: str, candidates: Any) -> Optional[str]:
    """The known key closest to *key*, or ``None`` when nothing is close."""
    matches = difflib.get_close_matches(key, sorted(candidates), n=1, cutoff=0.7)
    return matches[0] if matches else None


#: The top-level sections a project file may have.  A file with none of them is
#: not a project file at all, whatever its name.
SECTIONS = frozenset({"project", "inputs", "output", "style", "codegen",
                      "validation", "tag_descriptions"})

#: The tags a project may describe: the free ones, Tag1 .. Tag4.
DESCRIBED_TAGS = tuple(spec.tag_id for spec in optional_tags())


def _tag_descriptions(raw: Any) -> Dict[str, str]:
    """``tag_descriptions`` as text per free tag; a key that is no free tag is reported."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        get_logger().warning("'tag_descriptions' is not an object of texts - it is ignored.")
        return {}
    _warn_unknown_keys("tag_descriptions", raw, set(DESCRIBED_TAGS))
    return {tag: " ".join(str(raw[tag] or "").split()) for tag in DESCRIBED_TAGS if tag in raw}


def _refuse_a_file_that_is_not_a_project(path: Path, data: Dict[str, Any]) -> None:
    """Refuse a JSON file that is simply not a project.

    Every JSON file on the machine used to load as a project, because nothing
    here is mandatory: an empty object is a project with all the defaults.  So
    opening, say, a tool's own settings file quietly succeeded and made **its
    folder** the project root - and the next Generate would have written the
    parameter list into somebody's home directory.

    One section is enough to be a project, and no real project has none of them.
    """
    if not isinstance(data, dict):
        raise CodeGeneratorError(
            f"'{path}' does not hold a JSON object, so it is not a project "
            f"file.\nA project file looks like {PROJECT_FILE_NAME} in "
            f"paramgen/templates.")
    if SECTIONS.isdisjoint(data):
        found = ", ".join(sorted(data)[:4]) or "nothing"
        raise CodeGeneratorError(
            f"'{path}' is not a project file: it has none of the sections a "
            f"project has ({', '.join(sorted(SECTIONS))}).\n"
            f"What it does have: {found}.\n"
            f"A project is a folder with a {PROJECT_FILE_NAME} in it - open "
            f"the folder, or copy paramgen/templates/{PROJECT_FILE_NAME} to start "
            f"one.")


def _warn_unknown_sections(data: Dict[str, Any]) -> None:
    """A whole section spelled wrongly does nothing at all - say so."""
    known = set(SECTIONS)
    logger = get_logger()
    for key in sorted(key for key in data if key not in known):
        suggestion = _closest(key, known)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        logger.warning("Unknown configuration section '%s' - it is ignored.%s", key, hint)


def _warn_unknown_keys(section: str, data: Dict[str, Any], known: Any) -> None:
    """Same check for the sections that are not built from a dataclass."""
    logger = get_logger()
    for key in sorted(key for key in data if key not in known):
        suggestion = _closest(key, known)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        logger.warning("Unknown configuration key '%s.%s' - it is ignored.%s",
                       section, key, hint)


def _dataclass_from_dict(cls: type, data: Dict[str, Any], section: str = "") -> Any:
    """Build a dataclass from a dict, warning about keys it does not know.

    An unknown key is nearly always a typo - ``emit_timestemp`` instead of
    ``emit_timestamp``.  Silently dropping it means the user changes the setting,
    sees no effect, and has no way of finding out why, so it is reported.
    """
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    unknown = sorted(key for key in data if key not in known)
    if unknown:
        logger = get_logger()
        for key in unknown:
            suggestion = _closest(key, known)
            hint = f" Did you mean '{suggestion}'?" if suggestion else ""
            logger.warning("Unknown configuration key '%s%s' - it is ignored.%s",
                           f"{section}." if section else "", key, hint)
    return cls(**{key: value for key, value in data.items() if key in known})
