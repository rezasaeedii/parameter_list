"""Reading and writing the structure types that sit next to a parameter list.

Every parameter list ``foo.xml`` has a ``foo_types.xml`` beside it holding the
structure types that list uses.  The two travel together: hand both to another
project and its parameters keep their shape, which is the whole reason the
types are not buried inside the list file.

The project keeps an index of every type it knows next to the model its last
build was made from, written on every save.  That index is *derived* - the truth
is always the file next to the list - so deleting it costs nothing but the next
save rebuilds it.

The format is deliberately small::

    <ParameterListTypes schemaVersion="1.0" ...>
      <StructType name="Position">
        <Field name="Lat" valueType="float64_t" size="1" />
        <Field name="Lon" valueType="float64_t" size="1" />
        <Field name="Spare" valueType="uint8_t" enable="false" />
      </StructType>
    </ParameterListTypes>

There is nothing here about limits, tags, log ids, units or descriptions,
because a type has none of those - see :mod:`pl_codegen.model.struct_type`.  An
older file that still carries a ``description`` or a ``unit`` is read without
them, and the next save writes it clean.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from .. import __tool_name__, __version__
from ..errors import CodeGeneratorError, DiagnosticCollector, SourceLocation
from ..model.enum_type import EnumType, EnumValue
from ..model.struct_type import StructField, StructType, StructTypeLibrary
from . import schema as sch

#: ``power.xml`` -> ``power_types.xml``.  Next to the list and named after
#: it, so the two sort together in a folder listing and neither can be mistaken
#: for the other.  One word, no dot: ``power.types.xml`` looked like a parameter
#: list called "power" with an odd extension, and every tool that sorts on the
#: extension put it somewhere surprising.
TYPES_SUFFIX = "_types.xml"

#: What that file was called before.  A list whose types are still in the older
#: file reads them from there; the next save writes the new name and takes the
#: old file away, so there is never a second copy to wonder about.
LEGACY_TYPES_SUFFIX = "_structures.xml"


def is_types_file(path: Path) -> bool:
    """Whether *path* is a structures file and not a parameter list.

    The two live in the same folder and share an extension, so everything that
    offers "the .xml files here" has to ask.  Without this the Open dialog
    listed ``navigation.types`` as a parameter list, and opening it failed with
    a message about a root element - which is true, and no help at all.
    """
    name = str(path).lower()
    return name.endswith(TYPES_SUFFIX) or name.endswith(LEGACY_TYPES_SUFFIX)


def types_file_for(list_file: Path) -> Path:
    """The types file that belongs beside *list_file* - the name it is WRITTEN as."""
    list_file = Path(list_file)
    return list_file.with_name(list_file.stem + TYPES_SUFFIX)


def legacy_types_file_for(list_file: Path) -> Path:
    """The same file under its older name, ``<list>_structures.xml``."""
    list_file = Path(list_file)
    return list_file.with_name(list_file.stem + LEGACY_TYPES_SUFFIX)


def existing_types_file_for(list_file: Path) -> Path:
    """The types file to READ beside *list_file*: the new name, or the old one.

    A list nobody has saved since the rename still has its types in
    ``<list>_structures.xml``, and they are its parameters' shape - losing them
    would leave every structure in that list without fields.
    """
    current = types_file_for(list_file)
    older = legacy_types_file_for(list_file)
    return older if not current.is_file() and older.is_file() else current


def _size_of(element: ET.Element) -> Optional[str]:
    """A field's size, under the name it carries.

    'size' now; a types file written before the rename says 'arraySize'
    and reads the same.
    """
    size = element.get(sch.ATTR_ARRAY_SIZE)
    return size if size is not None else element.get(sch.ATTR_OLD_ARRAY_SIZE)


def read_types(path: Path, diagnostics: Optional[DiagnosticCollector] = None
               ) -> StructTypeLibrary:
    """Read one types file.  A file that is not there is an empty library.

    Missing is not an error: a list written before structure types existed
    simply has none, and a list with no structures in it never grows one.
    """
    path = Path(path)
    if not path.is_file():
        return StructTypeLibrary()

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise CodeGeneratorError(f"'{path}' is not a valid XML file: {exc}") from exc

    if root.tag != sch.TYPES_ROOT:
        raise CodeGeneratorError(
            f"'{path}' is not a structure-type file (root element is '{root.tag}', "
            f"expected '{sch.TYPES_ROOT}').")

    library = StructTypeLibrary()
    for element in root.findall(sch.STRUCT_TYPE):
        name = (element.get(sch.ATTR_NAME) or "").strip()
        if not name:
            if diagnostics is not None:
                diagnostics.error(
                    "TYP010", "A <StructType> element has no 'name' attribute.",
                    SourceLocation(file=str(path)),
                    hint="A structure type is identified by its name; it becomes "
                         "the C typedef.")
            continue

        struct_type = StructType(name=name)
        for member_element in element.findall(sch.STRUCT_FIELD):
            member_name = (member_element.get(sch.ATTR_NAME) or "").strip()
            if not member_name:
                if diagnostics is not None:
                    diagnostics.error(
                        "TYP011", f"A field of '{name}' has no 'name' attribute.",
                        SourceLocation(file=str(path), parameter=name),
                        hint="Every field needs a name; it becomes a C member.")
                continue
            struct_type.fields.append(StructField(
                name=member_name,
                value_type_name=(member_element.get(sch.ATTR_DATA_TYPE) or "").strip(),
                enum_type_name=(member_element.get(sch.ATTR_ENUM_TYPE) or "").strip(),
                array_size=_to_int(_size_of(member_element), 1),
                enable=_to_bool(member_element.get(sch.ATTR_ENABLE), True)))

        if struct_type.name in library:
            if diagnostics is not None:
                diagnostics.error(
                    "TYP012",
                    f"'{struct_type.name}' is declared twice in this file.",
                    SourceLocation(file=str(path), parameter=struct_type.name),
                    hint="A name identifies one structure type. Rename one of them, "
                         "or delete the copy.")
            continue
        library.put(struct_type)

    for element in root.findall(sch.ENUM_TYPE):
        enum_type = _read_enum(element, path, diagnostics)
        if enum_type is None:
            continue
        if library.get_enum(enum_type.name) is not None:
            if diagnostics is not None:
                diagnostics.error(
                    "ENUM012", f"Enumeration '{enum_type.name}' is declared twice in this file.",
                    SourceLocation(file=str(path), parameter=enum_type.name),
                    hint="A name identifies one enumeration. Rename one of them, or "
                         "delete the copy.")
            continue
        library.put_enum(enum_type)
    return library


def _read_enum(element: ET.Element, path: Path,
               diagnostics: Optional[DiagnosticCollector]) -> Optional[EnumType]:
    """One <EnumType>; a value whose number cannot be read is reported and left out."""
    name = (element.get(sch.ATTR_NAME) or "").strip()
    if not name:
        if diagnostics is not None:
            diagnostics.error(
                "ENUM012", "An <EnumType> element has no 'name' attribute.",
                SourceLocation(file=str(path)),
                hint="An enumeration is identified by its name; it becomes the C typedef.")
        return None
    enum_type = EnumType(name=name,
                         base_type_name=(element.get(sch.ATTR_BASE_TYPE) or "").strip())
    for value_element in element.findall(sch.ENUM_VALUE):
        value_name = (value_element.get(sch.ATTR_NAME) or "").strip()
        raw = (value_element.get(sch.ATTR_VALUE) or "").strip()
        try:
            number = int(raw, 0)
        except ValueError:
            number = None
        if not value_name or number is None:
            if diagnostics is not None:
                diagnostics.error(
                    "ENUM012",
                    f"A value of enumeration '{name}' has no name or no whole number "
                    f"(name '{value_name}', value '{raw}').",
                    SourceLocation(file=str(path), parameter=name),
                    hint="Every value needs a name and a whole number.")
            continue
        enum_type.values.append(EnumValue(name=value_name, value=number))
    return enum_type


def types_to_element(library: StructTypeLibrary) -> ET.Element:
    """The ``<ParameterListTypes>`` tree of *library*, exactly as it is written.

    Apart from :func:`write_types` so that the editor can ask what saving would
    write without writing it - which is how it knows whether a list has unsaved
    changes.
    """
    root = ET.Element(sch.TYPES_ROOT)
    root.set(sch.ATTR_SCHEMA_VERSION, sch.SCHEMA_VERSION)
    root.set(sch.ATTR_GENERATOR, __tool_name__)
    root.set(sch.ATTR_GENERATOR_VERSION, __version__)

    for struct_type in library.all():
        element = ET.SubElement(root, sch.STRUCT_TYPE, {sch.ATTR_NAME: struct_type.name})
        for member in struct_type.fields:
            attributes = {sch.ATTR_NAME: member.name,
                          sch.ATTR_DATA_TYPE: member.value_type_name or ""}
            if member.enum_type_name:
                attributes[sch.ATTR_ENUM_TYPE] = member.enum_type_name
            if member.array_size and member.array_size != 1:
                attributes[sch.ATTR_ARRAY_SIZE] = str(member.array_size)
            if not member.enable:
                attributes[sch.ATTR_ENABLE] = "false"
            ET.SubElement(element, sch.STRUCT_FIELD, attributes)
    for enum_type in library.enums():
        element = ET.SubElement(root, sch.ENUM_TYPE, {
            sch.ATTR_NAME: enum_type.name, sch.ATTR_BASE_TYPE: enum_type.base_type_name})
        for item in enum_type.values:
            ET.SubElement(element, sch.ENUM_VALUE,
                          {sch.ATTR_NAME: item.name, sch.ATTR_VALUE: str(item.value)})
    return root


def write_types(library: StructTypeLibrary, path: Path, *,
                emit_timestamp: bool = True) -> Optional[Path]:
    """Write *library* to *path*.

    An empty library removes the file rather than leaving an empty one behind:
    a list with no structures should look like a list with no structures, and a
    stale file full of types nobody uses is exactly the thing that later gets
    copied somewhere and causes a name clash.
    """
    path = Path(path)
    if not len(library):
        if path.is_file():
            path.unlink()
        return None

    root = types_to_element(library)
    _indent(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def _to_bool(raw: Optional[str], default: bool) -> bool:
    """``true`` / ``false`` in any case; anything else is *default*."""
    if raw is None:
        return default
    text = raw.strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return default


def _to_int(raw: Optional[str], default: int) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _indent(element: ET.Element, level: int = 0, indent: str = "  ") -> None:
    padding = "\n" + level * indent
    if len(element):
        if not (element.text or "").strip():
            element.text = padding + indent
        for child in element:
            _indent(child, level + 1, indent)
        if not (element.tail or "").strip():
            element.tail = padding
        if not (element[-1].tail or "").strip():
            element[-1].tail = padding
    elif level and not (element.tail or "").strip():
        element.tail = padding
