"""Model -> XML.

The XML file is the stable intermediate representation: the code generator only
ever reads *this*, and never whatever wrote it.
Producing a file in this format is therefore the whole contract a front end has
to meet.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from .. import __tool_name__, __version__
from ..config import relative_to_root
from ..model.parameter import Parameter, ParameterKind
from ..model.parameter_list import ParameterList
from ..model.tags import TAG_REGISTRY
from . import schema as sch
from .types_xml import (legacy_types_file_for, types_file_for,
                        write_types)


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return repr(value)
    return str(value)


def _set(element: ET.Element, name: str, value: object) -> None:
    """Set an attribute unless the value is ``None``."""
    if value is not None:
        element.set(name, _text(value))


def model_to_element(model: ParameterList, *, emit_timestamp: bool = True,
                     home: Optional[Path] = None,
                     project_root: Optional[Path] = None) -> ET.Element:
    """Build the XML tree of *model*.

    *home* is the file the tree is about to be written to, and it is what
    makes a parameter list **portable**.  Without it every parameter carried
    the absolute path of the machine it was last saved on; move the project
    folder - which is the whole point of a project being a folder - and every
    diagnostic then named a file that was no longer there.

    *project_root* is given for a file that belongs to one project: the full
    parameter list the generator writes.  Every list it names - in
    ``<SourceFiles>`` and in each parameter's ``<Source>`` - is then named from
    the folder of pl_project.json (``parameter_lists/core.xml``), the way the
    banners of the generated C files name them.  It used to be the full path,
    so the file changed with every machine that built the project.
    """
    root = ET.Element(sch.ROOT)
    root.set(sch.ATTR_SCHEMA_VERSION, sch.SCHEMA_VERSION)
    root.set(sch.ATTR_GENERATOR, __tool_name__)
    root.set(sch.ATTR_GENERATOR_VERSION, __version__)
    if emit_timestamp:
        stamp = model.generated_at or datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds")
        root.set(sch.ATTR_GENERATED_AT, stamp)

    files_element = ET.SubElement(root, sch.SOURCE_FILES)
    for path in model.source_files:
        ET.SubElement(files_element, sch.SOURCE_FILE, {
            sch.ATTR_PATH: path if project_root is None
            else relative_to_root(path, project_root)})

    # <Defines> is deliberately not written any more.  The drop-down lists are
    # the machine's (paramgen/var/choices.json), so a copy in every parameter list
    # would be four copies of one thing, drifting apart the first time somebody
    # added a sub-system to one project.  Old files keep theirs until saved.

    parameters_element = ET.SubElement(root, sch.PARAMETERS)
    for parameter in model.parameters:
        parameters_element.append(_parameter_to_element(parameter, home,
                                                        project_root=project_root))

    return root


def _parameter_to_element(parameter: Parameter,
                          home: Optional[Path] = None,
                          top_level: bool = True,
                          project_root: Optional[Path] = None) -> ET.Element:
    element = ET.Element(sch.PARAMETER)
    _set(element, sch.ATTR_NAME, parameter.name)
    _set(element, sch.ATTR_KIND, parameter.kind.value)
    _set(element, sch.ATTR_ENABLE, parameter.enable)
    _set(element, sch.ATTR_USER_NAME, parameter.user_name)
    _set(element, sch.ATTR_TYPE, parameter.param_type)
    _set(element, sch.ATTR_DATA_TYPE, parameter.value_type_name)
    _set(element, sch.ATTR_ARRAY_SIZE, parameter.array_size)
    _set(element, sch.ATTR_UNIT, parameter.unit)
    # Not inside <Tags>: the log id is not a tag.
    _set(element, sch.ATTR_LOG_ID, parameter.log_id)
    # The parameter table's address column - on every top-level parameter, 0
    # included, whatever this project generates.  One list has the same fields
    # in both formats, so moving it between a smart-data and a parameter-table
    # project loses nothing and adds nothing.
    if top_level:
        _set(element, sch.ATTR_ADDRESS, int(parameter.address or 0))

    source = ET.SubElement(element, sch.SOURCE)
    _set(source, sch.ATTR_FILE, _source_file(parameter.source.file, home, project_root))
    _set(source, sch.ATTR_SHEET, parameter.source.sheet)
    _set(source, sch.ATTR_ROW, parameter.source.row)

    limits = ET.SubElement(element, sch.LIMITS)
    _set(limits, sch.ATTR_DEFAULT, parameter.default_value)
    _set(limits, sch.ATTR_MINIMUM, parameter.minimum)
    _set(limits, sch.ATTR_MAXIMUM, parameter.maximum)
    _set(limits, sch.ATTR_RESOLUTION, parameter.resolution)

    tags = ET.SubElement(element, sch.TAGS)
    for spec in TAG_REGISTRY:
        value = parameter.tags.get(spec.tag_id)
        if value is None:
            continue
        tag_element = ET.SubElement(tags, sch.TAG)
        tag_element.set(sch.ATTR_ID, spec.tag_id)
        tag_element.set(sch.ATTR_KIND, spec.kind.value)
        tag_element.set(sch.ATTR_VALUE, _text(value))

    if parameter.description:
        ET.SubElement(element, sch.DESCRIPTION).text = parameter.description

    # What ONE value says instead - its description, its User Name or both, as
    # <Element at="3" userName="...">description</Element>.  Written only where
    # somebody typed something, so a list whose elements all mean the same
    # thing looks exactly as it did.
    overridden = set(parameter.element_descriptions) | set(parameter.element_user_names)
    if overridden:
        elements = ET.SubElement(element, sch.ELEMENTS)
        for at in sorted(overridden, key=_element_order):
            entry = ET.SubElement(elements, sch.ELEMENT, {sch.ATTR_AT: at})
            if at in parameter.element_user_names:
                entry.set(sch.ATTR_USER_NAME, parameter.element_user_names[at])
            if at in parameter.element_descriptions:
                entry.text = parameter.element_descriptions[at]

    if parameter.kind is ParameterKind.STRUCT:
        fields = ET.SubElement(element, sch.FIELDS)
        for child in parameter.children:
            fields.append(_parameter_to_element(child, home, top_level=False,
                                                project_root=project_root))

    return element


def _element_order(at: str) -> Tuple[int, ...]:
    """Element paths sort by their numbers: "1.10" comes after "1.9", not before."""
    try:
        return tuple(int(part) for part in at.split("."))
    except ValueError:
        return ()


def _source_file(file: Optional[str], home: Optional[Path],
                 project_root: Optional[Path] = None) -> Optional[str]:
    """What to write in ``<Source file="...">``, if anything.

    Nothing at all when the parameter comes from the very file being written,
    which is the ordinary case: the reader already falls back to the file it
    is reading, so the attribute would only repeat it - in absolute form, and
    wrongly as soon as the folder moved.

    A parameter that really did come from somewhere else keeps its origin, as
    a path relative to the file being written when that is possible.  A list
    on another drive keeps its absolute path, because there is no relative
    path to write.  In a project's own file (*project_root* given) the origin
    is named from the project root instead - which is every parameter of the
    full parameter list, since none of them comes from that file.
    """
    if not file or home is None:
        return file

    try:
        source = Path(file).expanduser()
        if not source.is_absolute():
            source = (home.parent if project_root is None else project_root) / source
        source = source.resolve()
        if source == home.resolve():
            return None
        if project_root is not None:
            return relative_to_root(source, project_root)
        return str(source.relative_to(home.resolve().parent))
    except (OSError, ValueError):
        # ValueError: not under the same folder - keep what we were given.
        return file


def write_xml(model: ParameterList, path: Path, *, emit_timestamp: bool = True,
              project_root: Optional[Path] = None) -> Path:
    """Write *model* to *path*, and its structure types beside it.

    The two are written together on purpose.  A list whose types file was left
    behind is a list whose parameters have no shape, so there is no moment at
    which only one of them is on disk.

    *project_root*: see :func:`model_to_element`.
    """
    path = Path(path)
    root = model_to_element(model, emit_timestamp=emit_timestamp, home=path,
                            project_root=project_root)
    _indent(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    # Every type of THIS list - the ones its parameters use and the ones
    # declared while it was open.  Writing only the used ones threw away a type
    # somebody had just declared and had not placed yet, which is the shortest
    # possible route from "I made a struct" to "where did it go?".
    write_types(model.struct_types, types_file_for(path), emit_timestamp=emit_timestamp)
    # The types file used to be called "<list>_structures.xml".  The types have
    # just been written under the new name, so the old file is not a second
    # opinion - it is a copy nothing reads and somebody would edit.
    older = legacy_types_file_for(path)
    if older.is_file():
        older.unlink()
    return path


def _indent(element: ET.Element, level: int = 0, indent: str = "  ") -> None:
    """``ET.indent`` replacement that also works on Python 3.8."""
    padding = "\n" + level * indent
    if len(element):
        if not (element.text or "").strip():
            element.text = padding + indent
        for child in element:
            _indent(child, level + 1, indent)
        last: Optional[ET.Element] = element[-1]
        if last is not None and not (last.tail or "").strip():
            last.tail = padding
    if level and not (element.tail or "").strip():
        element.tail = padding
