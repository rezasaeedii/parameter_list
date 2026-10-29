"""The Project settings dialog: what ``pl_project.json`` says, and changing it.  (Asked for.)

Everything the dialog shows comes from the project file and everything it
changes goes back into it - nowhere else.  The file can be changed from three
places: this dialog, the Parameter sublists dialog, and by hand in an editor.
Three rules keep them in step:

* **The file is read when the dialog opens**, not taken from what the editor
  loaded earlier, and its fingerprint goes with it.  Applying checks the
  fingerprint first: a file changed on disk in between is not overwritten -
  the dialog is told and shows the file as it is now.
* **Only what was changed is written**, each value in place, so every other key,
  every comment and the layout of the file stay exactly as they were.  A key
  the file does not have is added; a project nobody touches is never rewritten,
  however old it is.
* **Applying reloads the project** from the file it has just written, so the
  editor, the generator and the sublists dialog all go on from the same text.

What a missing key means is decided where it always was - by
:meth:`pl_codegen.config.Config.load` - so the dialog shows what a build would
really use.  The templates in ``paramgen/templates`` are only what a NEW project
starts with.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pl_codegen.config import (DESCRIBED_TAGS, CodegenConfig, Config, ValidationConfig,
                               load_jsonc)
from pl_codegen.errors import CodeGeneratorError
from pl_codegen.naming import is_reserved_keyword, is_valid_c_identifier

from .config_file import set_json_value


class SettingsError(ValueError):
    """A change the dialog cannot make; *field* is the setting it is about."""

    def __init__(self, message: str, field: str = "") -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class Setting:
    """One value the dialog shows, at ``section.key`` in the project file."""

    key: str
    kind: str
    #: what a build uses when the file does not have it - the same fallback
    #: Config.load applies
    default: Any = ""
    #: older spellings of the same key, read and written where the file has one
    aliases: Tuple[str, ...] = ()
    #: whether an empty value is refused
    required: bool = False

    @property
    def path(self) -> Tuple[str, ...]:
        return tuple(self.key.split("."))


_CODEGEN = CodegenConfig()
_VALIDATION = ValidationConfig()

#: Every setting, in the order the dialog's pages show them.
SETTINGS: Tuple[Setting, ...] = (
    Setting("project.name", "text", required=True),
    Setting("project.description", "text"),
    Setting("output.format", "readonly", "smart_data"),
    Setting("output.code_directory", "path", "cg_parameter_list"),
    Setting("output.full_parameter_list_file", "path",
            "full_parameter_list/parameter_list.xml",
            aliases=("last_build_file", "snapshot_file", "xml_file"), required=True),
    Setting("output.file_prefix", "name", "cg_"),
    Setting("output.base_name", "name", ""),
    Setting("inputs.model_directory", "path", "parameter_lists", required=True),
    Setting("inputs.model_files", "lists", [], aliases=("model_file",)),
    Setting("style.company", "text", "FAS"),
    Setting("style.indent", "indent", "    ", required=True),
    Setting("codegen.emit_description", "bool", _CODEGEN.emit_description),
    Setting("codegen.emit_unit", "bool", _CODEGEN.emit_unit),
    Setting("codegen.emit_generation_info", "bool", _CODEGEN.emit_generation_info),
    Setting("codegen.emit_timestamp", "bool", _CODEGEN.emit_timestamp),
    Setting("codegen.index_define_prefix", "prefix", _CODEGEN.index_define_prefix),
    Setting("codegen.offset_define_prefix", "prefix", _CODEGEN.offset_define_prefix),
    Setting("codegen.smart_data_prefix", "prefix", _CODEGEN.smart_data_prefix),
    Setting("codegen.struct_type_prefix", "prefix", _CODEGEN.struct_type_prefix),
    Setting("codegen.descriptor_symbol", "identifier", _CODEGEN.descriptor_symbol,
            required=True),
    Setting("codegen.quantity_define", "identifier", _CODEGEN.quantity_define,
            required=True),
    Setting("codegen.extra_includes", "includes", []),
    Setting("validation.treat_warnings_as_errors", "bool",
            _VALIDATION.treat_warnings_as_errors),
    Setting("validation.require_unit", "bool", _VALIDATION.require_unit),
    *(Setting(f"tag_descriptions.{tag}", "text") for tag in DESCRIBED_TAGS),
)

SETTINGS_BY_KEY: Dict[str, Setting] = {setting.key: setting for setting in SETTINGS}


# -- reading -------------------------------------------------------------------
def fingerprint(raw: bytes) -> str:
    """What the dialog hands back on Apply, to tell a file changed in between."""
    return hashlib.sha256(raw).hexdigest()


def read_settings(config_path: Path) -> Dict[str, Any]:
    """Every setting as the project file holds it, for the dialog.

    ``present`` says whether the file has the key; a missing one shows the
    value a build would use, and stays missing until somebody changes it.
    """
    config_path = Path(config_path)
    raw = config_path.read_bytes()
    data = load_jsonc(config_path)
    values: Dict[str, Any] = {}
    present: Dict[str, bool] = {}
    for setting in SETTINGS:
        found, value = _lookup(data, setting)
        if not found:
            value = setting.default
            if setting.key == "project.name":
                # Config.load falls back to the folder for a project with no name
                value = config_path.parent.name
        values[setting.key] = value
        present[setting.key] = found
    return {
        "file": str(config_path),
        "fingerprint": fingerprint(raw),
        "values": values,
        "present": present,
        # what an empty base name turns into: the first sublist's name
        "firstList": _first_list_stem(values["inputs.model_files"]),
        # which of the sublists named are really there, for the dialog to mark
        "listsFound": {entry: list_path(config_path, values["inputs.model_directory"],
                                        entry).is_file()
                       for entry in values["inputs.model_files"]},
    }


def list_path(config_path: Path, model_directory: str, entry: str) -> Path:
    """Where a ``model_files`` entry points - resolved as Config.load resolves it:
    a bare name in the sublist folder, anything else from the project file."""
    root = Path(config_path).parent
    directory = Path(str(model_directory)).expanduser()
    directory = directory if directory.is_absolute() else root / directory
    candidate = Path(str(entry)).expanduser()
    if candidate.is_absolute():
        return candidate
    if candidate.parent != Path("."):
        return root / candidate
    return directory / candidate


def _lookup(data: Dict[str, Any], setting: Setting) -> Tuple[bool, Any]:
    """``(found, value)`` for *setting* in the file's *data*, older spellings included."""
    section, _, key = setting.key.partition(".")
    block = data.get(section)
    if not isinstance(block, dict):
        return False, None
    for name in (key, *setting.aliases):
        if name in block:
            value = block[name]
            if setting.kind == "lists" and name == "model_file":
                value = [value] if value else []
            return True, _shown(setting, value)
    return False, None


def _shown(setting: Setting, value: Any) -> Any:
    """A value of the file in the shape its control takes."""
    if setting.kind == "bool":
        return bool(value)
    if setting.kind in ("lists", "includes"):
        return [str(item) for item in (value or [])] if isinstance(value, list) else []
    return "" if value is None else str(value)


def _first_list_stem(entries: List[str]) -> str:
    return Path(str(entries[0])).stem if entries else "parameter_list"


# -- checking ------------------------------------------------------------------
def check_value(setting: Setting, value: Any) -> Any:
    """*value* as it will be written, or :class:`SettingsError` saying why not."""
    label = setting.key
    if setting.kind == "readonly":
        raise SettingsError(f"'{label}' is chosen when the project is made and cannot be "
                            f"changed here.", setting.key)
    if setting.kind == "bool":
        if not isinstance(value, bool):
            raise SettingsError(f"'{label}' is on or off.", setting.key)
        return value
    if setting.kind in ("lists", "includes"):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise SettingsError(f"'{label}' is a list of names.", setting.key)
        items = [item.strip() for item in value]
        if any(not item for item in items):
            raise SettingsError(f"'{label}' has an empty line. Fill it in or remove it.",
                                setting.key)
        for item in items:
            if "\n" in item or "\r" in item:
                raise SettingsError(f"'{item}' in '{label}' spans two lines.", setting.key)
        seen = set()
        for item in items:
            if item in seen:
                raise SettingsError(f"'{item}' is in '{label}' twice.", setting.key)
            seen.add(item)
        if setting.kind == "includes":
            for item in items:
                bare = item[1:-1] if (item[:1], item[-1:]) in (("<", ">"), ('"', '"')) else item
                if not bare or any(char in bare for char in '<>"'):
                    raise SettingsError(
                        f"'{item}' is not a header to include. Write it as app.h, "
                        f"\"app.h\" or <app.h>.", setting.key)
        return items

    if not isinstance(value, str):
        raise SettingsError(f"'{label}' is a text.", setting.key)
    if "\n" in value or "\r" in value:
        raise SettingsError(f"'{label}' has to fit on one line.", setting.key)
    if setting.kind == "indent":
        if not value or value.strip(" \t"):
            raise SettingsError("The indent may hold only spaces and tabs.", setting.key)
        return value
    text = value.strip()
    if setting.required and not text:
        raise SettingsError(f"'{label}' cannot be empty.", setting.key)
    if setting.kind == "name" and text and not _plain_name(text):
        raise SettingsError(
            f"'{text}' cannot be used in '{label}': it becomes part of every generated "
            f"file name and include guard, so it may hold only letters, digits and '_', "
            f"and may not start with a digit.", setting.key)
    if setting.kind in ("prefix", "identifier") and text:
        if not is_valid_c_identifier(text):
            raise SettingsError(
                f"'{text}' cannot be used in '{label}': it starts names in the generated "
                f"C code, so it may hold only letters, digits and '_', and may not start "
                f"with a digit.", setting.key)
        if setting.kind == "identifier" and is_reserved_keyword(text):
            raise SettingsError(f"'{text}' is a C keyword and cannot name '{label}'.",
                                setting.key)
    return text


def _plain_name(text: str) -> bool:
    return (text[0].isalpha() or text[0] == "_") and all(
        char.isalnum() or char == "_" for char in text) and text.isascii()


# -- writing -------------------------------------------------------------------
def new_text(config_path: Path, seen_fingerprint: str,
             changes: Dict[str, Any]) -> Tuple[str, bytes]:
    """The project file's new text with *changes* in it, and its old bytes.

    Nothing is written here.  Refused with :class:`SettingsError` when the file
    is not the one the dialog showed, or a change cannot be made.
    """
    config_path = Path(config_path)
    raw = config_path.read_bytes()
    if fingerprint(raw) != seen_fingerprint:
        raise SettingsError(
            f"{config_path.name} was changed outside this dialog after it opened. "
            f"It is shown as it is now - make your change again.", "")

    checked: Dict[str, Any] = {}
    for key, value in changes.items():
        setting = SETTINGS_BY_KEY.get(key)
        if setting is None:
            raise SettingsError(f"'{key}' is not a project setting.", key)
        checked[key] = check_value(setting, value)

    text = raw.decode("utf-8-sig")
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")
    data = load_jsonc(config_path)
    for key, value in checked.items():
        text = _set(text, data, SETTINGS_BY_KEY[key], value)
    if crlf:
        text = text.replace("\n", "\r\n")
    return ("﻿" if bom else "") + text, raw


def _set(text: str, data: Dict[str, Any], setting: Setting, value: Any) -> str:
    """*text* with one setting written where the file keeps it."""
    section, _, key = setting.key.partition(".")
    block = data.get(section) if isinstance(data.get(section), dict) else {}
    if key not in block:
        for older in setting.aliases:
            if older in block:
                if older == "model_file":
                    # the one-list spelling grows into the list
                    return set_json_value(text, (section, older), value, key_name=key)
                return set_json_value(text, (section, older), value)
    return set_json_value(text, (section, key), value)


def write(config_path: Path, text: str) -> None:
    """Write *text* as the project file - through a sibling file, so a failure
    half way never leaves half a project file behind."""
    config_path = Path(config_path)
    temporary = config_path.with_name(config_path.name + ".saving")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(config_path)


def load_candidate(config_path: Path, text: str) -> Config:
    """*text* loaded the way the editor will load it - from a file beside the
    project's, so every relative path means the same - before anything is written."""
    config_path = Path(config_path)
    candidate = config_path.with_name(config_path.name + ".checking")
    try:
        candidate.write_bytes(text.encode("utf-8"))
        try:
            config = Config.load(candidate)
        except CodeGeneratorError as error:
            raise SettingsError(str(error).replace(candidate.name, config_path.name)) from None
        config.path = config_path.resolve()
        return config
    finally:
        try:
            candidate.unlink()
        except OSError:
            pass

