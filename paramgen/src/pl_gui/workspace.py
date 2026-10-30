"""Which project the editor has open, and which ones it had before.

The editor is installed once per machine and edits *projects*, the way a text
editor is installed once and edits files.  So it needs a small amount of state
that belongs to neither: the project that is open right now, and the handful
that were open recently.

That state lives in one small JSON file in the app folder.  It holds nothing
but paths and is safe to delete: the next start simply opens nothing and shows
the list of recent projects as empty.

Nothing here writes into a project.  Opening a project reads its project file;
everything a project owns is written by :class:`~pl_gui.document.Document`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from pl_codegen.app_home import (PROJECT_FILE_NAME, PROJECT_TEMPLATE, SETTINGS_FILE,
                                 project_file_in, project_files_in, project_name,
                                 read_settings,
                                 resolve_recent_entry, store_recent_entry,
                                 write_settings)
from pl_codegen.config import (FORMAT_SMART_DATA, OUTPUT_FORMATS, Config,
                               load_jsonc)
from pl_codegen.errors import CodeGeneratorError

from .document import Document

#: How many projects the "recent" list keeps.
RECENT_LIMIT = 12


class Workspace:
    """The open project, plus the list of recent ones."""

    def __init__(self, settings_file: Path = SETTINGS_FILE) -> None:
        self.settings_file = Path(settings_file)
        self.document: Optional[Document] = None
        self._recent: List[str] = []
        self._read_settings()

    # -- the open project --------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self.document is not None

    @property
    def config(self) -> Optional[Config]:
        return self.document.config if self.document is not None else None

    def require(self) -> Document:
        """The open document, or a message saying there is no project.

        Every editing action goes through here, so "no project is open" is
        answered once, in words, instead of as an ``AttributeError`` on
        ``None`` in twenty different places.
        """
        if self.document is None:
            raise CodeGeneratorError(
                "No project is open. Use 'Project > Open' to open one, or "
                "'Project > New' to start one.")
        return self.document

    def open(self, path: Path) -> Document:
        """Open the project file at *path* and make it the current one.

        The old project is replaced only once the new one has loaded: a
        project file with a typo in it must not close what the user was
        working on.
        """
        path = Path(path).expanduser()
        # A folder is what a person drags in, and inside it is exactly one
        # obvious answer - so take the folder and mean the project file.  The
        # file may have been renamed; with several to choose from, say which.
        if path.is_dir():
            chosen = project_file_in(path)
            several = project_files_in(path)
            if not chosen.is_file() and len(several) > 1:
                raise CodeGeneratorError(
                    f"'{path}' holds {len(several)} project files "
                    f"({', '.join(item.name for item in several)}). "
                    f"Open the one you mean.")
            path = chosen
        path = path.resolve()

        if not path.is_file():
            raise CodeGeneratorError(
                f"'{path}' does not exist.\n"
                f"A project is a folder with a project file in it "
                f"(usually {PROJECT_FILE_NAME}).")

        config = Config.load(path)
        document = Document(config)
        document.load()

        self.document = document
        self.remember(path)
        return document

    def adopt(self, document: Document) -> None:
        """Take a document that was opened elsewhere as the current project.

        For a caller that already has one - the tests, which build a project in
        a temp folder.  Deliberately not the same as :meth:`open`: nothing is
        remembered, because a folder that will be deleted in a moment has no
        business in the list of recent projects.
        """
        self.document = document

    def close(self) -> None:
        """Put the editor back on the start screen.  Nothing is saved here."""
        self.document = None
        self._write_settings(current="")

    # -- making one --------------------------------------------------------
    def create(self, folder: Path, name: str,
               output_format: str = FORMAT_SMART_DATA) -> Path:
        """Write a new project into *folder* and return its project file.

        The folder is created if it is not there; an existing one is used as
        it is, so a project can be started inside a firmware tree that already
        exists.  What is refused is overwriting a project file that is already
        there - that is somebody's project, and "New" is not a way to lose it.

        *output_format* decides what the project generates, and with it what the
        folder even needs: a ``param_table`` project gets no ``lib/``, because
        the table it writes is macro lines the firmware expands itself - there
        is no smart-data library underneath it to copy.
        """
        name = str(name).strip()
        if not name:
            raise ValueError("A project needs a name.")
        if output_format not in OUTPUT_FORMATS:
            raise ValueError(
                f"'{output_format}' is not an output format. "
                f"Pick one of: {', '.join(OUTPUT_FORMATS)}.")
        for bad in '\\/:*?"<>|':
            if bad in name:
                raise ValueError(f"A project name cannot contain '{bad}'.")

        folder = Path(folder).expanduser()
        if not folder.is_absolute():
            raise ValueError(f"'{folder}' is not a full path.")

        # Either name counts as "there is a project here already": a folder
        # still holding the old project.json is somebody's project, and "New"
        # is not a way to lose it.
        existing = project_file_in(folder)
        if existing.exists():
            raise FileExistsError(
                f"'{existing}' already exists. Open it, or choose another folder.")
        # ...and so does a project file somebody renamed, however many there are
        renamed = project_files_in(folder) if folder.is_dir() else []
        if renamed:
            raise FileExistsError(
                f"'{folder}' already holds a project "
                f"({', '.join(item.name for item in renamed)}). Open it, or choose "
                f"another folder.")
        target = folder / PROJECT_FILE_NAME

        if not PROJECT_TEMPLATE.is_file():
            raise CodeGeneratorError(
                f"The project template '{PROJECT_TEMPLATE}' is missing. "
                f"Copy the app folder again in full.")

        folder.mkdir(parents=True, exist_ok=True)
        # Read as data and written as plain JSON - no comments, no trailing
        # commas - so any editor opens the file without a red line in it.  The
        # name and the format are set as values, not swapped into the text.
        data = load_jsonc(PROJECT_TEMPLATE)
        data.setdefault("project", {})["name"] = name
        data.setdefault("output", {})["format"] = output_format
        # The template holds a place for every tag's description; a new project
        # gets only the ones written there - an empty one means nothing, and a
        # file keeps no key that means nothing.  (Asked for.)
        described = data.get("tag_descriptions")
        if isinstance(described, dict):
            described = {tag: text for tag, text in described.items() if str(text).strip()}
            if described:
                data["tag_descriptions"] = described
            else:
                del data["tag_descriptions"]
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")

        # The folder a project keeps its lists in, so the editor has somewhere
        # to put the first one and the Open dialog has somewhere to look.
        config = Config.load(target)
        config.inputs.model_directory.mkdir(parents=True, exist_ok=True)
        return target

    # -- the recent list ---------------------------------------------------
    # Entries are stored relative to the app (see store_recent_entry() in
    # app_home.py), so two entries that name the same project do not
    # necessarily compare equal as strings - one may be relative and an older
    # one absolute.  Comparisons below always go through resolve_recent_entry()
    # for that reason.
    def remember(self, path: Path) -> None:
        resolved = Path(path).resolve()
        entry = store_recent_entry(resolved)
        self._recent = [entry] + [item for item in self._recent
                                  if resolve_recent_entry(item) != resolved]
        del self._recent[RECENT_LIMIT:]
        self._write_settings(current=entry)

    def forget(self, path: Path) -> None:
        resolved = Path(path).resolve()
        self._recent = [item for item in self._recent
                        if resolve_recent_entry(item) != resolved]
        self._write_settings()

    def recent(self) -> List[Dict[str, object]]:
        """The recent projects that are still there, newest first.

        A project whose folder has been deleted is dropped rather than listed
        as "missing": it was listed here only as a shortcut, and a shortcut to
        something that no longer exists is not information, it is a row that
        can never be clicked.  The entry is forgotten too, so the list does not
        fill up with the dead over time.
        """
        alive = [item for item in self._recent if resolve_recent_entry(item).is_file()]
        if alive != self._recent:
            self._recent = alive
            self._write_settings()

        rows: List[Dict[str, object]] = []
        for item in alive:
            path = resolve_recent_entry(item)
            rows.append({
                "path": str(path),
                "folder": str(path.parent),
                "name": project_name(path),
                "exists": True,
                "current": (self.document is not None
                            and self.document.config.path == path),
            })
        return rows

    def last(self) -> Optional[Path]:
        """The project that was open last, if it is still there.

        This is what ``run.py generate`` uses when nobody says which project
        to build: the one the editor was last used on is the one somebody
        means.
        """
        for item in self._recent:
            path = resolve_recent_entry(item)
            if path.is_file():
                return path
        return None

    # -- the settings file -------------------------------------------------
    # Both use the workspace's OWN settings file.  They used to use the app's
    # file whatever the workspace had been given, so every test that built a
    # workspace on a settings file of its own - to keep out of the user's -
    # still wrote its temp project into paramgen/var/settings.json, and a
    # recent list with a project missing from disk was rewritten empty.
    def _read_settings(self) -> None:
        recent = read_settings(self.settings_file).get("recent")
        if isinstance(recent, list):
            self._recent = [str(item) for item in recent if isinstance(item, str)]
            del self._recent[RECENT_LIMIT:]

    def _write_settings(self, current: Optional[str] = None) -> None:
        write_settings({
            "recent": self._recent,
            "current": (current if current is not None
                        else (store_recent_entry(self.document.config.path)
                              if self.document else "")),
        }, self.settings_file)



