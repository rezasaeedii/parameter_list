"""Did this run move anything that firmware already has in flash?

This is the quiet danger of a parameter-list generator, and the reason this
module exists.

Every reset-proof value lives at a byte offset the generator computed.  That
offset is *positional*: it is the sum of the sizes of everything that carries
the same tag and comes before it.  So inserting a parameter in the middle,
disabling one in the middle, moving one up or down, or changing the type or the
array size of one, does not only affect that parameter - **it shifts every
parameter after it**.

Nothing about that is visible in the diff of the source: the new code compiles,
the tests pass, and the firmware boots.  What happens instead is that a board
which was already in the field reads the value that used to be at that offset
and now belongs to a different parameter.  A speed limit reads back as a serial
number.

So after every run the merged model is written next to the generated code, and
the next run compares against it.  If a parameter that existed before now sits
at a different offset, the run says so - loudly, by name, with the old and the
new offset - and reminds whoever is looking that the boards in the field need a
migration, not just a flash.

It is a **warning and never an error**: moving things is completely legitimate,
and there are plenty of reasons to do it (a project that has not shipped, a tag
nobody stores, a deliberate re-layout).  The tool's job is to make sure nobody
does it *without noticing*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..model.parameter_list import ParameterList
from ..model.tags import TAG_REGISTRY
from .tag_offset import build_offset_map


@dataclass
class OffsetMove:
    """One parameter whose byte offset inside one tag's area changed."""

    parameter: str
    tag_id: str
    old: int
    new: int

    def __str__(self) -> str:
        return f"{self.parameter}  [{self.tag_id}]  {self.old} -> {self.new}"


@dataclass
class LayoutDrift:
    """What changed between the previous build and this one."""

    #: parameters that were not in the previous build
    added: List[str] = field(default_factory=list)
    #: parameters that were in it and are gone (deleted, disabled or renamed)
    removed: List[str] = field(default_factory=list)
    #: parameters that kept their name but changed position in the table
    reindexed: List[Tuple[str, int, int]] = field(default_factory=list)
    #: parameters that kept their name but changed byte offset inside a tag
    moved: List[OffsetMove] = field(default_factory=list)
    #: parameters that moved to a different sub-system (parameter tables only)
    resystemed: List[Tuple[str, str, str]] = field(default_factory=list)
    #: True when there was no previous build to compare against
    first_run: bool = False
    #: True when the project generates a parameter table.  A different format
    #: means a different question: that one has no stored byte offsets at all,
    #: and what can break a board is the parameter's NUMBER in its sub-system.
    table: bool = False

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.reindexed or self.moved
                    or self.resystemed)

    @property
    def breaks_stored_data(self) -> bool:
        """True when something a board in the field relies on has moved.

        Which thing that is depends on the format.  In smart data it is the
        byte offset of a reset-proof value.  In a parameter table there are no
        offsets: the ground station asks for a parameter *by its number in its
        sub-system*, so a changed index is the thing that makes an old board
        read the wrong parameter - which is exactly what the warning at the top
        of the generated file has always said.
        """
        if self.table:
            return bool(self.reindexed or self.resystemed)
        return bool(self.moved)

    def summary(self) -> str:
        """One line, for a log or a status bar."""
        if self.first_run:
            return "no previous build to compare against"
        if self.is_empty:
            return ("the table is unchanged" if self.table
                    else "the memory layout is unchanged")
        parts = []
        if self.moved:
            parts.append(f"{len(self.moved)} offset(s) MOVED")
        if self.reindexed:
            parts.append(f"{len(self.reindexed)} index(es) CHANGED"
                         if self.table else
                         f"{len(self.reindexed)} index(es) changed")
        if self.resystemed:
            parts.append(f"{len(self.resystemed)} changed sub-system")
        if self.added:
            parts.append(f"{len(self.added)} added")
        if self.removed:
            parts.append(f"{len(self.removed)} removed")
        return ", ".join(parts)

    def report(self, limit: int = 12) -> List[str]:
        """The full message, as lines, ready to print or to show in a dialog."""
        if self.first_run or self.is_empty:
            return []

        lines: List[str] = []
        if self.moved:
            lines.append("The stored position of these values CHANGED:")
            for move in self.moved[:limit]:
                lines.append(f"    {move}")
            if len(self.moved) > limit:
                lines.append(f"    ... and {len(self.moved) - limit} more")
            lines.append("")
            lines.append("A board that already has data in flash will read the wrong")
            lines.append("value at these offsets. Before flashing, decide what to do:")
            lines.append("  * erase the stored area, or")
            lines.append("  * migrate it, or")
            lines.append("  * put the new parameters at the END instead of in the middle.")

        if self.reindexed:
            if lines:
                lines.append("")
            lines.append("These parameters changed their NUMBER in their sub-system:"
                         if self.table else
                         "These values kept their offset but changed table index:")
            for name, old, new in self.reindexed[:limit]:
                lines.append(f"    {name}  {old} -> {new}")
            if len(self.reindexed) > limit:
                lines.append(f"    ... and {len(self.reindexed) - limit} more")
            if self.table:
                lines.append("")
                lines.append("The ground station and the firmware ask for a parameter BY")
                lines.append("that number, so anything not rebuilt with this file will read")
                lines.append("the wrong one. That is what the warning at the top of the")
                lines.append("generated file means: do not put a new item between old ones,")
                lines.append("add it at the END of its sub-system.")

        if self.resystemed:
            if lines:
                lines.append("")
            lines.append("These parameters are now in a different sub-system:")
            for name, old, new in self.resystemed[:limit]:
                lines.append(f"    {name}  {old} -> {new}")
            if len(self.resystemed) > limit:
                lines.append(f"    ... and {len(self.resystemed) - limit} more")

        for title, names in (("Added in this build:", self.added),
                             ("Gone from this build (deleted, disabled or renamed):",
                              self.removed)):
            if not names:
                continue
            if lines:
                lines.append("")
            lines.append(title)
            for name in names[:limit]:
                lines.append(f"    {name}")
            if len(names) > limit:
                lines.append(f"    ... and {len(names) - limit} more")
        return lines


def _numbered_per_system(model: ParameterList) -> Dict[str, Tuple[str, int]]:
    """Every value's sub-system and its number inside it.

    Exactly the numbering the generated table uses: grouped by the file the
    parameter was read from, restarting at zero in each.  It has to be the same
    numbering, or the check would report changes the file does not have - which
    is what happened when the lists' build order was compared instead: moving a
    list up the build changed every global position while no parameter's number
    in its own sub-system moved at all.
    """
    from ..codegen.files.param_table_h import system_of        # local: one way

    counters: Dict[str, int] = {}
    numbered: Dict[str, Tuple[str, int]] = {}
    for leaf in model.flatten():
        system = system_of(Path(str(leaf.source.file or "")))
        index = counters.get(system, 0)
        counters[system] = index + 1
        numbered[leaf.name] = (system, index)
    return numbered


def compare(previous: Optional[ParameterList], current: ParameterList,
            table: bool = False) -> LayoutDrift:
    """What moved between *previous* and *current*.

    Parameters are matched **by name**, which is the only identity they have.  A
    rename therefore shows up as one removal plus one addition; that is honest -
    the tool cannot tell a rename from a delete-and-add, and either way the
    reader has to look.

    *table* says the project generates a parameter table.  That format stores
    nothing by byte offset, so there are no offsets to compare; what matters
    there is each parameter's number **within its own sub-system**, which is
    what the ground station addresses it by.
    """
    if previous is None:
        return LayoutDrift(first_run=True, table=table)

    old_leaves = {leaf.name: index for index, leaf in enumerate(previous.flatten())}
    new_leaves = {leaf.name: index for index, leaf in enumerate(current.flatten())}

    drift = LayoutDrift(table=table)
    drift.added = [name for name in new_leaves if name not in old_leaves]
    drift.removed = [name for name in old_leaves if name not in new_leaves]

    shared = [name for name in new_leaves if name in old_leaves]

    if table:
        was = _numbered_per_system(previous)
        now = _numbered_per_system(current)
        for name in shared:
            old_system, old_index = was[name]
            new_system, new_index = now[name]
            if old_system != new_system:
                drift.resystemed.append((name, old_system, new_system))
            elif old_index != new_index:
                drift.reindexed.append((name, old_index, new_index))
    else:
        for name in shared:
            if old_leaves[name] != new_leaves[name]:
                drift.reindexed.append((name, old_leaves[name], new_leaves[name]))

        old_offsets = build_offset_map(previous)
        new_offsets = build_offset_map(current)
        for spec in TAG_REGISTRY:
            for name in shared:
                had = old_offsets.has_entry(spec.tag_id, name)
                has = new_offsets.has_entry(spec.tag_id, name)
                if not (had and has):
                    # the tag was switched on or off for this parameter; that is
                    # a change of intent, not a silent move, and the
                    # added/removed lists already tell the story
                    continue
                old = old_offsets.offset(spec.tag_id, name)
                new = new_offsets.offset(spec.tag_id, name)
                if old != new:
                    drift.moved.append(OffsetMove(name, spec.tag_id, old, new))

    # a value that moved is more useful read in table order than in tag order
    order = {name: index for index, name in enumerate(new_leaves)}
    drift.moved.sort(key=lambda move: (order.get(move.parameter, 0), move.tag_id))
    drift.reindexed.sort(key=lambda item: item[2])
    drift.resystemed.sort(key=lambda item: order.get(item[0], 0))
    drift.added.sort(key=lambda name: order.get(name, 0))
    return drift


def previous_build(path: Path) -> Optional[ParameterList]:
    """The model the last successful run wrote, or ``None`` on a first run.

    Anything unreadable counts as "no previous build": this is a courtesy check,
    and a corrupt copy of an old model must never stop somebody generating code.
    """
    if not path.is_file():
        return None
    try:
        from ..errors import DiagnosticCollector
        from ..xml_model.xml_reader import read_xml

        return read_xml(path, DiagnosticCollector())
    except Exception:                                    # noqa: BLE001 - see above
        return None
