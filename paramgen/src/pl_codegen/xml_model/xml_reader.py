"""XML -> model.

This is the only entry point the code generator uses, so the generator is
completely independent of the editor.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from ..errors import CodeGeneratorError, DiagnosticCollector, SourceLocation
from ..choices import load_choices, seed_from
from ..model.defines import Defines
from ..model.parameter import Parameter, ParameterKind
from ..model.struct_migration import adopt_types
from ..model.struct_sync import apply_types
from ..model.parameter_list import PATH_SEPARATOR
from ..model.parameter_list import ParameterList
from ..model.tags import TAGS_BY_ID, TagKind
from ..model.types import resolve_value_type
from . import schema as sch
from .types_xml import existing_types_file_for, read_types


#: "3", "1.5" - the index of each array on the way to one value.
_ELEMENT_PATH = re.compile(r"\d+(?:\.\d+)*")


def read_xml(path: Path, diagnostics: DiagnosticCollector) -> ParameterList:
    """Parse *path* and rebuild the parameter list model."""
    if not path.is_file():
        raise CodeGeneratorError(f"The parameter sublist '{path}' does not exist.")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        # str(exc) already carries "line N, column M", which is the whole
        # answer for a hand-edited file - so it is quoted rather than
        # summarised, and the sentence after it says what to do with it.
        raise CodeGeneratorError(
            f"'{path}' is not a valid XML file: {exc}.  Open it in a text editor "
            f"at that line; the editor cannot load a file it cannot parse.") from exc

    if root.tag != sch.ROOT:
        raise CodeGeneratorError(
            f"'{path}' is not a parameter sublist (root element is '{root.tag}', "
            f"expected '{sch.ROOT}').")

    version = root.get(sch.ATTR_SCHEMA_VERSION, "")
    if version and version.split(".")[0] != sch.SCHEMA_VERSION.split(".")[0]:
        diagnostics.warning(
            "XML001",
            f"XML schema version '{version}' differs from the version supported by this tool "
            f"('{sch.SCHEMA_VERSION}').", SourceLocation(file=str(path)))

    model = ParameterList()
    model.generator_version = root.get(sch.ATTR_GENERATOR_VERSION, "")
    model.generated_at = root.get(sch.ATTR_GENERATED_AT, "")

    files_element = root.find(sch.SOURCE_FILES)
    if files_element is not None:
        model.source_files = [element.get(sch.ATTR_PATH, "")
                              for element in files_element.findall(sch.SOURCE_FILE)]

    # The drop-down lists belong to the machine, not to this file: they are
    # the company's vocabulary and every project on the machine uses the same
    # one.  A file written before that still has its own <Defines>, which is
    # read here only to hand it over the first time.
    seed_from(_read_defines(root))
    model.defines = load_choices()

    # The structure types this list uses, from foo_types.xml next to it.
    model.struct_types = read_types(existing_types_file_for(path), diagnostics)

    # A library written the old way - types inlined in the list file, as copies
    # of a structure's fields.  It is read so that a file from before types had
    # a file of their own still opens, and turned into real types.
    legacy: List[Parameter] = []
    templates_element = root.find(sch.STRUCT_TEMPLATES)
    if templates_element is not None:
        for element in templates_element.findall(sch.PARAMETER):
            template = _read_parameter(element, path, diagnostics)
            if template is not None:
                legacy.append(_as_template(template))

    parameters_element = root.find(sch.PARAMETERS)
    if parameters_element is None:
        diagnostics.error(
            "XML002", f"'{sch.PARAMETERS}' element is missing.",
            SourceLocation(file=str(path)),
            hint=f"The file needs a <{sch.PARAMETERS}> element, even an empty one; "
                 f"it is what holds the parameters.")
        return model

    for element in parameters_element.findall(sch.PARAMETER):
        parameter = _read_parameter(element, path, diagnostics)
        if parameter is not None:
            model.add(parameter)

    # Everything is in now, so the structures can be tied to their types: the
    # ones that name a type get their shape from it, and the ones written
    # before types existed have a type made out of the shape they already have.
    adopt_types(model, legacy, path, diagnostics)
    apply_types(model.parameters, model.struct_types)
    return model


def _read_defines(root: ET.Element) -> Defines:
    defines = Defines()
    defines_element = root.find(sch.DEFINES)
    if defines_element is None:
        return defines
    for group in defines_element.findall(sch.DEFINE_GROUP):
        column = group.get(sch.ATTR_NAME, "")
        for value_element in group.findall(sch.DEFINE_VALUE):
            value = value_element.get(sch.ATTR_VALUE)
            if column and value:
                defines.add(column, value)
    return defines


def _read_parameter(element: ET.Element, path: Path,
                    diagnostics: DiagnosticCollector,
                    prefix: str = "") -> Optional[Parameter]:
    """Read one <Parameter>.  *prefix* is the dotted path of its parent.

    The prefix is what lets every diagnostic name the parameter it is about.
    Without it the reader could only say which FILE was wrong, which in a list
    of four hundred values is not an answer to "where?".
    """
    name = element.get(sch.ATTR_NAME)
    if not name:
        where = f"inside '{prefix}'" if prefix else "at the top level"
        diagnostics.error(
            "XML010", f"A <Parameter> element {where} has no 'name' attribute.",
            SourceLocation(file=str(path), parameter=prefix or None),
            hint="Every parameter needs a name; it becomes a C identifier.")
        return None

    dotted = f"{prefix}{PATH_SEPARATOR}{name}" if prefix else name

    parameter = Parameter(name=name)
    raw_kind = (element.get(sch.ATTR_KIND) or ParameterKind.PRIMITIVE.value).strip().lower()
    try:
        parameter.kind = ParameterKind(raw_kind)
    except ValueError:
        diagnostics.warning(
            "XML016",
            f"Unknown parameter kind '{raw_kind}'; 'primitive' is assumed.",
            SourceLocation(file=str(path), parameter=dotted),
            hint="A parameter is either 'primitive' (it holds a value) or "
                 "'struct' (it holds fields).")
        parameter.kind = ParameterKind.PRIMITIVE
    parameter.enable = _to_bool(element.get(sch.ATTR_ENABLE), True)
    # 'userName'; a list written while it was called the GS name says
    # 'gsName' and reads the same - the next save writes userName again.
    user_name = element.get(sch.ATTR_USER_NAME)
    parameter.user_name = (user_name if user_name is not None
                           else element.get(sch.ATTR_OLD_USER_NAME))
    parameter.param_type = element.get(sch.ATTR_TYPE)
    parameter.value_type_name = element.get(sch.ATTR_DATA_TYPE)
    parameter.unit = element.get(sch.ATTR_UNIT)
    # 'size'; a list written before the rename says 'arraySize' and reads
    # the same - the next save writes 'size'.
    size = element.get(sch.ATTR_ARRAY_SIZE)
    parameter.array_size = _to_int(
        size if size is not None else element.get(sch.ATTR_OLD_ARRAY_SIZE), 1)
    parameter.log_id = _to_optional_int(element.get(sch.ATTR_LOG_ID))
    raw_address = element.get(sch.ATTR_ADDRESS)
    address = _to_optional_int(raw_address)
    if address is None and raw_address is not None and raw_address.strip():
        diagnostics.warning(
            "XML017",
            f"'{dotted}' has address '{raw_address}', which is not a whole number; "
            f"0 is used.",
            SourceLocation(file=str(path), parameter=dotted),
            hint="The address is the parameter table's address column: a whole "
                 "number, and 0 when the firmware should place the parameter itself.")
    parameter.address = address if address is not None else 0

    source_element = element.find(sch.SOURCE)
    if source_element is not None:
        # The editor writes an empty <Source /> - it has no origin to record
        # beyond the file itself.  Falling back to *path* rather than to None
        # is what lets a diagnostic say which parameter list a duplicate name
        # came from, which is the only useful thing to say when a project is
        # several lists merged into one.
        parameter.source = SourceLocation(
            file=source_element.get(sch.ATTR_FILE) or str(path),
            sheet=source_element.get(sch.ATTR_SHEET),
            row=_to_optional_int(source_element.get(sch.ATTR_ROW)),
            parameter=dotted)
    else:
        parameter.source = SourceLocation(file=str(path), parameter=dotted)

    value_type = resolve_value_type(parameter.value_type_name)
    is_float = bool(value_type and value_type.is_float)
    is_bool = bool(value_type and value_type.is_bool)

    limits = element.find(sch.LIMITS)
    if limits is not None:
        # Only the default value of a bool_t row is a boolean; its minimum,
        # maximum and resolution are meaningless for that type and are kept as
        # plain numbers, the way the editor keeps them.  Reading them
        # back as booleans would make the same model generate different files
        # depending on where it came from, and would turn "Minimum = 3" into an
        # unhelpful "not a valid boolean" instead of "a boolean has no minimum".
        def limit(attribute: str, label: str, as_bool: bool = False):
            return _to_number(limits.get(attribute), is_float, as_bool,
                              label=label, parameter=parameter,
                              type_name=parameter.value_type_name,
                              diagnostics=diagnostics)

        parameter.default_value = limit(sch.ATTR_DEFAULT, "DefaultValue", is_bool)
        parameter.minimum = limit(sch.ATTR_MINIMUM, "Minimum")
        parameter.maximum = limit(sch.ATTR_MAXIMUM, "Maximum")
        parameter.resolution = limit(sch.ATTR_RESOLUTION, "Resolution")

    tags_element = element.find(sch.TAGS)
    if tags_element is not None:
        for tag_element in tags_element.findall(sch.TAG):
            tag_id = tag_element.get(sch.ATTR_ID, "")
            spec = TAGS_BY_ID.get(tag_id)
            raw = tag_element.get(sch.ATTR_VALUE)
            if spec is None:
                diagnostics.warning("XML011", f"Unknown tag '{tag_id}' is ignored.",
                                    parameter.source)
                continue
            parameter.tags[tag_id] = convert_tag(spec.kind, raw)

    description_element = element.find(sch.DESCRIPTION)
    if description_element is not None and description_element.text:
        parameter.description = description_element.text.strip()

    # What one value of an array says instead of the declaration's description.
    elements_element = element.find(sch.ELEMENTS)
    if elements_element is not None:
        for entry in elements_element.findall(sch.ELEMENT):
            at = (entry.get(sch.ATTR_AT) or "").strip()
            if not _ELEMENT_PATH.fullmatch(at):
                diagnostics.warning(
                    "XML018",
                    f"'{dotted}' has a description for element '{at}', which is not "
                    f"an element path; it is ignored.",
                    SourceLocation(file=str(path), parameter=dotted),
                    hint="An element path is the index of every array on the way to "
                         "the value: '3' for Speed[3], '1.5' for "
                         "Wheels[1].Samples[5].")
                continue
            # An empty one says nothing, which is exactly what having none says:
            # the value falls back to the parameter's description.  Kept out of
            # the model so that reading a file and writing it back gives the
            # same file - the editor never writes an empty one either.
            text = (entry.text or "").strip()
            if text:
                parameter.element_descriptions[at] = text
            # The value's own User Name rides on the same element, as an
            # attribute; a file written before values had one has none.
            named = (entry.get(sch.ATTR_USER_NAME) or "").strip()
            if named:
                parameter.element_user_names[at] = named

    fields_element = element.find(sch.FIELDS)
    if fields_element is not None:
        for child_element in fields_element.findall(sch.PARAMETER):
            child = _read_parameter(child_element, path, diagnostics, dotted)
            if child is not None:
                _drop_inherited(child, parameter.name, diagnostics)
                parameter.children.append(child)

    return parameter


def _as_template(template: Parameter) -> Parameter:
    """Force a node read from the library into the shape a template has.

    A template is a *type*, not a parameter: it describes fields and nothing
    else.  Tags, the type, the array size and the log id belong to the
    parameter that will be made from it, so they are cleared here rather than
    trusted from the file - a hand-edited library then cannot smuggle a type
    into every copy.
    """
    template.kind = ParameterKind.STRUCT
    template.enable = True
    template.tags = {}
    template.param_type = None
    template.array_size = 1
    template.log_id = None
    return template


def _drop_inherited(field: Parameter, structure: str,
                    diagnostics: DiagnosticCollector) -> None:
    """Remove tags, the type and the log id from a field.

    All three belong to the top level entry.  A hand-edited file may still
    carry them on a field; they are dropped here with a warning rather than
    silently kept, because keeping them would mean the file no longer says what
    the generated code does - the log id in particular is handed out per value
    by ``_distribute_log_ids``, so a number on a field would never be used.
    """
    own_tags = sorted(key for key, value in field.tags.items() if value is not None)
    if own_tags:
        diagnostics.warning(
            "XML013",
            f"Field '{field.name}' of structure '{structure}' carried the tag(s) "
            f"{', '.join(own_tags)}; they were dropped.",
            field.source,
            hint=f"Tags belong to '{structure}'. Check them there and save the file "
                 f"again to remove this warning.")
        field.tags = {}

    if field.param_type:
        diagnostics.warning(
            "XML014",
            f"Field '{field.name}' of structure '{structure}' carried the type "
            f"'{field.param_type}'; it was dropped.",
            field.source,
            hint=f"The type belongs to '{structure}'.")
        field.param_type = None

    if field.log_id is not None:
        diagnostics.warning(
            "XML015",
            f"Field '{field.name}' of structure '{structure}' carried the log id "
            f"{field.log_id}; it was dropped.",
            field.source,
            hint=f"The log id belongs to '{structure}': it is the first id of the "
                 f"block, and every value inside takes one id out of it in order.")
        field.log_id = None


def convert_tag(kind: TagKind, raw: Optional[str]):
    """A tag's text as the model holds it: a free tag that is a number becomes one.

    Public because the editor stores a typed tag through it too.  A free tag
    typed as '5' stayed the text '5' there, which the free-tag rule (numbers or
    C identifiers) refused - while the build, reading the file back, got the
    number 5 and passed.
    """
    if raw is None:
        return None
    if kind is TagKind.BOOLEAN:
        return _to_bool(raw, False)
    if kind is TagKind.FREE:
        # An emptied box is no value.  It used to stay '' - in the model and as
        # value="" in the file - and the free-tag rule then refused it as
        # "neither a number nor a C identifier", stopping the build over a tag
        # nobody had set.  (Asked for.)
        if not str(raw).strip():
            return None
        number = _to_optional_int(raw)
        return number if number is not None else raw
    return raw


def _to_bool(raw: Optional[str], default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")


def _to_int(raw: Optional[str], default: int) -> int:
    value = _to_optional_int(raw)
    return default if value is None else value


def _to_optional_int(raw: Optional[str]) -> Optional[int]:
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(str(raw).strip(), 0)
    except ValueError:
        try:
            number = float(raw)
        except ValueError:
            return None
        return int(number) if number.is_integer() else None


def _to_number(raw: Optional[str], is_float: bool, is_bool: bool, *,
               label: str = "", parameter=None, type_name: Optional[str] = None,
               diagnostics: Optional[DiagnosticCollector] = None):
    """One numeric attribute of a ``<Limits>`` element.

    Anything that cannot be read is *reported*, never dropped.  Returning None
    in silence would be the dangerous behaviour: an unreadable Maximum simply
    looks like an empty cell, an empty Minimum and Maximum mean "the whole
    range of the type", and the generated firmware would then accept values the
    model was written to forbid - with nothing anywhere saying so.
    """
    if raw is None or not str(raw).strip():
        return None
    if is_bool:
        return _to_bool(raw, False)

    text = str(raw).strip()
    if is_float:
        try:
            return float(text)
        except ValueError:
            _report_bad_number(label, text, type_name, parameter, diagnostics,
                               "is not a number")
            return None

    value = _to_optional_int(text)
    if value is not None:
        return value

    # A number that is simply not whole is **kept**, not dropped.  Dropping it
    # left the editor showing an empty cell for a value the file plainly holds,
    # so the reader was told to "correct the value" with nothing on screen to
    # correct - and saving the file then erased what had been typed.  Keeping
    # it lets the row show 1.2, and RNG017 says in one line what the generated
    # code would really do with it.
    try:
        return float(text)
    except ValueError:
        _report_bad_number(label, text, type_name, parameter, diagnostics,
                           "is not a number")
        return None


def _report_bad_number(label: str, text: str, type_name: Optional[str], parameter,
                       diagnostics: Optional[DiagnosticCollector], reason: str) -> None:
    if diagnostics is None or parameter is None:
        return
    diagnostics.error(
        "XML012",
        f"'{label}' is '{text}' in the XML model, which {reason}.",
        parameter.source,
        hint="Correct the value in the editor, or fix it by hand in the XML file.")
