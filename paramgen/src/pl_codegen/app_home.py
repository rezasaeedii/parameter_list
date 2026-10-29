"""Where the app is installed, and what ships with it.

The tool now has two halves that live in different places:

  * **the app** - this folder.  The editor, the generator, the tests, the
    manuals and the templates.  Installed once on a machine, shared by every
    project, and never written to while a project is being edited.
  * **a project** - a folder somewhere else entirely, holding one project file
    (``pl_project.json``), the parameter lists and the generated output.

Anything that belongs to the *app* is found from here, so a project never has
to know where the app was unpacked.  That is what lets a project folder be
moved, copied to another machine or e-mailed to somebody: nothing inside it
points outwards.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

#: The ``paramgen`` folder.  This module is ``paramgen/src/pl_codegen/app_home.py``, so
#: the app is three levels up.
APP_DIR = Path(__file__).resolve().parent.parent.parent

#: The code itself.  The entry points in ``bin/`` put this on the import path.
SRC_DIR = APP_DIR / "src"

#: The entry points - one small file per action, all behind the launcher.
BIN_DIR = APP_DIR / "bin"

#: What a person starts the tool with on THIS machine: ``run.bat`` on Windows,
#: its twin ``run.sh`` everywhere else.  A message that tells somebody how to
#: run something names this, never one of the two by hand - a Linux user told
#: to double-click run.bat has been told the one thing that cannot work there.
LAUNCHER = "run.bat" if os.name == "nt" else "./run.sh"

#: State the app writes: which projects were open recently.  Not shipped, and
#: safe to delete.
VAR_DIR = APP_DIR / "var"

#: The manuals and their sources.
DOCS_DIR = APP_DIR / "docs"

#: Files the app ships for projects to start from.
TEMPLATES_DIR = APP_DIR / "templates"

#: The C library the generated code plugs into: ``smart_data`` and
#: ``parameter_descriptor``, kept beside this app in the same git repository
#: rather than inside it - see the ``smart_data/`` and ``parameter_descriptor/``
#: folders next to this one.  It is the firmware's, not the tool's, so a
#: firmware tree that vendors this repository pins its own commit of it; the
#: tool only ever reads it, never copies it into a project.
SMART_DATA_DIR = APP_DIR.parent / "smart_data"
PARAMETER_DESCRIPTOR_DIR = APP_DIR.parent / "parameter_descriptor"

#: The company's C file template (a VS Code snippet file).  Every project on a
#: machine uses the same one unless it names its own.
SNIPPET_FILE = TEMPLATES_DIR / "c.json"

#: The project file a new project is copied from.
PROJECT_TEMPLATE = TEMPLATES_DIR / "pl_project.json"

#: Name of the project file inside a project folder.  It carries the tool's
#: initials on purpose: a project folder is usually one corner of a much bigger
#: project, where a file called "project.json" says nothing about whose project
#: it is - and collides with the first thing anybody else puts there.
PROJECT_FILE_NAME = "pl_project.json"

#: What that file was called before.  A project written then opens exactly as
#: it did: renaming it is the owner's to do, not the tool's.
LEGACY_PROJECT_FILE_NAME = "project.json"

#: Both names a project file is given by the tool.  The owner may rename it -
#: any JSON file holding a project is one, see :func:`is_project_file`.
PROJECT_FILES = (PROJECT_FILE_NAME, LEGACY_PROJECT_FILE_NAME)

#: A project file is a few hundred bytes.  A JSON file far bigger than this is
#: somebody's data, and reading every one of them only to say "no" would make
#: listing a folder of them crawl.
_PROJECT_FILE_MAX_BYTES = 1024 * 1024


def is_project_file(path: Path) -> bool:
    """Whether *path* is a project file - by what it holds, not by its name.  (Asked for.)

    A JSON object with at least one of a project's sections (``project``,
    ``inputs``, ``output``, ...), which is the very test opening one applies:
    the file may be called anything, because its owner may rename it.
    """
    from .config import SECTIONS, load_jsonc     # local: config imports this module

    path = Path(path)
    try:
        if path.suffix.lower() != ".json" or not path.is_file():
            return False
        if path.stat().st_size > _PROJECT_FILE_MAX_BYTES:
            return False
        data = load_jsonc(path)
    except Exception:      # noqa: BLE001 - unreadable or not JSON: not a project
        return False
    return isinstance(data, dict) and not SECTIONS.isdisjoint(data)


def project_files_in(folder: Path) -> List[Path]:
    """Every project file directly inside *folder*, by name order."""
    try:
        candidates = sorted(Path(folder).glob("*.json"), key=lambda item: item.name.lower())
    except OSError:
        return []
    return [path for path in candidates if is_project_file(path)]


def project_file_in(folder: Path) -> Path:
    """The project file of *folder*.

    ``pl_project.json`` when it is there, then the old ``project.json``, then -
    because the owner may have renamed it - the one JSON file of the folder
    that holds a project.  Everything that turns a FOLDER into a project file
    goes through here, so "the folder I dragged in" means the same thing to the
    editor, to the command line and to the Open dialog.  With none, or with
    several renamed ones to choose from, the default name comes back, so the
    message that follows names the file a project needs.
    """
    folder = Path(folder)
    current = folder / PROJECT_FILE_NAME
    legacy = folder / LEGACY_PROJECT_FILE_NAME
    if current.is_file():
        return current
    if legacy.is_file():
        return legacy
    found = project_files_in(folder)
    return found[0] if len(found) == 1 else current


def default_snippet_file() -> Optional[Path]:
    """The app's C template, or ``None`` when it is not there.

    ``None`` rather than an error: the snippet file only decides the *layout*
    of the generated files, so a missing one is worth working without.  A
    project that names a snippet file of its own still gets an error when that
    one is missing, because there somebody asked for a specific file.
    """
    return SNIPPET_FILE if SNIPPET_FILE.is_file() else None


def copy_lib_into(dest: Path) -> Path:
    """Copies ``smart_data/`` and ``parameter_descriptor/`` into *dest*.

    The app never does this for a real project (see :data:`SMART_DATA_DIR`);
    it is what a test uses to give its own throwaway project a compilable
    ``lib/`` folder, the same shape firmware gets when somebody copies the two
    folders in by hand.
    """
    dest = Path(dest)
    shutil.copytree(SMART_DATA_DIR, dest / "smart_data", dirs_exist_ok=True)
    shutil.copytree(PARAMETER_DESCRIPTOR_DIR, dest / "parameter_descriptor",
                    dirs_exist_ok=True)
    return dest


#: The editor's own state: which project is open, and which were open before.
#: It belongs to the app rather than to any project, and it is safe to delete -
#: the next start simply has an empty recent list.
SETTINGS_FILE = VAR_DIR / "settings.json"


def read_settings(path: Optional[Path] = None) -> Dict[str, Any]:
    """The app settings, or an empty dict for anything wrong with them.

    A convenience file must never stop the tool from starting, so a missing,
    unreadable or corrupted one costs the recent list and nothing else.
    *path* is for a caller with a settings file of its own - a test; the app
    always uses :data:`SETTINGS_FILE`.
    """
    try:
        data = json.loads(Path(path or SETTINGS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_settings(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Write the app settings, shrugging off a read-only app folder."""
    target = Path(path or SETTINGS_FILE)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    except OSError:
        pass


def store_recent_entry(path: Path) -> str:
    """*path*, written the way it belongs in the "recent"/"current" list.

    Relative to :data:`APP_DIR` when that can be expressed, so an entry this
    file records still means the same project once the app and the project are
    both cloned or copied somewhere else together - this settings file goes
    into git with the rest of the app, and an absolute machine path in it is
    wrong on every machine but the one that wrote it.  An absolute path is
    written only when there truly is no relative route to the project, such as
    one on a different drive than the app on Windows.

    Forward slashes, as in the project file: every system reads them, and a
    Windows backslash is no separator at all on the Linux machine that clones
    the same repository.
    """
    resolved = Path(path).resolve()
    try:
        return Path(os.path.relpath(resolved, APP_DIR)).as_posix()
    except ValueError:          # a different drive: no relative path exists
        return resolved.as_posix()


def resolve_recent_entry(item: str) -> Path:
    """The path a "recent"/"current" entry names, however it was written.

    A relative entry is read against :data:`APP_DIR`, the way
    :func:`store_recent_entry` wrote it; an absolute one - including one an
    older version of the app wrote, before entries were relative - is used as
    it is.  Backslashes are read as separators on every system, so an entry
    written on Windows still names the same project on Linux.
    """
    path = Path(item.replace("\\", "/"))
    return path if path.is_absolute() else (APP_DIR / path).resolve()


def last_project() -> Optional[Path]:
    """The most recent project that is still on disk.

    This is what the generator falls back to when nobody says which project to
    build: somebody who has just been editing a project and asks for code
    means *that* project.
    """
    for item in read_settings().get("recent") or []:
        if not isinstance(item, str):
            continue
        path = resolve_recent_entry(item)
        if path.is_file():
            return path
    return None


def project_name(project_file: Path) -> str:
    """The name inside a project file, or the folder's name when it has none.

    Reading it needs the JSONC loader, so it lives here rather than being done
    twice - once by the editor's recent list and once by the menu.
    """
    from .config import load_jsonc          # local: config imports this module

    try:
        data = load_jsonc(Path(project_file))
        name = (data.get("project") or {}).get("name")
        if name:
            return str(name)
    except Exception:      # noqa: BLE001 - a listing must never fail on one bad row
        pass
    return Path(project_file).parent.name

