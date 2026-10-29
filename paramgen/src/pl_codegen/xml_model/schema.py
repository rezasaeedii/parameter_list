"""Element and attribute names of the intermediate XML format.

The XML file is the *contract* between whatever produces a parameter list and
the code generator that consumes it: the graphical editor writes exactly this,
and the generator reads nothing else.  Keeping every tag name in one module is
what lets another front end be written without touching the generator at all.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0"

# -- elements ------------------------------------------------------------
ROOT = "ParameterListModel"
DEFINES = "Defines"
DEFINE_GROUP = "DefineGroup"
DEFINE_VALUE = "Value"
PARAMETERS = "Parameters"
PARAMETER = "Parameter"
FIELDS = "Fields"
#: The old, inline library of "structure types", when a type was a copy of a
#: structure's fields.  Types now live in their own file next to the list (see
#: xml_model/types_xml.py); this is still read so that a file written before
#: that change opens, and its contents are turned into real types.
STRUCT_TEMPLATES = "StructTemplates"

# -- the structure file, foo_types.xml ------------------------------
TYPES_ROOT = "ParameterListTypes"
STRUCT_TYPE = "StructType"
STRUCT_FIELD = "Field"
SOURCE = "Source"
LIMITS = "Limits"
TAGS = "Tags"
TAG = "Tag"
DESCRIPTION = "Description"
#: Descriptions and User Names that belong to one VALUE of an array rather than
#: to the whole declaration:
#: <Elements><Element at="3" userName="...">description</Element></Elements>.
ELEMENTS = "Elements"
ELEMENT = "Element"
SOURCE_FILES = "SourceFiles"
SOURCE_FILE = "SourceFile"

# -- attributes ----------------------------------------------------------
ATTR_SCHEMA_VERSION = "schemaVersion"
ATTR_GENERATOR = "generator"
ATTR_GENERATOR_VERSION = "generatorVersion"
ATTR_GENERATED_AT = "generatedAt"

ATTR_NAME = "name"
ATTR_KIND = "kind"
ATTR_ENABLE = "enable"
ATTR_USER_NAME = "userName"
#: What it was called while it was the "GS name" - still read, never written.
ATTR_OLD_USER_NAME = "gsName"
ATTR_TYPE = "type"
ATTR_DATA_TYPE = "valueType"
ATTR_ARRAY_SIZE = "size"
#: What the size was called before - still read, never written.
ATTR_OLD_ARRAY_SIZE = "arraySize"
ATTR_UNIT = "unit"
ATTR_DESCRIPTION = "description"
#: Which value an <Element> is about: the index of each array on the way to it,
#: "3" for Speed[3] and "1.5" for Wheels[1].Samples[5].
ATTR_AT = "at"
#: The log id.  It sits on <Parameter> and not in <Tags> because it is not a
#: tag: it has no offset area and it is a plain uint16_t in the descriptor.
ATTR_LOG_ID = "logId"
#: The parameter table's address column.  On every top-level <Parameter>, 0
#: included, in both formats - one list, one set of fields.
ATTR_ADDRESS = "address"

ATTR_DEFAULT = "default"
ATTR_MINIMUM = "minimum"
ATTR_MAXIMUM = "maximum"
ATTR_RESOLUTION = "resolution"

ATTR_ID = "id"
ATTR_VALUE = "value"
# <Tag> spells its kind with the same attribute name as <Parameter>; the
# constant above is the one to use.

ATTR_FILE = "file"
ATTR_SHEET = "sheet"
ATTR_ROW = "row"
ATTR_PATH = "path"
