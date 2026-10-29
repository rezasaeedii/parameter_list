"""The JSON API the browser talks to.

One method per action, all of them tiny.  Adding a button to the GUI means
adding one method here and one ``fetch`` call in ``web/app.js``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pl_codegen import __tool_name__, __version__
from pl_codegen.app_home import APP_DIR, LAUNCHER, is_project_file, project_file_in
from pl_codegen.codegen.files import fixed_tags
from pl_codegen.codegen.files.param_table_h import system_of
from pl_codegen.choices import COLUMNS, NUMBERED, default_choices, default_defines
from pl_codegen.config import FORMAT_PARAM_TABLE, FORMAT_SMART_DATA, relative_to_root
from pl_codegen.errors import CodeGeneratorError, DiagnosticCollector
from pl_codegen.model.defines import (COLUMN_TYPES, COLUMN_PARAM_MODES, COLUMN_SYSTEM_NAMES,
                                      COLUMN_VALUE_TYPES)
from pl_codegen.model.parameter import Parameter, element_key
from pl_codegen.model.parameter_list import PATH_SEPARATOR, ParameterList
from pl_codegen.naming import strip_array_indices
from pl_codegen.model.tags import LOG_ID_FIELD, LOG_ID_LABEL, TAG_REGISTRY
from pl_codegen.validation.rules.tag_rules import LOG_ID_MAX
from pl_codegen.model.types import VALUE_TYPES

from pl_codegen.xml_model.xml_reader import read_xml

from . import native_dialog, project_settings
from .document import Document, listing_target, machine_roots
from .workspace import Workspace

#: Every file or folder the editor asks somebody to choose:
#: ``what -> (kind of dialog, its title, the file types it offers)``.  Where
#: each one starts is :func:`start_folder`'s to say.
CHOICES = {
    # Any JSON file: a project file may have been renamed by its owner, and
    # one that is not a project is refused, with why, when it is opened.
    "project": (native_dialog.KIND_FILE, "Open project",
                (("Project file (JSON)", ("*.json",)),)),
    "project-location": (native_dialog.KIND_FOLDER,
                         "Where the new project's folder is made", ()),
    "sub-list": (native_dialog.KIND_FILE, "Add an existing parameter sublist",
                 (("Parameter sublist", ("*.xml",)),)),
    "sub-list-location": (native_dialog.KIND_FOLDER,
                          "Folder for the new parameter sublist", ()),
}


class Api:
    """Every endpoint the front end can call.

    The editor edits *projects* the way a text editor edits files: it is
    installed once and opens whichever project is asked for.  So what it holds
    is a :class:`~pl_gui.workspace.Workspace` - the project that is open, or
    none at all - and ``self.document`` is whatever that currently is.
    """

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    @property
    def document(self) -> Document:
        """The open project's document; refuses in words when none is open."""
        return self.workspace.require()

    # -- dispatch ----------------------------------------------------------
    def handlers(self) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
        return {
            "state": self.state,
            "open_project": self.open_project,
            "new_project": self.new_project,
            "close_project": self.close_project,
            "browse_projects": self.browse_projects,
            "choose": self.choose,
            "open": self.open_file,
            "save": self.save,
            "add": self.add,
            "add_structure": self.add_structure,
            "duplicate": self.duplicate,
            "delete": self.delete,
            "move": self.move,
            "update": self.update,
            "undo": self.undo,
            "redo": self.redo,
            "defines": self.set_defines,
            "default_defines": self.default_defines,
            "project_settings": self.project_settings,
            "set_project_settings": self.set_project_settings,
            "generate": self.generate,
            "next_log_id": self.next_log_id,
            "lists": self.lists,
            "new_list": self.new_list,
            "select_lists": self.select_lists,
            "browse": self.browse,
            "inspect_list": self.inspect_list,
            "add_existing_list": self.add_existing_list,
            "remove_list": self.remove_list,
            "new_type": self.new_type,
            "update_type": self.update_type,
            "delete_type": self.delete_type,
            "use_type": self.use_type,
        }

    # -- reading -------------------------------------------------------------
    def state(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Everything the front end needs to render one full screen.

        ``allLists`` asks for the whole build instead of the open list: every
        list, in build order, as one tree.  It is the view that answers "what
        does the generated table actually contain?", which no single list can.
        """
        if not self.workspace.is_open:
            # The start screen. It is a state of the editor like any other, so
            # it comes back through the same call rather than as an error the
            # front end has to know how to read.
            return {
                "tool": {"name": __tool_name__, "version": __version__,
                         "launcher": LAUNCHER},
                "project": None,
                "recent": self.workspace.recent(),
                **self._dialogs(),
                "tree": [], "diagnostics": [], "modules": [], "structTypes": [],
                "file": "", "fileShown": "",
                "dirty": False, "canUndo": False, "canRedo": False,
            }

        document = self.document
        if request.get("allLists"):
            return self._all_lists_state()
        # Built once for the whole tree.  They were built again for every top
        # level row - each one a copy and a flatten of the whole build - so a
        # list of 400 parameters took 18 seconds to draw after every click.
        log_ids = _log_ids_by_declaration(document)
        # One list on its own: in a parameter table its rows are numbered
        # within that sublist - the number ADD_PARAM writes - and in smart
        # data across the whole build.  The merged view (_all_lists_state)
        # always counts the whole build.
        indices = _indices_by_row(
            document, per_list=document.config.output.format == FORMAT_PARAM_TABLE)
        return {
            # 'launcher' is how this machine starts the tool - run.bat or
            # ./run.sh - for the one sentence of the page that tells somebody
            # to run it from a terminal.
            "tool": {"name": __tool_name__, "version": __version__,
                     "launcher": LAUNCHER},
            "project": self._project_info(),
            "recent": self.workspace.recent(),
            **self._dialogs(),
            # In the parameter-table format the open list's file name IS its
            # sub-system, so the form shows that rather than the tag.
            "systemFromFile": (system_of(document.path)
                               if document.path is not None else ""),
            "file": str(document.path) if document.path else "",
            # The same list named from the project root, for the top bar -
            # 'file' stays whole for its tooltip.
            "fileShown": (relative_to_root(document.path, document.config.path.parent)
                          if document.path else ""),
            # Whether the list differs from its file: the '*' the editor shows.
            "dirty": document.dirty,
            "canUndo": document.can_undo,
            "canRedo": document.can_redo,
            "tree": [_node(child, child.name, {}, None,
                           log_ids=log_ids, indices=_row(indices, position),
                           fixed=fixed_tags(document.config))
                     for position, child in enumerate(document.model.parameters)],
            "diagnostics": document.validate(),
            "defines": {
                "paramTypes": document.model.defines.get(COLUMN_TYPES),
                "valueTypes": document.model.defines.get(COLUMN_VALUE_TYPES) or list(VALUE_TYPES),
                "systemNames": document.model.defines.get(COLUMN_SYSTEM_NAMES),
                "paramModes": document.model.defines.get(COLUMN_PARAM_MODES),
            },
            # The number each system name and parameter mode is #defined as,
            # for the Drop-down lists dialog: [[name, number], ...] in order.
            "defineNumbers": _numbers_of(document.model.defines),
            # the open list's own structure types, for the Structure types panel
            # and for the "Data type" list of a structure parameter
            "structTypes": document.struct_types(),
            # A free tag the project describes reads "Tag1 : Saveable" wherever
            # the editor names it, and its tooltip is that meaning.  (Asked for.)
            "tagSpecs": [
                {
                    "id": spec.tag_id,
                    "label": (f"{spec.label} : {meaning}" if meaning else spec.label),
                    "kind": spec.kind.value,
                    "mandatory": spec.mandatory,
                    "definesColumn": spec.defines_column,
                    "description": meaning or spec.description,
                    # what the project says it means, alone - the grid heads
                    # the tag's column with it
                    "meaning": meaning,
                }
                for spec in TAG_REGISTRY
                for meaning in [document.config.tag_descriptions.get(spec.tag_id, "")]
            ],
            # The tags this project's format writes the same into every
            # parameter - {"ParamMode": "PARAM_MODE_NONE"} in a smart-data
            # project - which the form shows read-only.
            "fixedTags": fixed_tags(document.config),
            # The log id is described separately because it is not a tag: it has
            # no offset area and it is a plain uint16_t in the descriptor, so
            # the editor gives it its own field instead of a row among the tags.
            "logIdSpec": {"field": LOG_ID_FIELD, "label": LOG_ID_LABEL,
                          "max": LOG_ID_MAX,
                          "description": "Identifier the logging sub-system uses for "
                                         "this value. Only meaningful while Tag Loggable "
                                         "is TRUE."},
            "outputDirectory": str(document.config.output.code_directory),
            # every parameter sublist of the project; the editor works on one at a time
            "modules": [{"path": str(path), "name": path.stem,
                         "current": document.path is not None and path == document.path,
                         "exists": path.is_file()}
                        for path in document.config.inputs.model_files],
        }

    def _all_lists_state(self) -> Dict[str, Any]:
        """The whole build as one read-only tree, in build order.

        Read-only on purpose: a node here can come from any of the files, and an
        edit would have to decide which one to write back to.  Rather than guess,
        the view says which list each entry belongs to and sends you there.
        """
        document = self.document
        state = self.state({})

        merged = document.merged_model()
        # Which file each top-level row of the merged model came from - by
        # POSITION, walking the lists exactly the way merged_model() does: the
        # open list from memory, the others from disk, and the open list last
        # when it is not part of the build.  It used to be looked up by NAME, so
        # a name used in two lists named the first list for both, and an open
        # list not yet on disk was skipped although merged_model() includes it.
        open_path = document.path.resolve() if document.path else None
        owners: List[str] = []
        seen = False
        for path in document.config.inputs.model_files:
            if open_path is not None and path.resolve() == open_path:
                count, seen = len(document.model.parameters), True
            elif path.is_file():
                try:
                    count = len(read_xml(path, DiagnosticCollector()).parameters)
                except Exception:
                    continue
            else:
                continue
            owners.extend([path.name] * count)
        if not seen and document.path is not None:
            owners.extend([document.path.name] * len(document.model.parameters))

        indices = _indices_by_row(document, merged_view=True)
        log_ids: Dict[str, List[int]] = {}
        for leaf in merged.flatten():
            if leaf.log_id is not None:
                log_ids.setdefault(strip_array_indices(leaf.name), []).append(leaf.log_id)

        tree = []
        for position, child in enumerate(merged.parameters):
            node = _node(child, child.name, {}, None,
                         log_ids=log_ids, indices=_row(indices, position))
            # Every node knows which file it came from, fields included: it is
            # what lets a row clicked here open the list that owns it and
            # select it there.  The merged view could never write a change
            # back itself - a node in it may come from any of six files - but
            # "you cannot edit this" was the wrong answer to a click.
            _mark_owner(node, owners[position] if position < len(owners) else "")
            tree.append(node)

        state["tree"] = tree
        state["allLists"] = True
        state["readOnly"] = True
        state["file"] = f"{len(document.config.inputs.model_files)} sublist(s), merged"
        state["fileShown"] = state["file"]
        return state

    # -- the project -----------------------------------------------------------
    #
    # A project is a folder with a project file in it.  The editor opens one at
    # a time, exactly the way a text editor opens a file, and everything below
    # this line is about *which* project rather than about what is in it.

    def _project_info(self) -> Dict[str, Any]:
        config = self.workspace.require().config
        return {
            "name": config.project.name,
            "description": config.project.description,
            # What this project generates.  The editor puts guard rails up for
            # 'param_table', which has no structures and no arrays - better to
            # stop somebody building one than to refuse it at the end.
            "format": config.output.format,
            "file": str(config.path),
            "folder": str(config.path.parent),
            "listDirectory": str(config.inputs.model_directory),
            "outputDirectory": str(config.output.code_directory),
        }

    def open_project(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.workspace.open(Path(str(request.get("path") or "")))
        except (CodeGeneratorError, OSError, ValueError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "project": self._project_info()}

    def new_project(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Make a project, then open it - nobody makes one to leave it shut."""
        try:
            path = self.workspace.create(
                Path(str(request.get("folder") or "")),
                str(request.get("name") or ""),
                str(request.get("format") or FORMAT_SMART_DATA))
            self.workspace.open(path)
        except (CodeGeneratorError, FileExistsError, OSError, ValueError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "path": str(path), "project": self._project_info()}

    def close_project(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        self.workspace.close()
        return {"ok": True}

    def browse_projects(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Folders and project files of one folder, for the project dialogs.

        Separate from ``browse`` because it is looking for something else: a
        project is its ``.json`` file.  A folder that holds one is marked, but a
        folder is only ever walked into - a project made inside another
        project's folder has to be reachable - and the project is opened by its
        file, which is marked too.
        """
        raw = str(request.get("directory") or "")
        # Where it starts: Open at the project, New beside the app.
        purpose = "project-location" if request.get("for") == "new" else "project"
        here, selected, missing = listing_target(raw, start_folder(self.workspace, purpose))
        try:
            here = here.resolve()
        except OSError as error:
            return {"ok": False, "message": f"Cannot open that folder: {error}"}
        if not here.is_dir():
            return {"ok": False, "message": f"'{raw or here}' is not a folder."}

        try:
            entries = sorted(here.iterdir(), key=lambda item: item.name.lower())
        except OSError as error:
            return {"ok": False, "message": f"Cannot list '{here}': {error}"}

        folders, files = [], []
        for entry in entries:
            try:
                if entry.is_dir():
                    if entry.name.startswith("."):
                        continue
                    inside = project_file_in(entry)
                    folders.append({"name": entry.name, "path": str(entry),
                                    "isProject": inside.is_file(),
                                    "projectFile": str(inside) if inside.is_file() else ""})
                elif entry.suffix.lower() == ".json":
                    # by what it holds: the owner may have renamed it
                    files.append({"name": entry.name, "path": str(entry),
                                  "isProject": is_project_file(entry)})
            except OSError:
                continue

        parent = here.parent
        return {"ok": True, "directory": str(here),
                "parent": str(parent) if parent != here else "",
                # ...and where else browsing could start: without this the
                # walk ends at the root of one drive and a project on another
                # can neither be opened nor created.
                "drives": machine_roots(),
                "folders": folders, "files": files,
                "selected": selected, "missing": missing}

    def choose(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Let somebody choose a file or a folder in the system's own dialog.

        ``what`` is one of :data:`CHOICES`; ``start`` is where to open instead
        of the usual place - the folder already typed into a Location box.
        When no such dialog can be shown here the answer says so
        (``unavailable``) and the page uses its own dialog instead.
        """
        what = str(request.get("what") or "")
        if what not in CHOICES:
            return {"ok": False, "message": f"Unknown choice '{what}'."}
        kind, title, filetypes = CHOICES[what]
        start, _selected, _missing = listing_target(str(request.get("start") or ""),
                                                    start_folder(self.workspace, what))
        try:
            path = native_dialog.ask(kind, title, start, filetypes)
        except native_dialog.DialogBusy as error:
            return {"ok": False, "busy": True, "message": str(error)}
        except native_dialog.NativeDialogUnavailable as error:
            return {"ok": False, "unavailable": True, "message": str(error)}
        return {"ok": True, "path": path, "cancelled": not path}

    def _dialogs(self) -> Dict[str, Any]:
        """What the page needs to know before it opens any of its dialogs."""
        return {
            # whether the system's own Open / Browse dialog can be used here
            "nativeDialogs": native_dialog.available(),
            # where each dialog starts - the same places for both kinds
            "startFolders": {what: str(start_folder(self.workspace, what))
                             for what in CHOICES},
        }

    # -- file ------------------------------------------------------------------
    def open_file(self, request: Dict[str, Any]) -> Dict[str, Any]:
        path = request.get("path") or None
        diagnostics = self.document.load(Path(path) if path else None)
        return {"ok": True, "diagnostics": diagnostics}

    def save(self, request: Dict[str, Any]) -> Dict[str, Any]:
        path = request.get("path") or None
        try:
            target = self.document.save(Path(path) if path else None)
        except ValueError as error:
            # A project with no parameter list has nothing to save into.  That
            # is a sentence for a person, not a server error with a class name.
            return {"ok": False, "message": str(error)}
        return {"ok": True, "path": str(target)}

    # -- tree editing ------------------------------------------------------------
    def add(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.document.add_parameter(str(request.get("parent") or ""),
                                               str(request.get("kind") or "primitive"))
        except ValueError as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "selected": path}

    def add_structure(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """A structure - and its new type, when fields come with it - in one step."""
        fields = request.get("fields")
        try:
            path = self.document.add_structure(
                str(request.get("name") or ""), str(request.get("type") or ""),
                fields if isinstance(fields, list) else None)
        except (ValueError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "selected": path}

    def duplicate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.document.duplicate(str(request.get("path") or ""))
        except ValueError as error:
            return {"ok": False, "message": str(error)}
        return {"ok": path is not None, "selected": path}

    def delete(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a node.  Its structure type stays: see ``Document.delete``."""
        path = str(request.get("path") or "")
        try:
            deleted = self.document.delete(path)
        except ValueError as error:
            return {"ok": False, "message": str(error)}
        return {"ok": deleted,
                "message": "" if deleted else f"There is nothing called '{path}' to delete."}

    def move(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.document.move(str(request.get("path") or ""),
                                      int(request.get("offset") or 0))
        except ValueError as error:
            return {"ok": False, "message": str(error)}
        return {"ok": path is not None, "selected": path}

    def update(self, request: Dict[str, Any]) -> Dict[str, Any]:
        changes = dict(request.get("changes") or {})
        try:
            path = self.document.update(str(request.get("path") or ""), changes)
        except ValueError as error:
            # A refused edit has to SAY why.  Coming back as ok:false with no
            # message would look exactly like the silent no-op this replaced.
            return {"ok": False, "message": str(error)}
        return {"ok": path is not None, "selected": path}

    def undo(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": self.document.undo() is not None}

    def redo(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": self.document.redo() is not None}

    def set_defines(self, request: Dict[str, Any]) -> Dict[str, Any]:
        column = {"paramTypes": COLUMN_TYPES, "systemNames": COLUMN_SYSTEM_NAMES,
                  "paramModes": COLUMN_PARAM_MODES, "valueTypes": COLUMN_VALUE_TYPES}
        key = str(request.get("list") or "")
        if key not in column:
            return {"ok": False, "message": f"Unknown list '{key}'."}
        try:
            self.document.set_defines(column[key], list(request.get("values") or []))
        except ValueError as error:        # 'SYS_NAV = abc' - said, not saved
            return {"ok": False, "message": str(error)}
        return {"ok": True}

    def default_defines(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        """The lists the app ships with, for the 'restore the defaults' button.

        The keys are the ones the dialog asks for.  They were not: the value
        types came back under 'types' while the dialog looked for 'valueTypes',
        so restoring the defaults filled that box with nothing and pressing OK
        wiped the machine's list of data types.
        """
        return {"ok": True, **default_choices(),
                "defineNumbers": _numbers_of(default_defines())}

    # -- the project settings dialog -----------------------------------------
    def project_settings(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        """The project file's settings, read from the file now.  (Asked for.)"""
        document = self.document
        try:
            settings = project_settings.read_settings(document.config.path)
        except (CodeGeneratorError, OSError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, **settings, "dirty": document.dirty}

    def set_project_settings(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Write the settings the dialog changed into the project file, then reload.

        Refused - with nothing written - while the open sublist has unsaved
        changes (reloading would throw them away), when the file changed on disk
        after the dialog read it, or when a value cannot be used.  A refusal
        sends the file's current settings back, so the dialog shows the truth.
        """
        document = self.document
        path = document.config.path
        changes = request.get("changes") or {}
        if not isinstance(changes, dict):
            return {"ok": False, "message": "The changes have to be a set of settings."}
        if document.dirty:
            return {"ok": False, "dirty": True,
                    "message": "The open sublist has unsaved changes. Save it, or reload "
                               "it to drop them - applying re-reads the whole project, "
                               "and that would lose them."}
        try:
            if changes:
                text, _old = project_settings.new_text(
                    path, str(request.get("fingerprint") or ""), changes)
                config = project_settings.load_candidate(path, text)
                try:
                    document.check_new_build(config.inputs.model_files)
                except ValueError as error:
                    raise project_settings.SettingsError(str(error), "inputs.model_files")
                project_settings.write(path, text)
            document.reload_project()
        except project_settings.SettingsError as error:
            answer: Dict[str, Any] = {"ok": False, "message": str(error), "field": error.field}
            try:
                answer["settings"] = project_settings.read_settings(path)
            except (CodeGeneratorError, OSError):
                pass
            return answer
        except (CodeGeneratorError, OSError, ValueError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "changed": sorted(changes)}

    # -- actions --------------------------------------------------------------
    def generate(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the code, and turn a tool error into an answer, not a crash.

        The commonest one is a parameter list named in the configuration that is
        not on disk - a state the editor itself shows as "(new)".  Letting that
        become a 500 would leave the page sitting on "Generating..." with nothing
        to read, so it comes back as a failed result with the reason in it.
        """
        try:
            return self.document.generate()
        except (CodeGeneratorError, OSError) as error:
            return {"success": False, "files": [], "count": 0, "saved": "",
                    "modules": [str(path) for path in self.document.config.inputs.model_files],
                    "diagnostics": [], "message": str(error)}

    def next_log_id(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "value": self.document.next_free_log_id()}

    # -- the parameter lists of the project ------------------------------------
    def lists(self, _request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "directory": str(self.document.list_directory()),
            "config": str(self.document.config.path),
            "lists": self.document.known_lists(),
        }

    def new_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = self.document.create_list(str(request.get("name") or ""),
                                             str(request.get("directory") or ""))
        except (ValueError, FileExistsError, OSError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "path": str(path)}

    def browse(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """The folders and .xml files of one folder, for the Open dialog."""
        try:
            return self.document.browse(str(request.get("directory") or ""))
        except OSError as error:
            return {"ok": False, "message": str(error)}

    def inspect_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Whether a file is a parameter list, without adding it to anything."""
        try:
            return self.document.inspect_list(str(request.get("path") or ""))
        except (OSError, CodeGeneratorError) as error:
            return {"ok": False, "reason": str(error)}

    def add_existing_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Take a parameter list that already exists into the build."""
        before = {str(item) for item in self.document.config.inputs.model_files}
        try:
            path = self.document.add_existing_list(str(request.get("path") or ""))
        except (ValueError, OSError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        # a list that was already in the build is opened, not added
        return {"ok": True, "path": str(path), "alreadyInBuild": str(path) in before}

    def remove_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Take a list out of the build; ``delete`` also removes the file."""
        try:
            result = self.document.remove_list(str(request.get("path") or ""),
                                               bool(request.get("delete")))
        except (ValueError, OSError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, **result}

    def select_lists(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            chosen = self.document.select_lists(
                [str(item) for item in (request.get("paths") or [])])
        except (ValueError, OSError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "paths": [str(path) for path in chosen]}

    # -- structure types ------------------------------------------------------
    def new_type(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            fields = request.get("fields")
            name = self.document.create_struct_type(
                str(request.get("name") or ""), fields if isinstance(fields, list) else None)
        except (ValueError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "name": name}

    def update_type(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            name = self.document.update_struct_type(
                str(request.get("name") or ""), request.get("changes") or {})
        except (ValueError, CodeGeneratorError) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "name": name}

    def delete_type(self, request: Dict[str, Any]) -> Dict[str, Any]:
        removed, message = self.document.delete_struct_type(str(request.get("name") or ""))
        return {"ok": removed, "message": message}

    def use_type(self, request: Dict[str, Any]) -> Dict[str, Any]:
        path = self.document.use_struct_type(str(request.get("path") or ""),
                                             str(request.get("name") or ""))
        return {"ok": path is not None, "selected": path,
                "message": "" if path else "No such structure type."}


def _mark_owner(node: Dict[str, Any], owner: str) -> None:
    """Put the owning file on this node and on everything under it."""
    node["ownerList"] = owner
    for child in node.get("children") or []:
        _mark_owner(child, owner)


def _log_ids_by_declaration(document) -> Dict[str, List[int]]:
    """``dotted declaration path -> the log ids its values actually got``.

    ``flatten()`` is what hands the ids out, one per value, so this asks it
    rather than trying to work the arithmetic out again in the front end - the
    two could then disagree, and the one the firmware sees is this one.

    The element indices are stripped from the key, so ``Motor[0].Rpm`` and
    ``Motor[1].Rpm`` both answer for the declaration ``Motor.Rpm`` and the
    editor can say "this field holds these ids".
    """
    found: Dict[str, List[int]] = {}
    # the OPEN list, because that is the tree the editor is showing
    for leaf in document.model.flatten():
        if leaf.log_id is None:
            continue
        found.setdefault(strip_array_indices(leaf.name), []).append(leaf.log_id)
    return found


#: The values of one top level row: ``dotted declaration path -> its values``.
RowValues = Dict[str, List[Dict[str, Any]]]


def _indices_by_row(document, per_list: bool = False,
                    merged_view: bool = False) -> List[RowValues]:
    """One ``dotted declaration path -> one entry per value it produces`` per
    top level row of the tree being drawn, in the tree's order.

    Each entry is ``{index, name, logId}``: the row it occupies in the generated
    table, the element it is (``Motor[2].Winding[1]``), and its log id.  The
    editor needs the individual values, not just their span - the values of one
    field of a struct array are NOT a contiguous run, so "13…25" would be a
    range that mostly belongs to other parameters.

    Counted over the whole build, in build order, because that is what the
    generator builds and therefore what the index macros count: a parameter's
    index depends on every list before it in the build, not only on its own
    list.

    *per_list* counts the open list on its own instead, from zero.  That is the
    parameter table's index: nsrParamTables.h restarts it in every sublist's
    block, so it is the number ADD_PARAM writes.  *merged_view* answers for the
    rows of every sublist, merged; otherwise for the open list's rows.

    One dict PER ROW, not one for the tree: a name is unique in one sublist
    only.  Two lists may each hold a 'NewParameter', and when the values were
    looked up by name the second one was shown the first one's index - in the
    merged view, and in its own list in smart data.  Counted row by row, every
    number stays with the row that earned it.

    A disabled parameter never appears, so it correctly gets no index.
    """
    if per_list:
        return _count_rows(document.model.parameters, 0)[0]
    try:
        parts = document.merged_parts()
    except Exception:
        # A list elsewhere in the build that will not parse must not stop the
        # editor from drawing the one that is open.
        return []
    if not parts:
        # merged_model() is then the open list on its own
        return _count_rows(document.model.parameters, 0)[0]

    open_path = document.path.resolve() if document.path else None
    every: List[RowValues] = []
    mine: List[RowValues] = []
    first = 0
    for path, part in parts:
        rows, first = _count_rows(part.parameters, first)
        every.extend(rows)
        # merged_parts() holds the open list once, built from memory
        if not mine and open_path is not None and Path(path).resolve() == open_path:
            mine = rows
    return every if merged_view else mine


def _count_rows(parameters: List[Parameter], first: int) -> Tuple[List[RowValues], int]:
    """The values of each of *parameters*, numbered on from *first*.

    Each top level entry is flattened on its own: flatten() walks them one
    after the other and nothing of one reaches into the next, so the numbers
    are the ones the whole list's flatten() gives - and each is known to be
    this entry's.  Returns the rows and the number after the last.
    """
    rows: List[RowValues] = []
    index = first
    for parameter in parameters:
        found: RowValues = {}
        for leaf in ParameterList(parameters=[parameter]).flatten():
            found.setdefault(strip_array_indices(leaf.name), []).append(
                {"index": index, "name": leaf.name, "logId": leaf.log_id,
                 # what THIS value means: its own description, or the declaration's
                 "description": leaf.description,
                 # and what it is called: its own User Name, the declaration's, or
                 # the structure's it is in - what pUserName holds for it
                 "userName": leaf.user_name or ""})
            index += 1
        rows.append(found)
    return rows, index


def _row(rows: List[RowValues], position: int) -> RowValues:
    """The values of the row at *position* - none when they could not be counted."""
    return rows[position] if position < len(rows) else {}


def _numbers_of(defines: Any) -> Dict[str, List[List[Any]]]:
    """``{"systemNames": [["SYS_UNKNOWN", 0], ...], "paramModes": [...]}``.

    Every name with the number it is #defined as - the ones nobody numbered
    included, worked out the way the generator works them out - so the dialog
    shows each line as ``SYS_NAV = 16``.
    """
    return {key: [[name, number] for name, number in defines.numbered(COLUMNS[key])]
            for key in NUMBERED}


def _node(parameter: Parameter, path: str,
          inherited: Dict[str, Any], inherited_type: Any,
          owner: str = "", inherited_log_id: Any = None,
          log_ids: Optional[Dict[str, List[int]]] = None,
          indices: Optional[Dict[str, List[Dict[str, Any]]]] = None,
          parent_enabled: bool = True,
          owner_type: str = "",
          above: Optional[Dict[Tuple[int, ...], Tuple[str, str]]] = None,
          fixed: Optional[Dict[str, Any]] = None
          ) -> Dict[str, Any]:
    """One node of the tree, as the front end wants it.

    Tags, the type and the log id belong to the top level entry.  For a field,
    ``owner`` is the name of that entry and ``effectiveTags`` /
    ``effectiveGroup`` / ``effectiveLogId`` are its values - the editor shows
    them read-only instead of an editable form.

    *above* is, for every element this node is found in - ``(1,)`` for the
    Samples of Wheels[1], ``()`` at the top - the User Name and the
    description the rows above it give it there.

    *fixed* is the tags the project's format writes into every parameter,
    whatever the list says: the grid and the form show those, because they are
    what the generated code gets.  The list keeps its own.
    """
    is_field = bool(owner)
    effective = dict(inherited) if is_field else {
        key: value for key, value in parameter.tags.items() if value is not None}
    shown_tags = {spec.tag_id: parameter.tags.get(spec.tag_id) for spec in TAG_REGISTRY}
    if not is_field and fixed:
        effective.update(fixed)
        shown_tags.update(fixed)
    effective_type = inherited_type if is_field else parameter.param_type
    rows, inside = _row_texts(parameter, above if above is not None else {(): ("", "")})
    # the declaration's row, for the form of a declaration: what it reads from
    # the structure it is in when it says nothing itself
    inherited_user_name = next(iter(above.values()))[0] if above else ""

    return {
        "path": path,
        "isField": is_field,
        "owner": owner,
        "name": parameter.name,
        "kind": parameter.kind.value,
        # Sent as its own flag as well as in 'kind': the form asks "is this a
        # structure?" in half a dozen places, and reading it off a string in
        # each of them is how the data-type list came to offer float32_t to a
        # structure - the check was there, it was just never true.
        "isStruct": parameter.is_struct,
        # Which structure type this field's shape comes from - what the form
        # points at when it says "you cannot change that here".
        "ownerType": owner_type,
        "enable": parameter.enable,
        "userName": parameter.user_name,
        # the parameter table's address column; the form shows it only there
        "address": parameter.address,
        "paramType": parameter.param_type,
        "valueType": parameter.value_type_name,
        "arraySize": parameter.array_size,
        "defaultValue": parameter.default_value,
        "minimum": parameter.minimum,
        "maximum": parameter.maximum,
        "resolution": parameter.resolution,
        "unit": parameter.unit,
        "logId": parameter.log_id,
        "effectiveLogId": inherited_log_id if is_field else parameter.log_id,
        # The ids this node's values really got, straight from flatten().  A
        # scalar has one; an array, or a field of an array of structures, has
        # one per value.
        "logIds": (log_ids or {}).get(path, []),
        # The rows this declaration occupies in the generated table.  Empty for
        # a structure (it is not a row), for a disabled parameter, and for a
        # list that is not part of the build.
        # One entry per value this declaration produces: {index, name, logId}.
        # The editor can show the span when it is a run, and expand into the
        # individual values when it is not.
        "values": (indices or {}).get(path, []),
        # Whether this value reaches the generated table at all.  A field of a
        # disabled structure keeps its own enable flag - it is still ticked, and
        # re-enabling the structure brings it back exactly as it was - but it is
        # NOT in the build, and a tree that showed it as enabled was telling the
        # reader the opposite of what the generator does.
        "effectiveEnable": bool(parameter.enable) and parent_enabled,
        "parentEnabled": parent_enabled,
        "description": parameter.description,
        # What ONE value means, where it is not what the declaration says.
        # Keyed by element path - "3" is Speed[3], "1.5" is
        # Wheels[1].Samples[5] - so the form can show an element its own
        # text without asking the backend again, and without depending on
        # the indices, which a list outside the build does not have.
        "elementDescriptions": dict(parameter.element_descriptions),
        # The same for the User Name, keyed the same way - and the name the
        # declaration's row reads: this node's, or, for a field with none, the
        # structure's it is in.
        "elementUserNames": dict(parameter.element_user_names),
        "sharedUserName": (parameter.user_name or "").strip() or inherited_user_name,
        "inheritedUserName": inherited_user_name,
        # What every row of this node in the grid shows, by element path -
        # "" is the declaration's own row, "1" is Wheels[1] (or the Samples of
        # Wheels[1]), "1.5" is Wheels[1].Samples[5] - and what it reads from
        # the rows above when it says nothing itself.  Worked out here, the
        # way flatten() does it, so the grid and the form never have to.
        "rowTexts": rows,
        "tags": shown_tags,
        "effectiveTags": {spec.tag_id: effective.get(spec.tag_id) for spec in TAG_REGISTRY},
        "effectiveType": effective_type,
        # A child's shape comes from THIS node's structure type - so that is
        # what it is told, and what the form names when it says the shape is
        # not editable here.
        "children": [_node(child, f"{path}{PATH_SEPARATOR}{child.name}",
                           effective, effective_type, owner or parameter.name,
                           inherited_log_id if is_field else parameter.log_id,
                           log_ids, indices,
                           bool(parameter.enable) and parent_enabled,
                           parameter.value_type_name or owner_type,
                           inside)
                     for child in parameter.children],
    }


def _row_texts(parameter: Parameter, above: Dict[Tuple[int, ...], Tuple[str, str]]
               ) -> Tuple[Dict[str, Dict[str, str]], Dict[Tuple[int, ...], Tuple[str, str]]]:
    """What every grid row of *parameter* shows, and what its fields read.

    A node has one row in every element it is found in - Wheels[1].Samples -
    and, when it is an array, one row per element of its own under that -
    Wheels[1].Samples[5].  Each shows its own text, or the nearest one above
    it: the shorter element paths of this node down to its declaration, then
    what *above* says for that element.  The same reading as ``_collect``.

    Returns the rows by element path, and - for a structure - what each of its
    elements hands to its fields.
    """
    count = max(1, parameter.array_size)
    rows: Dict[str, Dict[str, str]] = {}
    inside: Dict[Tuple[int, ...], Tuple[str, str]] = {}
    for where, (name_above, text_above) in above.items():
        own = [where] + ([where + (index,) for index in range(count)] if count > 1 else [])
        for row in own:
            # what the row would read if it said nothing itself
            shorter = row[:-1] if row else None
            rows[element_key(row)] = {
                "userName": (parameter.user_name_over(row) or name_above or "").strip(),
                "userNameAbove": ((parameter.user_name_over(shorter) if row else None)
                                  or name_above or "").strip(),
                "description": (parameter.description_over(row) or text_above or "").strip(),
                "descriptionAbove": ((parameter.description_over(shorter) if row else None)
                                     or text_above or "").strip(),
            }
        if parameter.is_struct:
            # the fields of each element read that element's row
            for row in (own[1:] if count > 1 else own):
                texts = rows[element_key(row)]
                inside[row] = (texts["userName"], texts["description"])
    return rows, inside


def start_folder(workspace: Workspace, what: str) -> Path:
    """Where the dialog for *what* (see :data:`CHOICES`) starts.

    It used to start one folder ABOVE the project, which for a project at
    ``F:\\test`` is the root of the drive - so every Open began by walking down
    from there.  (Reported.)  Now:

      * Open project: the folder the open project's file is in; else the last
        project's; else beside the app;
      * New project: beside the app - the folder paramgen/ is in.  Never inside
        it: the app folder is not written to while anybody works;
      * a parameter sublist, to add or to make: the project's sublist folder.
    """
    config = workspace.config
    if what == "project":
        if config is not None:
            return config.path.parent
        last = workspace.last()
        return last.parent if last is not None else APP_DIR.parent
    if what == "project-location" or config is None:
        return APP_DIR.parent
    folder = config.inputs.model_directory
    return folder if folder.is_dir() else config.path.parent

