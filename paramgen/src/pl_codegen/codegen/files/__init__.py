"""One class per generated file.

Each module here holds a ``FileBuilder`` whose ``generate()`` writes the whole
file from top to bottom with ``text += ...``.  Reading that one method tells you
exactly what the generated file will look like.

Adding a new output file: write a module here and list its class in
:data:`SMART_DATA_BUILDERS`.

There are two sets of them, because there are two output formats.  Which set a
run uses is the project's to say, and :func:`builders_for` is where that is
decided - once, from the configuration, rather than in every caller.  The tags
a format writes the same into every parameter are decided here too:
:func:`fixed_tags`.
"""

from __future__ import annotations

from typing import Dict, List, Type

from ...config import Config, FORMAT_PARAM_TABLE
from ...model.parameter_list import ParameterList
from .file_builder import FileBuilder
from .parameter_list_c import ParameterListSource
from .parameter_list_defines_h import ParameterListDefinesHeader
from .parameter_list_h import ParameterListHeader
from .parameter_list_table_h import ParameterListTableHeader
from .param_offsets_h import ParamOffsetsHeader
from .param_table_h import ParamTableHeader
from .parameter_types_h import ParameterTypesHeader
from .smart_data_c import SmartDataSource
from .smart_data_h import SmartDataHeader
from .system_names_h import SystemNamesHeader

#: The ``smart_data`` format, generated in this order.
SMART_DATA_BUILDERS: List[Type[FileBuilder]] = [
    ParameterListDefinesHeader,
    ParameterTypesHeader,
    SmartDataHeader,
    SmartDataSource,
    ParameterListHeader,
    ParameterListSource,
    ParameterListTableHeader,
]

#: The ``param_table`` format: the table, a note beside it saying where in
#: memory each of its values ends up, and the system names the table's #if
#: lines compare.  The note is entirely comments, so it adds nothing to the
#: build - it answers a question the table cannot.
PARAM_TABLE_BUILDERS: List[Type[FileBuilder]] = [
    ParamTableHeader,
    ParamOffsetsHeader,
    SystemNamesHeader,
]


def builders_for(config: Config) -> List[Type[FileBuilder]]:
    """The files this project's format produces."""
    if config.output.format == FORMAT_PARAM_TABLE:
        return list(PARAM_TABLE_BUILDERS)
    return list(SMART_DATA_BUILDERS)


#: Tags the ``smart_data`` format writes the same into every parameter, so a
#: parameter cannot choose them: the access mode is PARAM_MODE_NONE there
#: (asked for).  The sublist keeps whatever it says - the same list may be
#: built by a parameter-table project, where the mode is a real column of
#: ADD_PARAM - and the value here replaces it only in memory, on the way into
#: validation and code generation.  The editor shows it read-only.
SMART_DATA_FIXED_TAGS: Dict[str, str] = {"ParamMode": "PARAM_MODE_NONE"}


def fixed_tags(config: Config) -> Dict[str, str]:
    """The tags this project's format fixes, ``{tag id: value}``; empty for none."""
    if config.output.format == FORMAT_PARAM_TABLE:
        return {}
    return dict(SMART_DATA_FIXED_TAGS)


def apply_fixed_tags(model: ParameterList, config: Config) -> ParameterList:
    """Write the tags the format fixes into every top level entry of *model*.

    Changes *model* itself and returns it, so give it a copy of anything that
    is saved: the file must keep its own values.  The top level is enough -
    a field takes its tags from the entry it is in.
    """
    for tag_id, value in fixed_tags(config).items():
        for parameter in model.parameters:
            parameter.tags[tag_id] = value
    return model


__all__ = [
    "builders_for", "fixed_tags", "apply_fixed_tags", "SMART_DATA_FIXED_TAGS",
    "SMART_DATA_BUILDERS", "PARAM_TABLE_BUILDERS", "FileBuilder",
    "ParameterListDefinesHeader", "ParameterListHeader", "ParameterListSource",
    "ParameterListTableHeader", "ParameterTypesHeader", "ParamTableHeader",
    "ParamOffsetsHeader", "SystemNamesHeader",
    "SmartDataHeader", "SmartDataSource",
]
