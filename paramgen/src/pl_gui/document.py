"""The document the GUI edits: the parameter list plus its file and undo stack.

Everything the front end does goes through this class, so the rules about what
a valid edit is live in one place.
"""

from __future__ import annotations

import contextlib
import copy
import itertools
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from pl_codegen.choices import load_choices, parse_numbered, save_choices
from pl_codegen.codegen.files import apply_fixed_tags, fixed_tags
from pl_codegen.codegen.files.param_table_h import ADDRESS_MAX, READ_ONLY_TAGS, system_of
from pl_codegen.config import FORMAT_PARAM_TABLE, Config, relative_to_root
from pl_codegen.errors import CodeGeneratorError, DiagnosticCollector, Severity
from pl_codegen.layout.tag_offset import reserved_log_ids
from pl_codegen.model.defines import (COLUMN_SYSTEM_NAMES, COLUMN_TYPES, GENERATED_DEFINES,
                                      Defines)
from pl_codegen.model.parameter import Parameter, ParameterKind, element_key
from pl_codegen.model.parameter_list import PATH_SEPARATOR, ParameterList, merge_lists
from pl_codegen.model.struct_sync import apply_types
from pl_codegen.model.struct_type import StructField, StructType
from pl_codegen.model.types import resolve_value_type
from pl_codegen.naming import is_valid_c_identifier, strip_array_indices
from pl_codegen.xml_model.types_xml import (LEGACY_TYPES_SUFFIX, TYPES_SUFFIX,
                                            existing_types_file_for, is_types_file,
                                            legacy_types_file_for, read_types,
                                            types_file_for, types_to_element)
from pl_codegen.model.tags import TAG_REGISTRY, TagKind
from pl_codegen.pipeline import Pipeline
from pl_codegen.validation.rules.tag_rules import LOG_ID_MAX
from pl_codegen.validation.validator import Validator
from pl_codegen.xml_model.xml_reader import convert_tag, read_xml
from pl_codegen.xml_model.xml_writer import model_to_element, write_xml

from .config_file import rewrite_model_files

#: how many steps of undo the GUI keeps
UNDO_DEPTH = 60

#: What every action that needs a parameter list says when none is open.  A
#: parameter lives IN a list; a project without one has nowhere to keep it.
NO_LIST = ("This project has no parameter sub list yet, and a parameter lives in "
           "a sub list - there is nowhere to put one. Create a sub list first: "
           "'Parameter sub lists' (\u2630) in the toolbar, then '+ Add parameter sub "
           "list' (or 'Add an existing parameter sub list').")

#: Every field of :class:`~pl_codegen.model.parameter.Parameter` the
#: editor form is allowed to write, i.e. every ``data-field`` in ``editor.js``.
#: ``tags``, ``name`` and the tree structure are handled separately; ``kind``
#: and ``children`` are deliberately absent, because a wrong value in either
#: crashes validation - and validation runs inside ``/api/state``, so it would
#: take the whole editor down rather than show a diagnostic.
EDITABLE_FIELDS = frozenset({
    "user_name", "param_type", "value_type_name", "array_size", "unit", "enable",
    "default_value", "minimum", "maximum", "resolution", "log_id", "description",
    "address",
})

# The drop-down lists a brand new model starts with - the company's lists.
# Edit them here, or per model with the "Choices..." button in the editor.
DEFAULT_PARAMETER_TYPES = [
    "MONITORING",
    "COMMAND",
    "SETTING",
]

DEFAULT_SYSTEM_NAMES = [
    "SYS_UNKNOWN",
    "SYS_GS_COMPUTER",
    "SYS_GS_MANAGER",
    "SYS_GS_POWER",
    "SYS_ANTENNA_TRACKER",
    "SYS_AC_MANAGER",
    "SYS_AC_POWER",
    "SYS_AC_AUTOPILOT",
    "SYS_GIMBAL",
    "SYS_LOCK_TRACK",
    "SYS_LINK_GS",
    "SYS_GS_USB2CAN",
    "SYS_LINK_AIR",
    "SYS_BOOTLOADER",
    "SYS_LINK_BOX",
    "SYS_GOVERNOR",
    "SYS_NAV",
    "SYS_AND",
    "SYS_VNS",
    "SYS_RHS",
    "SYS_AUP",
]

DEFAULT_PARAM_MODES = [
    "PARAM_MODE_USER",
    "PARAM_MODE_READ_ONLY",
    "PARAM_MODE_PRODUCT_TYPE",
    "PARAM_MODE_FACTORY",
    "PARAM_MODE_CALIB",
    "PARAM_MODE_TEMPORARY",
]


class Document:
    """The in-memory parameter list plus everything the GUI needs around it."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.model = ParameterList()
        self.path: Optional[Path] = config.inputs.model_file
        #: the list the way its file holds it, as last read or written - what
        #: :attr:`dirty` compares with
        self._saved_text = self._file_text()
        #: what the READER said about the open file, kept until it is written
        #: again.  These do not come back from re-validating the model: the
        #: reader has already dropped the value it could not use, so the model
        #: in memory looks clean while the file on disk is still wrong - and
        #: the generator reads the file.
        self.load_problems: List[Dict[str, object]] = []
        self._undo: List[Tuple[str, ParameterList]] = []
        self._redo: List[Tuple[str, ParameterList]] = []

    # -- loading and saving ------------------------------------------------
    def reread_project(self) -> Optional[str]:
        """Pick up a project file that was changed outside the editor.

        The editor used to hold the ``Config`` it loaded when the project was
        opened, so an edit made in a text editor - a different output folder,
        a stricter validation setting - was simply invisible.  Reload said
        nothing had changed and Generate wrote to the old place, which is a
        very hard thing to explain to somebody looking at the file they just
        saved.

        Returns the reason when the file cannot be read, and keeps the working
        configuration in that case: a project file with a typo in it must not
        take the editor down, and the message goes to the Problems panel like
        any other.
        """
        if self.config.path is None or not self.config.path.is_file():
            return None
        try:
            self.config = Config.load(self.config.path)
        except CodeGeneratorError as error:
            return str(error)
        return None

    def load(self, path: Optional[Path] = None) -> List[Dict[str, object]]:
        """Read the XML model, and the project file around it.

        Both, because "Reload" means the project as it is on disk - not the
        parameter list on disk inside the settings this session started with.
        """
        broken_project = self.reread_project()
        target = Path(path) if path else self.path
        diagnostics = DiagnosticCollector()
        if target is not None and target.is_file():
            self.model = read_xml(target, diagnostics)
            self.path = target
        else:
            self.model = ParameterList()
            self.path = target
        self._ensure_defines()
        self._undo.clear()
        self._redo.clear()
        self.load_problems = diagnostics.to_list()
        if broken_project:
            self.load_problems.insert(0, {
                "severity": "error", "code": "CFG001", "message": broken_project,
                "location": {"file": str(self.config.path), "sheet": None, "row": None,
                             "column": None, "parameter": None},
                "hint": "The settings from before the edit are still in use.",
            })

        # In a parameter table the file names the sub-system, and the list has to
        # say it too: a project generating smart data from the same file decides
        # the sub-system by the tag.  Set here, in memory - the grid shows it at
        # once - and said out loud until the list is written.  Not marked as a
        # change, so merely opening a list starts no "unsaved changes" prompts.
        stamped = self._stamp_system_names()
        if stamped:
            system = self._list_system()
            self.load_problems.append({
                "severity": "warning", "code": "PTB008",
                "message": (f"{len(stamped)} parameter(s) of this sub list did not "
                            f"say {system} in Tag System Name (the first: "
                            f"'{stamped[0].name}'). The editor has set it - save the "
                            f"sub list to write it into the file."),
                "location": {"file": str(self.path), "sheet": None, "row": None,
                             "column": None, "parameter": stamped[0].name,
                             "structType": None},
                "hint": ("In a parameter table the file name decides the sub-system. "
                         "The tag is what a project generating smart data from the "
                         "same sub list uses, so the sub list has to carry it."),
            })
        # A text a field shared across the elements of an array goes onto each
        # of its rows; it reads the same, so it is written at the next save.
        self._give_every_row_its_text()
        # What was read counts as saved - the stamping and the rows above
        # included, so merely opening a list does not mark it.
        self._saved_text = self._file_text()
        return self.load_problems

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError(NO_LIST)
        self._stamp_system_names(target)
        write_xml(self.model, target,
                  emit_timestamp=self.config.codegen.emit_timestamp)
        self.path = target
        self._saved_text = self._file_text()
        # The file now says what the model says, so whatever the reader
        # complained about on the way in is no longer true of it.
        self.load_problems = []
        return target

    # -- is it saved? -------------------------------------------------------
    @property
    def dirty(self) -> bool:
        """Whether the list differs from its file - the ``*`` in the editor.

        Compared, not remembered.  A flag every edit raised also counted the
        edit the form sends when a box is merely left, and stayed up after Undo
        had brought the list back to exactly what is on disk: a ``*`` on a list
        nobody had changed.
        """
        return self._file_text() != self._saved_text

    def _file_text(self) -> bytes:
        """The list and its structure types as saving writes them, as one text.

        Built by the writers' own element builders, without a timestamp and
        without *home*: that only decides how ``<Source file>`` is spelled, and
        resolving the path of every parameter on each call would cost more than
        the comparison.  Both sides of :attr:`dirty` are made the same way.
        """
        return (ET.tostring(model_to_element(self.model, emit_timestamp=False))
                + ET.tostring(types_to_element(self.model.struct_types)))

    def _ensure_defines(self) -> None:
        """The machine's drop-down lists, which are never empty.

        They come from the app rather than from this project, so an empty list
        is not a state a project can be in: at worst the machine has never had
        one and gets the shipped defaults.
        """
        self.model.defines = load_choices()

    def _list_system(self, path: Optional[Path] = None) -> Optional[str]:
        """The sub-system a parameter-table list's file names, as SYSTEM NAMES spells it.

        ``None`` outside a parameter-table project, without a list, or when the
        file names no sub-system - PTB005 reports that one, and writing its
        made-up name into a tag would only put an invalid value into the list.
        """
        target = path if path is not None else self.path
        if self.config.output.format != FORMAT_PARAM_TABLE or target is None:
            return None
        wanted = system_of(Path(target))
        return next((name for name in self.model.defines.get(COLUMN_SYSTEM_NAMES) or []
                     if str(name).upper() == wanted), None)

    def _stamp_system_names(self, path: Optional[Path] = None) -> List[Parameter]:
        """Write the list's sub-system into every parameter's Tag System Name.  (Reported.)

        In a parameter table the FILE says which sub-system a list is, and the
        form showed that - in place of the tag, which nothing ever set.  So a
        parameter added here said SYS_UNKNOWN in the grid and in the file, and
        the same list used by a smart-data project, where the tag is what
        counts, had its parameters in no sub-system at all.  The list is the
        database, so it has to say it.  The file decides: a tag naming another
        sub-system is corrected as well.  Returns the parameters that changed.
        """
        system = self._list_system(path)
        if system is None:
            return []
        changed = [parameter for parameter in self.model.parameters
                   if parameter.tags.get("SystemName") != system]
        for parameter in changed:
            parameter.tags["SystemName"] = system
        return changed

    # -- undo / redo --------------------------------------------------------
    def snapshot(self, label: str) -> None:
        """Remember the current state before changing it."""
        self._undo.append((label, copy.deepcopy(self.model)))
        del self._undo[:-UNDO_DEPTH]
        self._redo.clear()

    def undo(self) -> Optional[str]:
        if not self._undo:
            return None
        label, state = self._undo.pop()
        self._redo.append((label, copy.deepcopy(self.model)))
        self.model = state
        return label

    def redo(self) -> Optional[str]:
        if not self._redo:
            return None
        label, state = self._redo.pop()
        self._undo.append((label, copy.deepcopy(self.model)))
        self.model = state
        return label

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @contextlib.contextmanager
    def _change(self, label: str) -> Iterator[None]:
        """One edit, taken whole or not at all.

        The snapshot is taken first, as for every edit; if anything inside
        refuses, the model and both undo stacks go back to exactly what they
        were.  A refused edit used to leave half of itself behind - a type edit
        whose rename was refused had already written the new fields and never
        reshaped the structures of that type - and even though it changed
        nothing it left an undo step and the list marked modified.

        An edit that goes through but leaves the file's text as it was is no
        edit either, and leaves no undo step: the form sends every box whenever
        one is left, so clicking through a parameter used to fill the undo stack
        with steps that undid nothing.
        """
        undo, redo = list(self._undo), list(self._redo)
        text = self._file_text()
        self.snapshot(label)
        before = self._undo[-1][1]
        try:
            yield
        except Exception:
            self.model = before
            self._undo, self._redo = undo, redo
            raise
        # A structure that has just become an array leaves its fields' texts
        # shared by every element; each row gets its own, as on opening a list.
        self._give_every_row_its_text()
        if self._file_text() == text:
            self._undo, self._redo = undo, redo

    # -- is there anywhere to put a parameter? ------------------------------
    @property
    def has_list(self) -> bool:
        """Whether a parameter list is open - the only place a parameter lives."""
        return self.path is not None

    def _require_a_list(self) -> None:
        """Refuse an edit that would have nowhere to go.

        A brand new project has no list.  Adding a parameter to it used to
        work - into memory only - after which Save said "No file name given."
        and Generate wrote every output file from a parameter that existed
        nowhere on disk.
        """
        if not self.has_list:
            raise ValueError(NO_LIST)

    # -- finding nodes ------------------------------------------------------
    def find(self, path: str) -> Optional[Parameter]:
        return self.model.find(path) if path else None

    def parent_of(self, path: str) -> Tuple[Optional[Parameter], List[Parameter]]:
        """Return ``(parent node or None, the list the node lives in)``."""
        parts = path.split(PATH_SEPARATOR)
        if len(parts) == 1:
            return None, self.model.parameters
        parent = self.model.find(PATH_SEPARATOR.join(parts[:-1]))
        return parent, parent.children if parent else self.model.parameters

    # -- editing ------------------------------------------------------------
    def add_parameter(self, parent_path: str = "", kind: str = "primitive") -> str:
        """Add a parameter (or a struct) under *parent_path*; return its path."""
        self._require_a_list()
        if kind == "struct":
            self._refuse_structures_in_a_table()

        parent = self.find(parent_path) if parent_path else None
        if parent is not None and parent.is_struct:
            self._refuse_reshaping(parent, "added to")
        self.snapshot("add")
        siblings = parent.children if parent is not None and parent.is_struct \
            else self.model.parameters
        prefix = parent_path if (parent is not None and parent.is_struct) else ""

        node = Parameter(
            name=_unique_name("NewStruct" if kind == "struct" else "NewParameter", siblings),
            kind=ParameterKind.STRUCT if kind == "struct" else ParameterKind.PRIMITIVE)
        if node.is_primitive:
            node.value_type_name = "uint8_t"
            self._give_starting_values(node)
        if prefix == "":
            node.param_type = self.model.defines.get(COLUMN_TYPES)[0] \
                if self.model.defines.get(COLUMN_TYPES) else "MONITORING"
            node.tags = {spec.tag_id: _default_tag(spec, self.model.defines)
                         for spec in TAG_REGISTRY}
            # not the first SYSTEM NAMES entry, SYS_UNKNOWN: in a parameter table
            # the list's file already says which sub-system this is
            system = self._list_system()
            if system is not None:
                node.tags["SystemName"] = system
            # and what the format writes into every parameter is what a new one
            # is saved with - PARAM_MODE_NONE in a smart-data project
            node.tags.update(fixed_tags(self.config))
        siblings.append(node)
        return f"{prefix}{PATH_SEPARATOR}{node.name}" if prefix else node.name

    def _refuse_structures_in_a_table(self) -> None:
        """A parameter table has one value per row and no structures at all."""
        if self.config.output.format == FORMAT_PARAM_TABLE:
            raise ValueError(
                "This project generates a parameter table, which has no "
                "structures - every row is one value. Add parameters instead, "
                "or set output.format to 'smart_data' in the project file.")

    def _refuse_reshaping(self, structure: Optional[Parameter], done: str) -> None:
        """Refuse adding, deleting, duplicating or moving one field of a structure.

        The fields of a structure are its TYPE's: every parameter of the type has
        the same ones, which is what lets them share one C typedef.  These edits
        looked like they worked and were thrown away by the next thing that
        re-applied the type - a deleted field came back, a duplicated one
        vanished, and the generated code never had either.  So while the type
        exists they are refused, the way renaming a field already is.  A
        structure whose type is missing keeps whatever fields it has, and those
        can still be cleaned up.
        """
        if structure is None or not structure.is_struct:
            return
        type_name = structure.value_type_name or ""
        if self.find_struct_type(type_name) is None:
            return
        raise ValueError(
            f"A field cannot be {done} '{structure.name}' on its own: its fields "
            f"belong to the structure type '{type_name}', and every parameter of "
            f"that type has the same ones. Change them in 'Structure types…' and "
            f"they change everywhere at once.")

    def duplicate(self, path: str) -> Optional[str]:
        node = self.find(path)
        if node is None:
            return None
        parent, siblings = self.parent_of(path)
        self._refuse_reshaping(parent, "duplicated in")
        self.snapshot("duplicate")
        clone = copy.deepcopy(node)
        clone.name = _copy_name(node.name, siblings)
        _clear_log_ids(clone)
        # A fixed table address belongs to one row: the copy is placed by the
        # firmware until somebody gives it an address of its own.
        clone.address = 0
        siblings.insert(siblings.index(node) + 1, clone)
        prefix = path.rsplit(PATH_SEPARATOR, 1)[0] if PATH_SEPARATOR in path else ""
        return f"{prefix}{PATH_SEPARATOR}{clone.name}" if prefix else clone.name

    def delete(self, path: str) -> bool:
        """Delete the node at *path* - and never its structure type.

        A type is its list's until somebody deletes it in 'Structure types…',
        and nowhere else: deleting the last structure of a type leaves the type
        in the list, unused.  (Deleting a structure used to offer its type
        along - asked for once, then asked to go: the type is a declaration of
        the list, and a structure is only one use of it.)  An unused type costs
        nothing: it generates nothing and is not in the build's merged types
        file, and a problem it has is only a warning.
        """
        node = self.find(path)
        if node is None:
            return False
        parent, siblings = self.parent_of(path)
        self._refuse_reshaping(parent, "deleted from")
        with self._change("delete"):
            siblings.remove(node)
        return True

    def move(self, path: str, offset: int) -> Optional[str]:
        node = self.find(path)
        if node is None:
            return None
        parent, siblings = self.parent_of(path)
        self._refuse_reshaping(parent, "moved in")
        index = siblings.index(node)
        target = index + offset
        if not 0 <= target < len(siblings):
            return None
        self.snapshot("move")
        siblings.pop(index)
        siblings.insert(target, node)
        return path

    #: "Speed[3]", "Wheels[1]" - one part of a path, with the element it names.
    _ELEMENT = re.compile(r"(.+?)\[(\d+)\]")

    def value_at(self, path: str) -> Tuple[Optional[Parameter], Tuple[int, ...]]:
        """The declaration a VALUE path names, and which element of it that is.

        The grid draws one row per value - ``Speed[3]``, ``Wheels[1].Speed`` -
        while the tree holds one node per declaration.  A path with no index in
        it is a declaration and comes back with an empty element path, so
        everything that edits a whole parameter can go through here too.
        """
        names: List[str] = []
        indices: List[int] = []
        for part in path.split(PATH_SEPARATOR):
            found = self._ELEMENT.fullmatch(part)
            if found:
                names.append(found.group(1))
                indices.append(int(found.group(2)))
            else:
                names.append(part)
        return self.find(PATH_SEPARATOR.join(names)), tuple(indices)

    def update(self, path: str, changes: Dict[str, object]) -> Optional[str]:
        """Apply the values coming from the editor form.  Returns the new path.

        Only the fields the form actually offers are written.  The browser
        chooses the names (``data-field``), so without this list a stale page -
        or a typo - could set ``kind`` to a string or ``children`` to something
        that is not a list, and the next validation run would die inside
        ``/api/state``, which takes the whole editor down with it.
        """
        node, indices = self.value_at(path)
        if node is None:
            return None
        # Whole or not at all: a refused edit used to keep whatever it had set
        # before the refusal, add an undo step for nothing and mark the list
        # modified.
        with self._change("edit"):
            if indices:
                return self._apply_to_one_value(path, node, indices, changes)
            return self._apply_update(path, node, changes)

    def _apply_to_one_value(self, path: str, node: Parameter,
                            indices: Tuple[int, ...],
                            changes: Dict[str, object]) -> Optional[str]:
        """An edit made on ONE row with an index in it - a value such as
        Speed[3] or Wheels[1].Speed, or a row above values such as Wheels[1]
        or Wheels[1].Samples.

        Only the description and the User Name are that row's own.  The log id
        moves the whole block, so the value edited gets the number typed and the
        ids of the entry stay consecutive - that rule is not this edit's to
        break.  Everything else belongs to the declaration and therefore
        reaches every element, which is what the form says while a row is open.
        """
        changes = dict(changes)
        if "description" in changes:
            self._describe_one_value(path, node, indices, changes.pop("description"))
        if "user_name" in changes:
            self._name_one_value(path, node, indices, changes.pop("user_name"))
        if "log_id" in changes:
            self._move_the_log_block(path, changes.pop("log_id"))

        declaration = strip_array_indices(path)
        if changes:
            declaration = self._apply_update(declaration, node, changes) or declaration
        return _as_written(declaration, path)

    def _describe_one_value(self, path: str, node: Parameter,
                            indices: Tuple[int, ...], text: object) -> None:
        """Give ONE row its own description, or take it back.

        Every element is the same kind of thing, ``[0]`` included: what is
        typed here belongs to THIS row - and to every value under it that has
        none of its own - and to no other row.  (Asked for: Wheels[0].Samples
        used to write the text of Samples in every wheel.)

        Emptying the box, or typing exactly what the row reads from above it,
        hands the row back: it says nothing of its own and follows the rows
        above again.  That is also what keeps an ordinary edit ordinary - the
        form sends every box on every change, so a row with no description of
        its own must not acquire one because its unit was edited.
        """
        wanted = str(text).strip() if text is not None else ""
        if not wanted or wanted == self.text_above(path, "description"):
            node.element_descriptions.pop(element_key(indices), None)
            return
        node.element_descriptions[element_key(indices)] = wanted

    def _name_one_value(self, path: str, node: Parameter, indices: Tuple[int, ...],
                        text: object) -> None:
        """Give ONE row a User Name of its own, or take it back.  (Asked for.)

        Exactly the rule of the description: the name reaches every value
        under the row that has none of its own, and emptying the box - or
        typing the name the row would read anyway - hands it back.
        """
        wanted = str(text).strip() if text is not None else ""
        if not wanted or wanted == self.text_above(path, "user_name"):
            node.element_user_names.pop(element_key(indices), None)
            return
        node.element_user_names[element_key(indices)] = wanted

    def row_chain(self, path: str) -> List[Tuple[Parameter, Tuple[int, ...]]]:
        """Every row from the top level entry down to the row *path* names.

        Each node on the way with the element path it has there:
        ``Wheels[1].Samples`` is ``[(Wheels, (1,)), (Samples, (1,))]``.  Empty
        when the path names no node.
        """
        chain: List[Tuple[Parameter, Tuple[int, ...]]] = []
        nodes = self.model.parameters
        indices: Tuple[int, ...] = ()
        for part in path.split(PATH_SEPARATOR):
            found = self._ELEMENT.fullmatch(part)
            name = found.group(1) if found else part
            node = next((item for item in nodes if item.name == name), None)
            if node is None:
                return []
            if found:
                indices = indices + (int(found.group(2)),)
            chain.append((node, indices))
            nodes = node.children
        return chain

    def text_above(self, path: str, field: str) -> str:
        """What the row *path* reads for *field* when it says nothing itself.

        *field* is ``"user_name"`` or ``"description"``.  The rows above it,
        nearest first, the way flatten() reads them: the shorter element paths
        of its own node down to its declaration, then the rows of the
        structures it is in.  A declaration of its own - a row with no index -
        reads only the structures it is in.
        """
        chain = self.row_chain(path)
        if not chain:
            return ""
        def over(node: Parameter, indices: Tuple[int, ...]) -> Optional[str]:
            return (node.user_name_over(indices) if field == "user_name"
                    else node.description_over(indices))

        node, indices = chain[-1]
        found = over(node, indices[:-1]) if indices else None
        for above, above_indices in reversed(chain[:-1]):
            if found:
                break
            found = over(above, above_indices)
        return (found or "").strip()

    def _give_every_row_its_text(self) -> None:
        """Hand a text one field shared across the elements of an array to each
        of its rows.  (Asked for.)

        A field of an array of structures used to carry one User Name and one
        description for every element at once - Wheels[0].Samples was where it
        was written, and it reached the Samples of every wheel.  Now a row
        reaches only what is under it, and that shared text would have no row
        left to be seen or edited on; so it is written onto every row it
        reached - Wheels[0].Samples, Wheels[1].Samples, ... - except a row that
        already has its own, which never read it.  What every value reads is
        exactly what it read before, so nothing generated changes.
        """
        def walk(node: Parameter, sizes: List[int]) -> None:
            if sizes:
                for field_name, rows in (("user_name", node.element_user_names),
                                         ("description", node.element_descriptions)):
                    text = getattr(node, field_name)
                    if not (text or "").strip():
                        continue
                    for element in itertools.product(*(range(size) for size in sizes)):
                        rows.setdefault(element_key(element), text)
                    setattr(node, field_name, None)
            inside = sizes + ([node.array_size] if node.array_size > 1 else [])
            for child in node.children:
                walk(child, inside)

        for parameter in self.model.parameters:
            walk(parameter, [])

    def _move_the_log_block(self, path: str, wanted: object) -> None:
        """Set the log id OF ONE VALUE by moving the block it belongs to.

        The ids of one top level entry are handed out in one run - the entry
        holds the first and every value after it takes the next - so a value in
        the middle cannot be given a number of its own without breaking that.
        What it can do is MOVE the run: asking for 57 on Speed[7] of a block
        based at 45 puts the base at 50, and every element follows.
        """
        root_name = path.split(PATH_SEPARATOR)[0].split("[")[0]
        root = self.find(root_name)
        if root is None:
            return

        if wanted is None or (isinstance(wanted, str) and not str(wanted).strip()):
            root.log_id = None          # no id at all, for the whole block
            return
        try:
            number = int(str(wanted).strip())
        except (TypeError, ValueError):
            raise ValueError(f"'{wanted}' is not a whole number, so it cannot be a "
                             f"log id.") from None

        offset = self._offset_in_the_block(root_name, path)
        if offset is None:              # disabled: it produces no value at all
            root.log_id = number
            return
        if number - offset < 0:
            raise ValueError(
                f"'{path}' is value {offset + 1} of '{root_name}', so a log id of "
                f"{number} would start the block at {number - offset}. The ids of "
                f"one parameter run one after another, so this value needs at "
                f"least {offset}.")
        if number > LOG_ID_MAX:
            raise ValueError(f"A log id is a uint16_t: 0 to {LOG_ID_MAX}.")
        root.log_id = number - offset

    def _offset_in_the_block(self, root_name: str, path: str) -> Optional[int]:
        """How many values of that entry come before *path*, or None if it has none."""
        block = [leaf for leaf in self.model.flatten()
                 if strip_array_indices(leaf.name).split(PATH_SEPARATOR)[0] == root_name]
        for offset, leaf in enumerate(block):
            if leaf.name == path:
                return offset
        return None

    def _apply_update(self, path: str, node: Parameter,
                      changes: Dict[str, object]) -> Optional[str]:
        """What :meth:`update` does, inside its :meth:`_change`."""
        previous_type = node.value_type_name

        # A parameter table has one value per row and no structures at all.
        # Refused here as well as hidden in the form, so a page left open from
        # before the format was changed cannot write one either.
        if self.config.output.format == FORMAT_PARAM_TABLE:
            wanted = changes.get("array_size")
            if wanted is not None and int(wanted) > 1:
                raise ValueError(
                    f"This project generates a parameter table, where every row "
                    f"is one value, so an array size of {int(wanted)} has "
                    f"nowhere to go. Write that many parameters instead, or set "
                    f"output.format to 'smart_data' in the project file.")

        # Tags and the type belong to the top level entry.  A field inside a
        # structure cannot set them, so drop them here as well as in the form -
        # that way a stale page can never write them either.
        if PATH_SEPARATOR in path:
            changes.pop("tags", None)
            changes.pop("param_type", None)

            # ...and the SHAPE of a field belongs to its structure type: its
            # name, what it holds and how many of it there are.  Writing one
            # here looked like it worked and was then thrown away by the next
            # thing that re-applied the type - the edit simply vanished, with
            # nothing anywhere to say why.  Refusing it and pointing at the type
            # is the honest answer.  The unit and the description are NOT in
            # this list: they say what this use of the type means, and one xyz
            # type is a speed in one parameter and an offset in another.
            # Whether a field is generated at all is the type's too: every
            # parameter of a type is an instance of one C typedef, so they all
            # have the same fields.
            owned = [key for key in ("name", "value_type_name", "array_size",
                                     "enable") if key in changes]
            if owned:
                owner = self.find(path.split(PATH_SEPARATOR)[0])
                type_name = owner.value_type_name if owner is not None else ""
                shown = {"name": "name", "value_type_name": "data type",
                         "array_size": "array size", "enable": "enabled flag"}
                named = f"'{type_name}'" if type_name else "of its structure"
                raise ValueError(
                    f"The {', '.join(shown[key] for key in owned)} of a field "
                    f"belongs to the structure type {named}, not to this "
                    f"parameter - every parameter of that type has the same "
                    f"fields. Change it in 'Structure types…' and it changes "
                    f"everywhere at once.")

        new_path = path
        if "name" in changes:
            name = str(changes.pop("name") or "").strip()
            _reject_path_characters(name)
            self._reject_duplicate_name(path, node, name)
            if name and name != node.name:
                node.name = name
                prefix = path.rsplit(PATH_SEPARATOR, 1)[0] if PATH_SEPARATOR in path else ""
                new_path = f"{prefix}{PATH_SEPARATOR}{name}" if prefix else name

        tags = changes.pop("tags", None)
        if isinstance(tags, dict):
            tags = dict(tags)
            # In a parameter table the sub-system tag is the file's - the editor
            # writes it into every parameter - so the form shows it read-only,
            # and a form with no field for a tag sends no value for it, which
            # through the line below would DELETE it.  The parameter list is
            # shared: a smart-data project opening the same file decides the
            # sub-system by that tag.  So in this format it keeps what it had.
            # (Reset proof and the logging tags are the form's to set.)
            # A smart-data project does the same with the access mode: it
            # writes PARAM_MODE_NONE for every parameter, the form shows that
            # read-only, and the sub list keeps its own value - a parameter-
            # table project building the same list uses it.
            kept = list(fixed_tags(self.config))
            if self.config.output.format == FORMAT_PARAM_TABLE:
                kept += READ_ONLY_TAGS
            for tag_id in kept:
                if tag_id in node.tags:
                    tags[tag_id] = node.tags[tag_id]
                else:
                    tags.pop(tag_id, None)
            # A free tag (Tag1..Tag4) comes from a text box, so '5' arrives as
            # text.  Held as the file reader holds it - the number 5 - or the
            # free-tag rule reported it as neither a number nor an identifier,
            # and only in the editor: the build read the file and was fine.
            for spec in TAG_REGISTRY:
                if spec.kind is TagKind.FREE and isinstance(tags.get(spec.tag_id), str):
                    tags[spec.tag_id] = convert_tag(spec.kind, tags[spec.tag_id])
            node.tags = tags

        if "address" in changes:
            changes["address"] = _checked_address(changes["address"])
        for key, value in changes.items():
            if key in EDITABLE_FIELDS:
                setattr(node, key, value)

        # The two worlds are kept apart here as well as in the form: a
        # structure IS of a structure type and a parameter IS of a data type,
        # and neither may be given the other's.  The drop-down never offers the
        # wrong ones, so this only ever catches a stale page - but silently
        # converting one into the other is how a parameter list used to end up
        # generating something nobody asked for.
        chosen = str(changes.get("value_type_name") or "")
        if chosen and node.is_struct and resolve_value_type(chosen) is not None:
            node.value_type_name = previous_type
            raise ValueError(
                f"'{node.name}' is a structure, so its type has to be a structure "
                f"type - '{chosen}' is a data type. Give '{chosen}' to one of its "
                f"fields, or delete this and add a parameter instead.")
        if chosen and node.is_primitive and self.find_struct_type(chosen) is not None:
            node.value_type_name = previous_type
            raise ValueError(
                f"'{node.name}' is a parameter, so it holds one value - "
                f"'{chosen}' is a structure type. Add a structure instead.")

        # A structure that was given a type it really may have is reshaped by
        # that type, right away: the fields are what the parameter now has.
        if chosen and node.is_struct and chosen != previous_type:
            self._resync()
            return new_path

        # The value type decides what the range, the resolution and the default
        # value even MEAN, so changing it has to bring them along.
        if "value_type_name" in changes:
            self._retune_for_type(node, previous_type)

        # ... and a boolean is held to its shape on EVERY edit, not only when
        # the type changed.  Its form has no minimum, maximum or resolution box,
        # so a number written into one of those - by a stale page, or by an
        # update that was already in flight when the type became bool_t - could
        # never be seen or corrected.  Every other type shows its fields, so a
        # wrong value there is visible and gets a diagnostic instead.
        self._hold_boolean_shape(node)
        self._hold_number_shape(node)

        return new_path

    @staticmethod
    def _hold_boolean_shape(node: Parameter) -> None:
        """Keep a boolean at the only shape a boolean can have.

        0 / 1 / 1 is the triple the range rule accepts in silence - it simply
        restates what a boolean is - and the default value has to be a real
        boolean rather than a number that happens to be truthy.
        """
        value_type = resolve_value_type(node.value_type_name)
        if node.is_struct or value_type is None or not value_type.is_bool:
            return

        node.minimum = 0
        node.maximum = 1
        node.resolution = 1
        if not isinstance(node.default_value, bool):
            node.default_value = bool(node.default_value)

    @staticmethod
    def _hold_number_shape(node: Parameter) -> None:
        """Keep the limits in the shape reading them back from the file gives.

        The form sends JSON numbers, and JSON writes a whole number without its
        ``.0``: a float32_t minimum read from the file as 0.0 came back from a
        box nobody touched as the int 0 - written "0" where the file says "0.0".
        Nothing had changed, and the list still counted as edited.  So a float
        type keeps floats and any other type keeps whole numbers whole, which
        is what ``_to_number`` in the XML reader makes of the file.
        """
        value_type = resolve_value_type(node.value_type_name)
        is_float = bool(value_type and value_type.is_float)
        for key in ("default_value", "minimum", "maximum", "resolution"):
            value = getattr(node, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if is_float:
                setattr(node, key, float(value))
            elif isinstance(value, float) and value.is_integer():
                setattr(node, key, int(value))

    def _reject_duplicate_name(self, path: str, node: Parameter, name: str) -> None:
        """Refuse a name another node at the same level already has.

        A node is addressed by its dotted path, so two siblings sharing a name
        share a path - and every lookup then finds the first of the two.  The
        validator did report the clash, but by then delete, move and edit were
        all acting on the wrong node: renaming a new parameter to match an
        existing one and then deleting it took the ORIGINAL away, with nothing
        on screen to say so.

        Uniqueness is therefore enforced where the name is typed, not where the
        model is checked.
        """
        if not name or name == node.name:
            return
        _parent, siblings = self.parent_of(path)
        for other in siblings:
            if other is not node and other.name == name:
                raise ValueError(
                    f"'{name}' is already used here. Two parameters at the same "
                    f"level cannot share a name - they would have the same path, "
                    f"and the editor could no longer tell them apart."
                )

    @staticmethod
    def _retune_for_type(node: Parameter, previous_type: Optional[str]) -> None:
        """Bring the type-dependent fields to values the NEW type can hold.

        Three of them depend on the type: the minimum, the maximum and the
        resolution describe a range in that type's units, and the default value
        has to be a value of it.  Left alone across a type change they become
        either meaningless or impossible:

        * ``float32_t`` -> ``bool_t`` kept a 0..120 range and a 0.1 resolution.
          A boolean has none of the three, so the form does not show them - and
          a value you cannot see is a value you cannot correct.  This was a
          dead end: the tool warned about something the editor gave no way to
          fix.
        * ``bool_t`` -> ``uint8_t`` kept ``DefaultValue = True``.
        * ``int32_t`` -> ``int8_t`` kept limits that do not fit in a byte.

        Only what is actually wrong for the new type is touched.  A limit that
        still fits was somebody's decision and stays.
        """
        if node.value_type_name == previous_type:
            return

        new_type = resolve_value_type(node.value_type_name)
        old_type = resolve_value_type(previous_type)

        # -- the resolution ------------------------------------------------
        # Per type: 1 for the integers, 0.001 for float32_t, 0.000001 for
        # float64_t.  1 on a float is not a rounding detail - it quantises
        # every value to whole numbers.  A resolution somebody chose is kept.
        old_default = _default_resolution(previous_type)
        if node.resolution is None or node.resolution == old_default:
            node.resolution = _default_resolution(node.value_type_name)

        # -- becoming a boolean --------------------------------------------
        if new_type is not None and new_type.is_bool:
            # A boolean has no range and no resolution, and the form has no box
            # for any of them, so they are cleared rather than left invisible.
            # 0 / 1 / 1 is the one triple that simply restates what a boolean
            # is; the range rule accepts it in silence, where 0 / 0 / 1 would
            # be reported as odd - and reported is exactly what this parameter
            # can no longer be fixed from.
            node.minimum = 0
            node.maximum = 1
            node.resolution = 1
            node.default_value = bool(node.default_value)
            return

        # -- leaving a boolean ---------------------------------------------
        if old_type is not None and old_type.is_bool:
            node.default_value = 1 if node.default_value else 0
            # "no range" - the generated code then uses the type's own limits
            node.minimum = 0
            node.maximum = 0
            return

        # -- number to number ----------------------------------------------
        if new_type is None or new_type.native_min is None:
            return
        low, high = new_type.native_min, new_type.native_max
        whole_only = not new_type.is_float

        def fits(value) -> bool:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            if not (low <= value <= high):
                return False
            # An integer type cannot hold 10.5 either.  C takes the literal and
            # quietly makes it 10, so a value that is merely IN RANGE is not yet
            # a value the new type can carry.
            return not whole_only or float(value).is_integer()

        # A limit the new type cannot express is reset to "no range" - both
        # zero - rather than clamped to a boundary nobody chose.  Resetting
        # only one of the two would leave a half range that reads like a
        # decision, so they go together.
        if not fits(node.minimum) or not fits(node.maximum):
            node.minimum = 0
            node.maximum = 0
        if not fits(node.default_value):
            node.default_value = 0

        # The resolution is a step in the units of the type, so a fractional one
        # means nothing on an integer - it would be written into the generated
        # code as a whole number the author never asked for.  A step somebody
        # chose that the new type CAN hold is left alone.
        if whole_only and node.resolution is not None:
            try:
                fractional = not float(node.resolution).is_integer()
            except (TypeError, ValueError):
                fractional = False
            if fractional:
                node.resolution = _default_resolution(node.value_type_name)

    # -- the parameter lists of the project --------------------------------------
    #
    # A project is one parameter list split over several files, one per
    # sub-module.  They all live in one folder (``inputs.model_directory``), and
    # the configuration says which of them take part in a build and in what
    # order - that order is the order of the indices in the generated code, so
    # it is a real decision and not a detail.  The editor writes that choice back
    # into pl_project.json, because that file is what run_generate.py reads:
    # if the two could disagree, the code someone generates from the command line
    # would not be the code they saw in the editor.

    def list_directory(self) -> Path:
        return self.config.inputs.model_directory

    def known_lists(self) -> List[Dict[str, object]]:
        """Every parameter list of the project, selected ones first, in order.

        A file in the folder that no configuration mentions is still shown -
        that is how somebody finds the list a colleague added - it is simply not
        selected, so it takes no part in the build until someone says so.
        """
        # A configuration edited by hand can name the same file twice; the rows
        # are what the dialog binds its checkboxes to, so each file appears once
        # here and 'select_lists' drops the duplicate when it writes back.
        chosen: List[Path] = []
        for path in self.config.inputs.model_files:
            if path not in chosen:
                chosen.append(path)

        directory = self.list_directory()
        # A "_types.xml" is a list's structure types, not a list.
        found = sorted(path for path in directory.glob("*.xml")
                       if not is_types_file(path)) if directory.is_dir() else []

        entries: List[Dict[str, object]] = []
        for order, path in enumerate(chosen):
            entries.append(self._list_entry(path, selected=True, order=order))
        for path in found:
            if path not in chosen:
                entries.append(self._list_entry(path, selected=False, order=-1))
        return entries

    def _list_entry(self, path: Path, *, selected: bool, order: int) -> Dict[str, object]:
        return {
            "path": str(path),
            "name": path.stem,
            "file": path.name,
            "selected": selected,
            "order": order,
            "exists": path.is_file(),
            "current": self.path is not None and path == self.path,
            "inFolder": path.parent == self.list_directory(),
        }

    def _admit_to_the_build(self, build: List[Path], adding: List[Path]) -> None:
        """Refuse a list that a parameter-table project could not build.

        In that format a list's FILE NAME is its sub-system.  A list named after
        none - or after one that already has a list - used to be created and put
        in the build, and only then reported as PTB005.  It is refused here
        instead, before anything is written or added.

        *build* is the build as it would be afterwards and *adding* the lists
        entering it.  Only those are judged: a build that already holds an old,
        badly named list can still be reordered, and PTB005 goes on reporting
        that one.
        """
        if self.config.output.format != FORMAT_PARAM_TABLE or not adding:
            return

        known = {name.upper()
                 for name in self.model.defines.get(COLUMN_SYSTEM_NAMES) or []}
        for path in adding:
            system = system_of(path)
            if system not in known:
                raise ValueError(
                    f"'{path.name}' does not name a sub-system: '{system}' is not in "
                    f"the 'SYSTEM NAMES' list, and in a parameter table a sub list's "
                    f"file name is its sub-system. Known: {', '.join(sorted(known)) or 'none'}.")

        # One list per sub-system.  The table is built one block per FILE, so two
        # lists of one sub-system would be two blocks for it, both numbered from 0.
        first_of: Dict[str, Path] = {}
        for path in build:
            system = system_of(path)
            first = first_of.setdefault(system, path)
            if first is path:
                continue
            path_is_new = any(_same_file(path, item) for item in adding)
            first_is_new = any(_same_file(first, item) for item in adding)
            if not (path_is_new or first_is_new):
                continue        # both were in the build already: not a choice made now
            if path_is_new and first_is_new and not _same_file(first, path):
                raise ValueError(
                    f"'{first.name}' and '{path.name}' both name {system}. A "
                    f"sub-system has one sub list: two would be two blocks for it "
                    f"in the table, both numbered from 0.")
            kept = first if path_is_new else path
            raise ValueError(
                f"{system} already has a parameter sub list in this build: "
                f"'{kept.name}'. A sub-system has one sub list: two would be two "
                f"blocks for it in the table, both numbered from 0.")

    def create_list(self, name: str, directory: str = "") -> Path:
        """Make a new, empty parameter list and add it to the build.

        It is written to disk straight away, so the file the editor is about to
        open really exists and ``run_generate.py`` sees the same project the
        editor does.

        *directory* is where to put it; empty means the project's own
        parameter-list folder, which is the usual case.  A sub-module that
        keeps its list next to its own code passes its own folder instead - the
        configuration then records a relative path and the build works exactly
        the same.
        """
        stem = _safe_stem(name)
        if not stem:
            # A name typed only in other letters (Persian, say) is emptied by
            # _safe_stem, and "needs a name" would contradict what was typed.
            raise ValueError(
                "A parameter sub list needs a name." if not str(name).strip() else
                "The name becomes the file name, so write it in English letters, "
                "digits, '_' or '-'.")

        target_directory = Path(directory).expanduser() if directory.strip() \
            else self.list_directory()
        if self.config.output.format == FORMAT_PARAM_TABLE:
            asked = target_directory / f"{stem}.xml"
            self._admit_to_the_build(
                list(self.config.inputs.model_files) + [asked], [asked])
            # The file name IS the sub-system, written the way this format's own
            # lists are: 'SYS_RHS' and 'sys_rhs_paramTable' both make
            # sys_rhs_paramTable.xml.
            stem = f"{system_of(asked).lower()}_paramTable"

        try:
            target_directory = target_directory.resolve()
            target_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ValueError(f"Cannot use the folder '{target_directory}': {error}") from error

        target = target_directory / f"{stem}.xml"
        if target.exists():
            instead = (" In a parameter table that file already is the sub-system's "
                       "sub list: add it with 'Add an existing parameter sub list' "
                       "instead."
                       if self.config.output.format == FORMAT_PARAM_TABLE else "")
            raise FileExistsError(
                f"'{target.name}' already exists in {target_directory}.{instead}")

        fresh = ParameterList()
        fresh.defines = copy.deepcopy(self.model.defines)
        write_xml(fresh, target, emit_timestamp=self.config.codegen.emit_timestamp)

        self.select_lists([str(path) for path in self.config.inputs.model_files]
                          + [str(target)])
        return target

    def inspect_list(self, path: str) -> Dict[str, object]:
        """Ask whether *path* is a parameter list this tool can build.

        This is the gate in front of "add an existing file": the editor lets
        somebody point at any XML on the machine, and an XML that is not a
        parameter list has to be refused *here*, with a reason - not accepted
        and then discovered halfway through a build, when the configuration has
        already been rewritten.

        Returns what the dialog needs to show: whether it fits, why not if it
        does not, and a short summary of what is inside if it does.
        """
        candidate = Path(path).expanduser()
        if not str(path).strip():
            return {"ok": False, "reason": "No file name given."}
        try:
            candidate = candidate.resolve()
        except OSError as error:
            return {"ok": False, "reason": f"Cannot read that path: {error}"}

        if not candidate.is_file():
            return {"ok": False, "reason": f"'{candidate}' does not exist."}
        if is_types_file(candidate):
            return {"ok": False,
                    "reason": f"'{candidate.name}' holds the structure types of "
                              f"'{_list_of_a_types_file(candidate)}', not a "
                              f"parameter sub list. Open that file instead."}
        if candidate.suffix.lower() != ".xml":
            return {"ok": False,
                    "reason": f"'{candidate.name}' is not an .xml file."}

        diagnostics = DiagnosticCollector()
        try:
            model = read_xml(candidate, diagnostics)
        except CodeGeneratorError as error:
            # read_xml raises for the two things that mean "this is not one of
            # ours at all": unparsable XML, and a different root element.
            return {"ok": False, "path": str(candidate), "reason": str(error)}

        # The rest of what OK would say, said now: the dialog used to learn only
        # "is it a parameter list?" here, and every other refusal - a list
        # already in the build, a name that is not a sub-system - after OK.
        in_build = any(_same_file(candidate, item) for item in self.config.inputs.model_files)
        if not in_build:
            refusal = self._why_not_added(candidate)
            if refusal:
                return {"ok": False, "path": str(candidate), "reason": refusal}

        structures = sum(1 for node in model.walk() if node.is_struct)
        # A file that parses can still have something to say about itself -
        # an unknown tag, a field carrying a type it should not.  It is not a
        # reason to refuse the file, but the dialog shows it.
        notes = [item["message"] for item in diagnostics.to_list()][:5]
        # ... and so is a structure type this build already has: a type belongs
        # to one list, so once added that is an error (TYP016) until one of
        # the two is renamed - better said before OK than found after it.
        if not in_build:
            taken = []
            for name in model.struct_types.names():
                owner = self._list_defining_type(name)
                if (not owner and self.path is not None and name in self.model.struct_types
                        and not _same_file(candidate, self.path)):
                    owner = self.path.stem
                if owner:
                    taken.append(f"'{name}' (also in {owner})")
            if taken:
                notes.insert(0, f"Its structure type(s) {', '.join(taken)} already "
                                f"exist in this project. A structure type belongs to "
                                f"one sub list, so after adding it, rename one of each "
                                f"pair.")
        return {
            "ok": True,
            "inBuild": in_build,
            "path": str(candidate),
            "name": candidate.stem,
            "values": len(model.flatten()),
            "parameters": len(model.parameters),
            "structures": structures,
            "types": model.struct_types.names(),
            "notes": notes,
        }

    def add_existing_list(self, path: str) -> Path:
        """Take an existing parameter list into the build - copying it in.

        A list from another project is **copied** into this one, together with
        the structures file beside it.  That is what keeps a project a folder
        you can move: every list it builds lives inside it, so its project file
        never has to point at somewhere else on the machine, and the two
        projects go on being independent - editing this copy cannot change what
        the other project generates.

        A list already inside this project is simply added to the build; there
        is nothing to copy.
        """
        verdict = self.inspect_list(path)
        if not verdict.get("ok"):
            raise ValueError(str(verdict.get("reason")
                                 or "That file is not a parameter sub list."))

        source = Path(str(verdict["path"]))
        if verdict.get("inBuild"):
            # Already one of this build's lists: there is nothing to add, and the
            # dialog is "Open a parameter list" - so it is opened.  It used to be
            # refused as "already part of the build", and nothing opened.
            return next(item for item in self.config.inputs.model_files
                        if _same_file(item, source))
        refusal = self._why_not_added(source)
        if refusal:
            raise ValueError(refusal)

        target = self._bring_into_the_project(source)
        self.select_lists([str(item) for item in self.config.inputs.model_files]
                          + [str(target)])
        return target

    def _why_not_added(self, source: Path) -> Optional[str]:
        """Why *source* cannot be added to this build - or ``None`` when it can.

        The one place these refusals live, asked by :meth:`inspect_list` for the
        verdict the Open dialog shows and by :meth:`add_existing_list` on OK, so
        the check and the button can never disagree.
        """
        try:
            self._admit_to_the_build(
                list(self.config.inputs.model_files) + [source], [source])
        except ValueError as error:
            return str(error)
        if self.config.output.format == FORMAT_PARAM_TABLE:
            # A copy that had to be renamed - sys_rhs_paramTable_2.xml - would
            # name no sub-system at all, so it is refused before it is made.
            landing = self.list_directory() / source.name
            outside = self.config.path.parent.resolve() not in source.parents
            if outside and landing.exists() and not _same_file(landing, source):
                return (f"This project already has a '{landing.name}' in its sub "
                        f"list folder, and a sub-system has one file: add that one to "
                        f"the build instead, or delete it first.")
        return None

    def _bring_into_the_project(self, source: Path) -> Path:
        """Copy *source* (and its structures) into the project's list folder.

        A file already under the project root stays where it is: somebody who
        keeps a list in a sub-folder of their project meant to.
        """
        root = self.config.path.parent.resolve()
        try:
            source.resolve().relative_to(root)
            return source            # already ours
        except ValueError:
            pass

        directory = self.list_directory()
        directory.mkdir(parents=True, exist_ok=True)

        target = directory / source.name
        if target.exists() and not _same_file(target, source):
            # Never write over a list this project already has: two different
            # lists of one name is exactly the mess the copy is meant to avoid.
            stem, suffix = source.stem, source.suffix
            index = 2
            while (directory / f"{stem}_{index}{suffix}").exists():
                index += 1
            target = directory / f"{stem}_{index}{suffix}"

        shutil.copy2(source, target)
        # The structures come along, whichever name their file still has: a
        # list whose types were in "<list>_structures.xml" used to arrive
        # without them, every structure in it naming a type nobody declared.
        # They land under the current name, beside the copy.
        structures = existing_types_file_for(source)
        if structures.is_file():
            shutil.copy2(structures, types_file_for(target))
        return target

    def remove_list(self, path: str, delete_file: bool = False) -> Dict[str, object]:
        """Take a list out of the build, and optionally delete its file.

        Removing the list that is currently open leaves the editor with nothing
        to show, so the caller is told which list to open instead - the first
        one still in the build, or none at all.

        Deleting the file is a separate flag rather than the same action: one is
        a change of mind about the build and is undone by adding the list back,
        the other is not undoable at all.
        """
        target = Path(path).expanduser()
        try:
            target = target.resolve()
        except OSError:
            pass

        remaining = [item for item in self.config.inputs.model_files
                     if not _same_file(item, target)]
        if len(remaining) == len(self.config.inputs.model_files) and not delete_file:
            raise ValueError(f"'{target.name}' is not part of the build.")

        if remaining:
            self.select_lists([str(item) for item in remaining])
        else:
            # An empty build would leave the generator with no input at all;
            # the configuration keeps its list rather than being emptied.
            raise ValueError("The build needs at least one parameter sub list.")

        deleted = False
        if delete_file and target.is_file():
            target.unlink()
            # ...and the structures beside it.  A list's structures describe
            # that list and nothing else, so one left behind is a file nobody
            # will ever open again - and the thing most likely to be copied
            # somewhere later and clash with a type that is still in use.  Under
            # either name the file may still have.
            for structures in (types_file_for(target), legacy_types_file_for(target)):
                if structures.is_file():
                    structures.unlink()
            deleted = True

        was_open = self.path is not None and _same_file(self.path, target)
        return {"removed": str(target), "deleted": deleted, "wasOpen": was_open,
                "openInstead": str(remaining[0]) if was_open else ""}

    def browse(self, directory: str = "") -> Dict[str, object]:
        """List the sub-folders and the .xml files of one folder.

        The editor runs in a browser, and a browser cannot hand a page a real
        path - a file input gives a name and a blob, never a location the
        generator could put in its configuration.  So the browsing is done
        here, where the paths are real.
        """
        default = self.path.parent if self.path is not None else self.list_directory()
        here, selected, missing = listing_target(str(directory), default)
        try:
            here = here.resolve()
        except OSError as error:
            return {"ok": False, "message": f"Cannot open that folder: {error}"}

        if not here.is_dir():
            return {"ok": False, "message": f"'{directory or here}' is not a folder."}

        try:
            entries = sorted(here.iterdir(), key=lambda item: item.name.lower())
        except OSError as error:
            return {"ok": False, "message": f"Cannot list '{here}': {error}"}

        folders, files = [], []
        for entry in entries:
            try:
                if entry.is_dir():
                    if not entry.name.startswith("."):
                        folders.append({"name": entry.name, "path": str(entry)})
                elif entry.suffix.lower() == ".xml" and not is_types_file(entry):
                    files.append({"name": entry.name, "path": str(entry)})
            except OSError:
                continue        # a folder we are not allowed to stat

        chosen = {str(item) for item in self.config.inputs.model_files}
        for item in files:
            item["inBuild"] = item["path"] in chosen

        parent = here.parent
        return {
            "ok": True,
            "directory": str(here),
            "parent": str(parent) if parent != here else "",
            "drives": machine_roots(),
            "folders": folders,
            "files": files,
            # what was typed, as far as it goes: the file it names, or the
            # part of it that is not there yet - see listing_target()
            "selected": selected,
            "missing": missing,
        }

    def select_lists(self, paths: List[str]) -> List[Path]:
        """Set which lists take part in a build, in this order.

        The choice is written into the configuration file *and* into the
        configuration this session is using, so the change takes effect at once
        without a restart.
        """
        directory = self.list_directory()

        # The same list twice would be merged twice, and every parameter in it
        # would collide with itself - a screenful of NAME003 errors about names
        # the user only wrote once.  The first mention wins, so the order the
        # user chose is kept.
        chosen: List[Path] = []
        for item in paths:
            if not str(item).strip():
                continue
            path = Path(item).expanduser().resolve()
            if path not in chosen:
                chosen.append(path)

        # A parameter table only takes lists it can build - judged for the ones
        # being ADDED, so a build that already holds an old, badly named list
        # can still be reordered, or have a list unticked.
        self._admit_to_the_build(
            chosen, [path for path in chosen
                     if not any(_same_file(path, old)
                                for old in self.config.inputs.model_files)])

        # A list that lives in the project's folder is written as a bare file
        # name, which is what makes the folder the one place lists live in; one
        # kept elsewhere keeps a path relative to the configuration file.
        names: List[str] = []
        for path in chosen:
            if path.parent == directory:
                names.append(path.name)
            else:
                names.append(relative_to_root(path, self.config.path.parent))

        rewrite_model_files(self.config.path, names)
        self.config.inputs.model_files = chosen
        return chosen

    # -- structure types ---------------------------------------------------
    #
    # A structure type is a C++ ``struct`` declaration: a name and the fields
    # inside it.  A parameter *names* one, so editing the type edits every
    # parameter that names it - add a field and every one of them grows it, in
    # the right place, with the log ids after it shifted along.
    #
    # A type belongs to the list that declares it: only the open list's own
    # types are offered, edited or used here, and a name another list of the
    # build already has is refused where it is typed.  (The types of the whole
    # project used to be offered, and using another list's copied it in - which
    # put one name into two lists, each of which could then reshape the other's
    # structures.)  A type nothing uses any more stays until it is deleted.

    def struct_types(self) -> List[Dict[str, object]]:
        """The open list's own types, as the Structure types panel shows them.

        Unused ones included: a type stays the list's until it is deleted.
        """
        rows: List[Dict[str, object]] = []
        for struct_type in self.model.struct_types.all():
            rows.append({
                "name": struct_type.name,
                "fields": [{"name": member.name,
                            "valueType": member.value_type_name,
                            "arraySize": member.array_size,
                            "enable": member.enable}
                           for member in struct_type.fields],
                "usedHere": self._uses_of_type(struct_type.name),
            })
        return rows

    def _uses_of_type(self, name: str) -> List[str]:
        """The parameters of the open list that are of type *name*."""
        found: List[str] = []

        def walk(node: Parameter, prefix: str) -> None:
            dotted = f"{prefix}{PATH_SEPARATOR}{node.name}" if prefix else node.name
            if node.is_struct and node.value_type_name == name:
                found.append(dotted)
            for child in node.children:
                walk(child, dotted)

        for parameter in self.model.parameters:
            walk(parameter, "")
        return found

    def find_struct_type(self, name: str) -> Optional[StructType]:
        """One of the open list's own types - the only ones it may use."""
        return self.model.struct_types.get(name)

    def create_struct_type(self, name: str,
                           fields: Optional[List[Dict[str, object]]] = None) -> str:
        """Declare a new structure type, with its fields when given.  Returns its name.

        The dialog sends the name and the fields together, and they are checked
        together before anything is declared.  It used to declare an empty type
        first and give it its fields in a second call - so a field the second
        call refused left an empty type behind (TYP007), and trying again said
        the name was taken.  Without *fields* the type starts empty, as before.
        """
        # a type is kept in the structures file beside a list; no list, no file
        self._require_a_list()
        name = self._new_type_name(name)
        members = self._fields_from(fields) if fields is not None else []
        with self._change("new type"):
            self.model.struct_types.put(StructType(name=name, fields=members))
        return name

    def _new_type_name(self, name: object) -> str:
        """*name* as a new structure type may have it - or a refusal saying why."""
        name = str(name or "").strip()
        if not name:
            raise ValueError("A structure type needs a name.")
        if not is_valid_c_identifier(name):
            raise ValueError(f"'{name}' is not a valid C identifier. It becomes a "
                             f"typedef, so use letters, digits and '_', and do not "
                             f"start with a digit.")
        if resolve_value_type(name) is not None:
            raise ValueError(f"'{name}' is a data type already. Choose another name.")
        if self.find_struct_type(name) is not None:
            raise ValueError(f"A structure type called '{name}' already exists.")
        self._refuse_a_name_another_list_has(name)
        return name

    def _refuse_a_name_another_list_has(self, name: str) -> None:
        """Refuse a type name another list of the build already declares.

        A type belongs to one list, so a name in two lists is an error (TYP016)
        - refused here, where the name is typed, rather than reported once the
        second list has it.
        """
        owner = self._list_defining_type(name)
        if owner:
            raise ValueError(
                f"The parameter sub list '{owner}' already has a structure type "
                f"called '{name}'. A structure type belongs to one sub list, so its "
                f"name has to be free in the whole project - choose another one.")

    def update_struct_type(self, name: str, changes: Dict[str, object]) -> str:
        """Change a type, and reshape every parameter that names it.

        ``changes`` may hold ``name`` and ``fields``.  A field is
        ``{name, valueType, arraySize, enable}`` - its unit and description belong to
        each parameter that uses the type - and the list is
        taken as the whole truth: what is not in it has been removed, and the
        order given is the order of the C members.
        """
        # Everything is checked before anything changes.  A rename refused after
        # the new fields had been written used to leave the type changed and
        # its structures not reshaped.
        struct_type = self.model.struct_types.get(name)
        if struct_type is None:
            raise ValueError(f"This sub list has no structure type called '{name}'.")

        members = self._fields_from(changes["fields"]) if "fields" in changes else None
        asked = changes.get("name", name)
        new_name = str(name if asked is None else asked).strip()
        if new_name != name:
            if not new_name:
                raise ValueError("A structure type needs a name.")
            if not is_valid_c_identifier(new_name):
                raise ValueError(f"'{new_name}' is not a valid C identifier.")
            if resolve_value_type(new_name) is not None:
                raise ValueError(f"'{new_name}' is a data type already.")
            if self.find_struct_type(new_name) is not None:
                raise ValueError(f"A structure type called '{new_name}' already exists.")
            self._refuse_a_name_another_list_has(new_name)

        with self._change("edit type"):
            if members is not None:
                struct_type.fields = members
            if new_name != name:
                self._rename_struct_type(name, new_name)
            self._resync()
        return new_name

    def _field_from(self, raw: Dict[str, object]) -> StructField:
        field_name = str(raw.get("name") or "").strip()
        if not field_name:
            raise ValueError("Every field of a structure type needs a name.")
        if not is_valid_c_identifier(field_name):
            raise ValueError(f"'{field_name}' is not a valid C identifier; it becomes "
                             f"a C member name.")
        value_type = str(raw.get("valueType") or "").strip()
        try:
            array_size = max(1, int(raw.get("arraySize") or 1))
        except (TypeError, ValueError):
            array_size = 1
        enable = raw.get("enable", True)
        if not isinstance(enable, bool):
            enable = str(enable).strip().lower() not in ("false", "0", "no", "")
        return StructField(name=field_name, value_type_name=value_type,
                           array_size=array_size, enable=enable)

    def _fields_from(self, raw: object) -> List[StructField]:
        """A type's fields as a dialog sends them, checked as a whole.

        Each one named and a valid C identifier (:meth:`_field_from`), no two
        with one name, each holding a data type or a structure type the project
        has - and at least one of them, since an empty struct generates a
        typedef nothing can be built from.  Refused here, with the reason,
        rather than written and reported afterwards: once written, a broken
        type outlived the structure it had been made for.
        """
        items = raw if isinstance(raw, list) else []
        members = [self._field_from(item if isinstance(item, dict) else {})
                   for item in items]
        if not members:
            raise ValueError("A structure type needs at least one field - an empty "
                             "struct generates a typedef nothing can be built from.")
        seen: set = set()
        for member in members:
            if member.name in seen:
                raise ValueError(f"Two fields are called '{member.name}'; the members "
                                 f"of one struct need different names.")
            seen.add(member.name)
            wanted = member.value_type_name
            if not wanted:
                raise ValueError(f"Field '{member.name}' has no data type.")
            if resolve_value_type(wanted) is not None:
                continue
            # this list's own types only: a field of another list's type is a
            # use of that type, and no list may use another's
            if self.find_struct_type(wanted) is None:
                raise ValueError(
                    f"Field '{member.name}' is of type '{wanted}', which is neither "
                    f"a data type nor a structure type of this sub list.")
        return members

    def _rename_struct_type(self, old: str, new: str) -> None:
        """Rename a type here, and every mention of it in this list."""
        self.model.struct_types.rename(old, new)
        for struct_type in self.model.struct_types.all():
            for member in struct_type.fields:
                if member.value_type_name == old:
                    member.value_type_name = new
        for node in self.model.walk():
            if node.is_struct and node.value_type_name == old:
                node.value_type_name = new

    def delete_struct_type(self, name: str) -> Tuple[bool, str]:
        """Remove a type.  ``(removed, why not)``.

        A type still used by a parameter is not removed: the parameters would
        lose their shape, and "it is in use" is the answer somebody needs.
        """
        used = self._uses_of_type(name)
        if used:
            shown = ", ".join(used[:4]) + (" …" if len(used) > 4 else "")
            return False, (f"'{name}' is still used by {len(used)} parameter(s): "
                           f"{shown}. Change them to another type, or delete them.")

        holders = self.model.struct_types.uses_of(name)
        if holders:
            return False, (f"'{name}' is a field of the structure type(s) "
                           f"{', '.join(holders)}. Remove those fields first.")

        if name not in self.model.struct_types:
            return False, f"This sub list has no structure type called '{name}'."

        self.snapshot("delete type")
        self.model.struct_types.remove(name)
        return True, ""

    def _list_defining_type(self, name: str) -> str:
        """Which OTHER parameter list of the build declares *name*, if any.

        Read from each list's types file, under its current name or its older
        one, the way opening that list would read it.  The open list is
        skipped by file, not by spelling: the configuration and the editor may
        name one file two ways.
        """
        for path in self.config.inputs.model_files:
            if self.path is not None and _same_file(path, self.path):
                continue
            try:
                if name in read_types(existing_types_file_for(path)):
                    return path.stem
            except CodeGeneratorError:
                continue
        return ""

    def use_struct_type(self, path: str, name: str) -> Optional[str]:
        """Make the parameter at *path* a structure of type *name*."""
        node = self.find(path)
        struct_type = self.find_struct_type(name)
        if node is None or struct_type is None:
            return None
        with self._change("set type"):
            self._give_type(node, struct_type)
        return path

    def _give_type(self, node: Parameter, struct_type: StructType) -> None:
        """Make *node* a structure of *struct_type* - one of this list's own - reshaped to it."""
        node.kind = ParameterKind.STRUCT
        node.value_type_name = struct_type.name
        # A structure holds fields, not a value: whatever this parameter was
        # when it held one has no meaning any more.
        node.unit = None
        node.default_value = None
        node.minimum = None
        node.maximum = None
        node.resolution = None
        self._resync()

    def add_structure(self, name: str, type_name: str,
                      fields: Optional[List[Dict[str, object]]] = None) -> str:
        """Add a structure of *type_name*, declaring the type too when *fields* come.

        One step, checked whole before anything changes, and one undo step.  The
        dialog used to make separate calls - declare the type, give it its
        fields, add a structure, name it, give it the type - and a refusal half
        way left the earlier ones behind: an empty type when a field had no
        name, a ``NewStruct`` with no type when the name was taken.  Undo then
        walked back through each of those broken states in turn.

        Returns the path of the new structure.
        """
        self._require_a_list()
        self._refuse_structures_in_a_table()

        name = str(name or "").strip()
        if name:
            _reject_path_characters(name)
            if not is_valid_c_identifier(name):
                raise ValueError(
                    f"'{name}' is not a valid C identifier. A structure becomes a C "
                    f"variable, so use letters, digits and '_', and do not start "
                    f"with a digit.")
            self._reject_duplicate_name(name, Parameter(name=""), name)
        else:
            name = _unique_name("NewStruct", self.model.parameters)

        type_name = str(type_name or "").strip()
        if fields is None:
            struct_type = self.find_struct_type(type_name)
            if struct_type is None:
                raise ValueError(
                    f"This sub list has no structure type called '{type_name}'." if type_name
                    else "A structure needs a structure type: pick one, or declare "
                         "a new one.")
            declared = None
        else:
            declared = StructType(name=self._new_type_name(type_name),
                                  fields=self._fields_from(fields))
            struct_type = declared

        with self._change("add structure"):
            if declared is not None:
                self.model.struct_types.put(declared)
            node = Parameter(name=name, kind=ParameterKind.STRUCT)
            node.param_type = self.model.defines.get(COLUMN_TYPES)[0] \
                if self.model.defines.get(COLUMN_TYPES) else "MONITORING"
            node.tags = {spec.tag_id: _default_tag(spec, self.model.defines)
                         for spec in TAG_REGISTRY}
            node.tags.update(fixed_tags(self.config))
            self.model.parameters.append(node)
            self._give_type(node, struct_type)
        return name

    def _resync(self) -> None:
        """Make every structure in the open list match its type again.

        By the list's OWN types.  The merged library used to be used - and the
        merge keeps the first declaration of a name, so another list declaring
        the same name reshaped this list's structures to its fields: a field
        this list had and the other did not was dropped, limits, unit and
        description with it, the first time anything here was edited.

        A field the type has just given a structure starts with the values a
        new parameter starts with, and a field whose type changed has its
        values brought to the new type, the way a parameter's are.  (Asked for:
        a field used to start with nothing at all, so a new structure opened
        with a warning on every field, each to be filled in by hand.)  Fields
        that were there already keep what they have.
        """
        # the nodes themselves are held, so none of them can be freed and its
        # id handed to a new field while the type is applied
        before = {id(node): (node, node.value_type_name) for node in self._fields()}
        apply_types(self.model.parameters, self.model.struct_types)
        for node in self._fields():
            if id(node) not in before:
                self._give_starting_values(node)
            elif node.is_primitive and node.value_type_name != before[id(node)][1]:
                self._retune_for_type(node, before[id(node)][1])
                self._hold_number_shape(node)

    def _fields(self) -> Iterator[Parameter]:
        """Every field of every structure of the open list, at any depth."""
        for parameter in self.model.parameters:
            for node in parameter.walk():
                if node is not parameter:
                    yield node

    @classmethod
    def _give_starting_values(cls, node: Parameter) -> None:
        """The values a new value starts with, so it starts with no warning.

        A default of 0 and no range - Minimum and Maximum both 0, which the
        generated code reads as the whole range of the type - with the type's
        own resolution.  A boolean starts at FALSE with 0 / 1 / 1, the one
        triple the range rule takes in silence (see _retune_for_type).  A
        structure holds no value, so it gets nothing.
        """
        if not node.is_primitive:
            return
        value_type = resolve_value_type(node.value_type_name)
        if value_type is not None and value_type.is_bool:
            node.default_value, node.minimum, node.maximum, node.resolution = False, 0, 1, 1
            return
        node.default_value, node.minimum, node.maximum = 0, 0, 0
        node.resolution = _default_resolution(node.value_type_name)
        cls._hold_number_shape(node)

    # -- defines -------------------------------------------------------------
    def set_defines(self, column: str, values: List[str]) -> None:
        """Change one of the machine's drop-down lists.

        Not an edit of this project: the lists belong to the app, so this is
        written to ``paramgen/var/choices.json`` and every project on the machine
        sees it.  It is deliberately NOT on the undo stack for that reason -
        undoing an edit to this parameter list must not quietly change the
        company's list of sub-systems back.

        The system names and the parameter modes come as ``SYS_NAV = 16`` - a
        name and the number its #define gets - and a line that cannot be read
        raises ``ValueError`` before anything is changed.
        """
        column = column.upper()
        if column in GENERATED_DEFINES:
            names, numbers = parse_numbered(values)
            self.model.defines.values[column] = names
            self.model.defines.numbers[column] = numbers
        else:
            self.model.defines.values[column] = [str(v).strip()
                                                 for v in values if str(v).strip()]
        save_choices(self.model.defines)

    # -- validation and generation -------------------------------------------
    def merged_model(self, diagnostics: Optional[DiagnosticCollector] = None
                     ) -> ParameterList:
        """This sub list as it is being edited, plus the others as they are on disk.

        The project is one parameter list even when it is split over several
        files, so a name or a log id clashing with another sub list has to
        show up while editing, not at the end.

        Built in the order of ``inputs.model_files``, which is the order the
        generator merges them in - so the position of a parameter here is the
        index it gets in the generated table.  Appending the edited list first
        and the rest after would give the right *set* and the wrong *numbers*.
        """
        parts = self.merged_parts(diagnostics)
        if not parts:
            # with nothing merged this is the open list itself, so the tags the
            # format fixes go onto a copy - the list keeps its own values
            if not fixed_tags(self.config):
                return self.model
            return apply_fixed_tags(copy.deepcopy(self.model), self.config)
        # The generator's own merge, so both see the same clashes: which list
        # declares which structure type is only known while they are apart.
        # Every part is already a copy, so the fixed tags can go on as the
        # generator puts them on.
        return apply_fixed_tags(merge_lists(parts), self.config)

    def merged_parts(self, diagnostics: Optional[DiagnosticCollector] = None
                     ) -> List[Tuple[Path, ParameterList]]:
        """The sub lists :meth:`merged_model` merges, still apart, in its order.

        ``(file, list)`` per sub list - the open one as it is being edited, the
        others as they are on disk, each its own copy.  Empty when none of them
        is anywhere to be found.  Kept apart for the editor's index column: a
        name is unique in one sub list only, so which value is whose can only
        be told while each list is still on its own.
        """
        # Resolved, because the same file reached by two different paths is one
        # file: opening '../parameter_lists/power.xml' while the configuration
        # holds the absolute path used to merge that list twice, which doubled
        # every index and invented name clashes with itself.
        open_path = self.path.resolve() if self.path else None

        # Problems the READER finds in the other lists - a resolution of "1.1"
        # on an int8_t, a number that will not parse - used to be thrown away
        # here, so the editor showed a clean model and then Generate refused it
        # with a message about a file the reader never mentioned.  Pass a
        # collector in and they reach the Problems panel like everything else.
        quiet = diagnostics if diagnostics is not None else DiagnosticCollector()
        parts: List[Tuple[Path, ParameterList]] = []
        seen = False
        for path in self.config.inputs.model_files:
            if open_path is not None and path.resolve() == open_path:
                parts.append((self.path, copy.deepcopy(self.model)))
                seen = True
            elif path.is_file():
                parts.append((path, read_xml(path, quiet)))

        if not parts:
            return parts
        if not seen and self.path is not None:
            # The open list is not part of the build; it still has to be
            # validated against the rest, it just contributes no indices.
            parts.append((self.path, copy.deepcopy(self.model)))
        return parts

    def validate(self) -> List[Dict[str, object]]:
        """Every problem in the whole build, as the Problems panel shows them.

        Both halves are collected: what the READER says about the other lists
        on disk, and what the RULES say about the merged model.  Leaving the
        first half out is how the editor came to report a clean model that the
        generator then refused.
        """
        diagnostics = DiagnosticCollector()
        model = self.merged_model(diagnostics)
        Validator(self.config).validate(model, diagnostics)
        # ... plus what the reader said about the open file itself.  A value it
        # refused - a resolution of "1.1" on an int8_t - is gone from the model,
        # so re-validating can never find it again; but it is still in the file,
        # and the file is what the generator reads.
        return self.load_problems + diagnostics.to_list()

    def validate_codes(self, code: str) -> int:
        """How many problems of one code the open list has.

        A small thing the tests lean on constantly: "is this reported, and only
        once?" is the question almost every rule needs answered.
        """
        return sum(1 for item in self.validate() if item["code"] == code)

    def generate(self) -> Dict[str, object]:
        """Save the model, then generate the code from every configured module.

        Saving first is not a convenience - it is what keeps the editor and
        ``run_generate.py`` from ever disagreeing.  If the editor generated from the
        model in its memory while the file on disk still held the previous
        version, the next command line run would silently produce different
        code.  So the file is written first, and the generator then reads the
        same files the command line reads.
        """
        # The project file is read again first, so that generating from the
        # editor and running run_generate.py can never write to two different
        # places.  Both read the same file at the moment they run.
        broken_project = self.reread_project()
        if broken_project:
            return {"success": False, "message": broken_project, "files": [],
                    "count": 0, "saved": "", "modules": [], "diagnostics": [],
                    "drift": None}

        diagnostics = DiagnosticCollector()
        pipeline = Pipeline(self.config)

        saved = None
        if self.path is not None:
            saved = self.save()

        # Everything is read back from disk and merged, so the editor generates
        # exactly what "run.bat generate" would - always, including when no list
        # is open.  That case used to generate from the model in memory, so a
        # project with no parameter list at all wrote every output file from
        # parameters that existed nowhere on disk, while the command line,
        # reading the very same project, generated nothing.
        model = pipeline.load_model(diagnostics)

        result = pipeline.generate(model, diagnostics)
        drift = result.drift
        return {
            "success": result.success,
            # Always present, so that "why did nothing happen?" is answered by
            # the same field whether the run was refused by the validator or
            # blew up in the tool.  Without it a failed build came back with no
            # message at all and every caller had to invent one.
            "message": "" if result.success else _refusal(diagnostics),
            "files": [str(path) for path in result.generated_files],
            "count": result.parameter_count,
            "saved": str(saved) if saved else "",
            "modules": [str(path) for path in self.config.inputs.model_files],
            "diagnostics": diagnostics.to_list(),
            # What this build moved relative to the last one.  A value that
            # changed byte offset is a value a board already in the field will
            # read wrongly, so the editor shows this before anything else.
            "drift": {
                "breaksStoredData": drift.breaks_stored_data,
                "summary": drift.summary(),
                "report": drift.report(),
                "moved": [{"parameter": m.parameter, "tag": m.tag_id,
                           "old": m.old, "new": m.new} for m in drift.moved],
                "reindexed": [{"parameter": n, "old": o, "new": w}
                              for n, o, w in drift.reindexed],
                "resystemed": [{"parameter": n, "old": o, "new": w}
                               for n, o, w in drift.resystemed],
                "added": list(drift.added),
                "removed": list(drift.removed),
                "firstRun": drift.first_run,
                # Which question was asked: a parameter table has no stored
                # offsets, so the dialog has to say something else entirely.
                "table": drift.table,
            } if drift is not None else None,
        }

    def next_free_log_id(self) -> int:
        """The first log id no parameter has reserved yet.

        ``flatten()`` has already spread every structure's block over its
        leaves, so looking at the leaves covers structures too.  A leaf reserves
        one id per *value* - ``reserved_log_ids``, not its size in bytes: a
        ``float64_t[10]`` at 410 ends at 419 and the next free id is 420.

        The other sub lists count as well: the log ids of a project have to be
        unique across all of them, so an id that is free here but taken in
        another file is not free.
        """
        highest = 0
        for leaf in self.merged_model().flatten():
            log_id = leaf.log_id
            if isinstance(log_id, int) and not isinstance(log_id, bool):
                highest = max(highest, log_id + reserved_log_ids(leaf))
        return highest

    # -- what the front end renders -------------------------------------------
    def error_count(self) -> int:
        return sum(1 for item in self.validate()
                   if item["severity"] == Severity.ERROR.label)


def _refusal(diagnostics: DiagnosticCollector) -> str:
    """Why a build wrote nothing, in one line.

    The Problems panel has the full list; this is what a toast can show, so it
    names the first error and counts the rest instead of repeating them.
    """
    errors = [item for item in diagnostics.to_list()
              if item["severity"] == Severity.ERROR.label]
    if not errors:
        return "The model has errors - nothing was generated. See Problems."
    first = f"{errors[0]['code']}: {errors[0]['message']}"
    if len(errors) == 1:
        return first
    return f"{first} (and {len(errors) - 1} more error(s) - see Problems)"


#: The characters the dotted path syntax is built from.  A name containing one
#: of them cannot be addressed: "A.B" reads as the field B of a structure A, and
#: "A[0]" as an element of an array A.
_PATH_CHARACTERS = (PATH_SEPARATOR, "[", "]")


def _reject_path_characters(name: str) -> None:
    """Refuse a name that the path syntax could never address again.

    This is checked when the name is *set*, not when the model is validated,
    because by validation time it is already too late: the node is in the tree
    under a path that does not resolve, so the editor can no longer find it to
    edit, rename or even delete.  The only way out was to edit the XML by hand.
    """
    for character in _PATH_CHARACTERS:
        if character in name:
            raise ValueError(
                f"A name cannot contain '{character}'. Parameters are addressed "
                f"by their dotted path - Position.Home.Lat - so a name with "
                f"'{character}' in it could not be found again."
            )


def _default_resolution(type_name: Optional[str]) -> float:
    """The resolution a parameter of this type starts with.

    It comes from the type table, never from a constant here: 1 is right for
    the integers and wrong for the floats, where it would quantise every value
    to whole numbers.  An unknown type keeps 1, which is what the integers use.
    """
    value_type = resolve_value_type(type_name)
    return value_type.default_resolution if value_type is not None else 1


def _checked_address(raw: object) -> int:
    """An Address as the form sends it - or a refusal saying what it has to be."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 0
    number: object = raw
    try:
        if isinstance(raw, bool):
            raise ValueError(raw)
        if isinstance(raw, str):
            number = float(raw.strip())
        if isinstance(number, float):
            if not number.is_integer():
                raise ValueError(raw)
            number = int(number)
        if not isinstance(number, int) or not 0 <= number <= ADDRESS_MAX:
            raise ValueError(raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"The address is a whole number from 0 to {ADDRESS_MAX} - 0 means the "
            f"firmware places the parameter itself. '{raw}' is not one.") from None
    return number


def _default_tag(spec, defines: Defines):
    from pl_codegen.model.tags import TagKind
    if spec.kind is TagKind.BOOLEAN:
        return False
    if spec.kind is TagKind.ENUM and spec.defines_column:
        values = defines.get(spec.defines_column)
        return values[0] if values else None
    return None


def machine_roots() -> List[str]:
    """Every place browsing can START from: the drives of this machine.

    Walking up from a folder ends at the root of ITS drive - the parent of
    ``C:\\`` is ``C:\\`` - so a project on E: could not be reached by clicking
    at all, and "New project" had no box to type a path into either.  Whoever
    keeps their work on a second drive simply could not use the editor.

    So the dialogs are given the roots as well, and they are a list rather
    than one: on Windows a machine has as many as it has drives, and which
    letters exist is the machine's business, not something to guess from.  A
    drive that is there but not ready - an empty card reader - is left out,
    because listing it only produces an error when it is clicked.
    """
    if os.name != "nt":
        return ["/"]
    roots: List[str] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{letter}:\\")
        try:
            if root.is_dir():
                roots.append(str(root))
        except OSError:
            continue            # there, but not ready to be read
    return roots


def listing_target(raw: str, default: Path) -> Tuple[Path, str, str]:
    """Where a dialog lists, for whatever is in its path box right now.

    ``(folder to list, file to select or "", typed path that is not there or "")``.

    The box is read while it is typed into, not only on Enter, so it has to
    make sense of every half-typed state.  (Reported: a pasted path showed
    nothing until Enter, while a click showed a folder at once.)

      * nothing typed - the dialog's own starting folder;
      * a folder - that folder;
      * a file - the folder it is in, with the file selected;
      * a path that is not there (yet) - the nearest folder above it that is,
        and the typed path as *missing*: a new project may well be made in a
        folder that does not exist, and the dialog says it will be created;
      * a relative path - which would be relative to wherever the server
        happens to run - names nothing yet, so the starting folder stays.  It
        is not "missing" either: "it will be created" would be a promise the
        Create button then refuses, for want of a full path.

    Quotes around the path are dropped: Windows' "Copy as path" adds them.
    """
    text = str(raw or "").strip().strip('"').strip()
    if not text:
        return default, "", ""
    typed = Path(text).expanduser()
    if not typed.is_absolute():
        return default, "", ""
    try:
        if typed.is_file():
            return typed.parent, str(typed), ""
        if typed.is_dir():
            return typed, "", ""
    except OSError:
        pass
    here = typed
    while here != here.parent:
        here = here.parent
        try:
            if here.is_dir():
                return here, "", text
        except OSError:
            continue
    return here, "", text


def _as_written(declaration: str, like: str) -> str:
    """*declaration* with the element indices of *like* put back onto it.

    A rename made while an element was open has to come back as that element's
    new path, or the editor would go on pointing at something that is gone.
    """
    parts = declaration.split(PATH_SEPARATOR)
    written = like.split(PATH_SEPARATOR)
    out: List[str] = []
    for position, part in enumerate(parts):
        found = (Document._ELEMENT.fullmatch(written[position])
                 if position < len(written) else None)
        out.append(f"{part}[{found.group(2)}]" if found else part)
    return PATH_SEPARATOR.join(out)


def _list_of_a_types_file(path: Path) -> str:
    """The parameter list a types file belongs to, whichever name it carries."""
    name = Path(path).name
    for suffix in (TYPES_SUFFIX, LEGACY_TYPES_SUFFIX):
        if name.lower().endswith(suffix):
            return f"{name[:-len(suffix)]}.xml"
    return name


def _safe_stem(name: str) -> str:
    """Turn what somebody typed into a file name that cannot surprise them.

    Only letters, digits, ``_`` and ``-`` survive, so a name can never walk out
    of the project's folder with a ``..`` or a slash, and never collides with a
    shell or a path separator on any of the three platforms this runs on.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip()).strip("_-")
    return cleaned[:64]


def _same_file(left: Path, right: Path) -> bool:
    """Whether two paths name the same file, resolving both first.

    The configuration stores absolute paths and the browser sends back whatever
    it was given, so a plain ``==`` would call the same file two different
    files.
    """
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _unique_name(base: str, siblings: List[Parameter]) -> str:
    taken = {node.name for node in siblings}
    if base not in taken:
        return base
    index = 2
    while f"{base}{index}" in taken:
        index += 1
    return f"{base}{index}"


#: A name that is already a copy: the original's name, "_Copy", and maybe a number.
_COPY_NAME = re.compile(r"(?P<original>.+?)_Copy\d*")


def _copy_name(name: str, siblings: List[Parameter]) -> str:
    """What the copy of *name* is called: Airspeed_Copy, then Airspeed_Copy2, ...

    The way a file manager names a copy, written as a C identifier: no spaces
    and no brackets, so "_Copy" and a number.  A copy of a copy counts on from
    the same original - copying Airspeed_Copy gives the first free
    Airspeed_CopyN, never Airspeed_Copy_Copy.  (_unique_name appended its
    number to the whole name, so copying Airspeed2 gave Airspeed22.)  Free means
    free among *siblings*, the same scope as before.
    """
    copied = _COPY_NAME.fullmatch(name)
    original = copied.group("original") if copied else name
    taken = {node.name for node in siblings}
    candidate = f"{original}_Copy"
    number = 2
    while candidate in taken:
        candidate = f"{original}_Copy{number}"
        number += 1
    return candidate


def _clear_log_ids(node: Parameter) -> None:
    """A copy must not reuse the log ids of the original."""
    node.log_id = None
    for child in node.children:
        _clear_log_ids(child)
