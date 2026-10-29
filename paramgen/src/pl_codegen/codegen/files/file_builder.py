"""Base class of every generated file.

It does three things and nothing more:

  * it keeps the model, the configuration and the tag offsets at hand,
  * it creates one instance of every block class (``self.include``,
    ``self.define``, ``self.comment``, ...),
  * it saves the text that :meth:`generate` returned.

Everything else happens inside the ``generate()`` of each concrete builder,
which simply writes the file from top to bottom with ``text += ...``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ... import __tool_name__, __version__
from ...config import Config, relative_to_root
from ...layout.tag_offset import OffsetMap
from ...model.parameter import Parameter
from ...model.parameter_list import ParameterList
from ...naming import (array_size_macro, index_macro, offset_total_macro,
                       smart_data_symbol, struct_type_name)
from ..blocks import (Comment, CppGuard, Define, Enum, FileBanner, FileFooter, Function,
                      Include, IncludeGuard, SectionMarker, Table, Variable)
from ..c_style import CStyle


#: The line that says a file came out of this tool.  Anything looking for
#: the tool's own output - an abandoned copy left in an old output folder,
#: say - recognises it by this, so it lives here, beside the one place that
#: writes it.
GENERATED_MARKER = "This file is generated automatically - DO NOT EDIT IT BY HAND."


class FileBuilder(ABC):
    """Builds the complete text of one generated file."""

    def __init__(self, model: ParameterList, config: Config, offsets: OffsetMap,
                 style: CStyle) -> None:
        self.model = model
        self.config = config
        self.offsets = offsets
        self.style = style
        self.tab = style.indent
        self.timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        self._leaves: Optional[List[Parameter]] = None

        # one instance of every block class - use them inside generate()
        self.banner = FileBanner(style)
        self.footer = FileFooter(style)
        self.marker = SectionMarker(style)
        self.guard = IncludeGuard()
        self.cpp = CppGuard()
        self.include = Include()
        self.define = Define()
        self.comment = Comment()
        self.enum = Enum(self.tab)
        self.variable = Variable()
        self.function = Function(self.tab)
        self.table = Table()

    # -- to be written by each concrete builder --------------------------
    @property
    @abstractmethod
    def file_name(self) -> str:
        """Name of the generated file, e.g. ``cg_parameter_list.h``."""

    @abstractmethod
    def generate(self) -> str:
        """Return the complete text of the file."""

    # -- saving ----------------------------------------------------------
    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.file_name
        path.write_text(self.generate(), encoding="utf-8", newline="\n")
        return path

    # -- small helpers used by the builders ------------------------------
    @property
    def parameters(self) -> List[Parameter]:
        """The flattened leaves: every value the generated table holds.

        A struct contributes no entry of its own, only its fields, each with a
        dotted name such as ``Position.Home.Lat``.
        """
        if self._leaves is None:
            self._leaves = self.model.flatten()
        return self._leaves

    @property
    def guard_name(self) -> str:
        return self.file_name.rsplit(".", 1)[0].upper() + "_H"

    def generation_notes(self) -> List[str]:
        """The "do not edit" lines placed in the banner of every file."""
        if not self.config.codegen.emit_generation_info:
            return []
        notes = [
            GENERATED_MARKER,
            f"Generator      : {__tool_name__} v{__version__}",
        ]
        if self.config.codegen.emit_timestamp:
            notes.append(f"Generated at   : {self.timestamp}")
        # Named from the project root - the folder of pl_project.json - and never
        # with this machine's folders: the banner is then the same wherever the
        # project is built, so a file kept in git does not change just because
        # somebody else generated it.
        for index, source in enumerate(self.model.source_files):
            notes.append(f"{'Input file(s)  :' if index == 0 else '                 '} "
                         f"{relative_to_root(source, self.config.path.parent)}")
        structs = len(self.model.struct_parameters())
        notes.append(f"Parameters     : {len(self.parameters)} value(s)"
                     + (f" in {structs} structure(s)" if structs else ""))
        return notes

    # -- generated file names --------------------------------------------
    @property
    def defines_header(self) -> str:
        return self.config.generated_file_name("defines", "h")

    @property
    def list_header(self) -> str:
        return self.config.generated_file_name("", "h")

    @property
    def list_source(self) -> str:
        return self.config.generated_file_name("", "c")

    @property
    def table_header(self) -> str:
        return self.config.generated_file_name("table", "h")

    @property
    def smart_data_header(self) -> str:
        return self.config.smart_data_file_name("h")

    @property
    def smart_data_source(self) -> str:
        return self.config.smart_data_file_name("c")

    # -- identifier names -------------------------------------------------
    def index_of(self, parameter: Parameter) -> str:
        return index_macro(parameter.name, self.config.codegen.index_define_prefix)

    def array_size_of(self, parameter: Parameter) -> str:
        """The size macro of *parameter*'s array declaration.

        A value of an array field is named after the TYPE that declares the
        field (``Stest.alive`` -> ``STEST_ALIVE_ARRAY_SIZE``), because every
        parameter of the type shares that one declaration; a top level array is
        named after itself.
        """
        return self.array_size_of_name(parameter.array_declaration or parameter.name)

    def array_size_of_name(self, dotted_name: str) -> str:
        """Array-size macro of a node, addressed by its dotted path.

        ``array_size_macro`` drops any element index, so the leaves
        ``Wheels[0].Samples`` and ``Wheels[1].Samples`` and the declaration
        ``Wheels.Samples`` all name ``WHEELS_SAMPLES_ARRAY_SIZE``.
        """
        return array_size_macro(dotted_name, self.config.codegen.index_define_prefix)

    def smart_data_of(self, parameter: Parameter) -> str:
        """The C object of a leaf, e.g. ``Cg_SmartData_Position.Home.Lat``.

        ``c_object`` is set by ``ParameterList.flatten()`` and already carries
        the ``.field.field`` part; only the top level name gets the prefix.
        """
        path = parameter.c_object or parameter.name
        return smart_data_symbol(path, self.config.codegen.smart_data_prefix)

    def top_level_objects(self) -> List[Tuple[str, str, Optional[str], Optional[str]]]:
        """The smart-data objects declared at file scope.

        A primitive parameter yields one smart-data object; a struct parameter
        yields ONE object of its generated structure type, which already holds
        the objects of all its fields.  Returns
        ``(c type, name, array size macro or None, comment)``.
        """
        objects: List[Tuple[str, str, Optional[str], Optional[str]]] = []
        for parameter in self.model.enabled:
            name = smart_data_symbol(parameter.name,
                                     self.config.codegen.smart_data_prefix)
            if parameter.is_struct:
                # A struct array is a real C array of the generated type; its
                # elements were expanded into separate leaves in the model, but
                # the object itself is declared once, with its size.
                # an INSTANCE of its structure type - 'sCgStruct_Stest
                # Cg_SmartData_MyStr' - not a type of its own
                objects.append((self.struct_type_of(parameter.value_type_name
                                                    or parameter.name), name,
                                self.array_size_of(parameter)
                                if parameter.is_array else None,
                                self.description_of(parameter)))
                continue

            value_type = parameter.value_type
            if value_type is None:
                continue

            comment = self.description_of(parameter)
            unit = self.unit_of(parameter)
            if unit:
                comment = f"[{unit}] {comment}" if comment else f"[{unit}]"
            objects.append((
                value_type.smart_data_struct, name,
                self.array_size_of(parameter) if parameter.is_array else None,
                comment))
        return objects

    def struct_type_of(self, dotted_name: str) -> str:
        return struct_type_name(dotted_name, self.config.codegen.struct_type_prefix)

    @property
    def types_header(self) -> str:
        return self.config.generated_file_name("types", "h")

    def tag_size_function_of(self, tag_id: str) -> str:
        """Name of the generated ``...GetXxxSize()`` function of a tag."""
        from ...naming import tag_size_function
        return tag_size_function(tag_id)

    def sized_tags(self):
        """Tags that at least one enabled value carries.

        A tag nobody uses has a total of zero and no size macro, so it gets no
        getter either - an accessor that can only ever return 0 is noise.
        """
        from ...model.tags import TAG_REGISTRY
        return [spec for spec in TAG_REGISTRY if self.offsets.total(spec.tag_id) > 0]

    def offset_total_of(self, tag_id: str) -> str:
        return offset_total_macro(tag_id, self.config.codegen.offset_define_prefix)

    @property
    def quantity(self) -> str:
        return self.config.codegen.quantity_define

    @property
    def descriptor_symbol(self) -> str:
        return self.config.codegen.descriptor_symbol

    def description_of(self, parameter: Parameter) -> str:
        """Description for the table - an empty string, never ``None``.

        ``pDescription`` and ``pUnit`` are read far more often than they are
        checked, and a ``NULL`` there turns an ordinary
        ``printf("%s", p->pUnit)`` into undefined behaviour.  An empty string
        costs one byte in flash, is safe to pass anywhere a string is expected,
        and still tests false with ``pUnit[0] == '\\0'`` for anyone who wants to
        know whether a unit was given.
        """
        if not self.config.codegen.emit_description:
            return ""
        return parameter.description or ""

    def unit_of(self, parameter: Parameter) -> str:
        """Unit for the table - an empty string, never ``None``.  See above."""
        if not self.config.codegen.emit_unit:
            return ""
        return parameter.unit or ""
