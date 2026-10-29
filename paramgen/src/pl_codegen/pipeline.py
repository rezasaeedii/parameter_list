"""The shared pipeline: XML model -> validation -> tag offsets -> C files.

This module is the core of the tool and knows exactly one input: the XML model.

    XML  ->  model  ->  validation  ->  tag offsets  ->  C files

Where that XML comes from is the front end's business, not the core's.  In this
the graphical editor (``pl_gui``) writes it; the generator never learns that,
which is what would let a different front end be put in front of it without
touching a line here.

Several parameter sublists can be listed - usually one per sub-module of the
firmware - and they are merged into one list before anything else happens.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional

from .codegen.c_style import CStyle
from .codegen.files import apply_fixed_tags, builders_for
from .codegen.files.file_builder import GENERATED_MARKER
from .config import FORMAT_PARAM_TABLE, Config
from .errors import (CodeGeneratorError, DiagnosticCollector, Severity,
                     SourceLocation)
from .layout.tag_offset import build_offset_map
from .logging_utils import banner, get_logger
from .model.parameter_list import ParameterList, merge_lists
from .model.struct_sync import types_used_by
from .validation.validator import Validator
from .xml_model.xml_reader import read_xml
from .layout.drift import LayoutDrift, compare as compare_layout, previous_build
from .xml_model.xml_writer import write_xml


@dataclass
class PipelineResult:
    """Everything a caller needs to report the outcome of a run."""

    success: bool
    diagnostics: DiagnosticCollector
    model_file: Optional[Path] = None
    generated_files: List[Path] = field(default_factory=list)
    parameter_count: int = 0
    #: What this run moved relative to the previous one.  See ``layout/drift.py``:
    #: a value that changed byte offset is a value a board in the field will read
    #: wrongly, so it is reported even though the code is perfectly correct.
    drift: Optional[LayoutDrift] = None
    #: Every parameter sublist this run read, in build order.  ``model_file``
    #: is only the first of them.
    model_files: List[Path] = field(default_factory=list)


#: "work out the previous build yourself" - see Pipeline.generate
_READ_FROM_DISK = object()


class Pipeline:
    """Runs the code generator."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = get_logger()

    # -- reading the model -----------------------------------------------
    def load_model(self, diagnostics: DiagnosticCollector,
                   model_file: Optional[Path] = None) -> ParameterList:
        """The merged parameter list of every configured sublist."""
        paths = [model_file] if model_file else list(self._config.inputs.model_files)

        parts = []
        for path in paths:
            self._logger.info("  reading %s", path)
            if not path.is_file():
                raise CodeGeneratorError(
                    f"The parameter sublist '{path}' does not exist.\n"
                    f"Create it in the editor, or fix "
                    f"'inputs.model_files' "
                    f"in {self._config.path.name}.")
            part = read_xml(path, diagnostics)
            if str(path) not in part.source_files:
                part.source_files.append(str(path))
            parts.append((path, part))
        # The one merge the editor uses too - it is also where a structure type
        # two lists declare, or a list using another list's type, is noticed.
        merged = merge_lists(parts)

        if len(paths) > 1:
            self._logger.info("  merged %d sublist(s) into one parameter list",
                              len(paths))
        # What the format decides for every parameter - in a smart-data project
        # the access mode - replaces what the lists say, here in memory only.
        return apply_fixed_tags(merged, self._config)

    def generate(self, model: ParameterList, diagnostics: DiagnosticCollector,
                 previous: object = _READ_FROM_DISK) -> PipelineResult:
        """Validate *model* and write the C files.

        *previous* is the model the last build used; it is what the memory
        layout is compared against.  By default it is read from
        ``output.xml_file``, which is exactly where the previous run left it.
        A front end that writes that file itself before generating has to
        capture the old one first and pass it in here, or it would end up
        comparing the new model with itself.
        """
        # Again, for a model that did not come through load_model; doing it
        # twice changes nothing.
        apply_fixed_tags(model, self._config)
        if not Validator(self._config).validate(model, diagnostics):
            return PipelineResult(False, diagnostics)

        if previous is _READ_FROM_DISK:
            previous = previous_build(self._config.output.xml_file)
        drift = compare_layout(
            previous, model,
            table=self._config.output.format == FORMAT_PARAM_TABLE)

        offsets = build_offset_map(model)
        style = CStyle.load(self._config.style.snippet_file,
                            company=self._config.style.company,
                            indent=self._config.style.indent)

        generated: List[Path] = []
        directory = self._config.output.code_directory

        for builder_class in builders_for(self._config):
            builder = builder_class(model, self._config, offsets, style)
            path = builder.save(directory)
            generated.append(path)
            self._logger.info("  generated %s (%d lines)", path.name,
                              path.read_text(encoding="utf-8").count("\n"))

        # The copy of the merged model is what the NEXT run compares against, so
        # it is written last - only a run that got this far counts as "what the
        # firmware was built from".  The lists it names are named from the
        # project root, the way the banners of the C files name them.
        #
        # Its types file beside it holds the structure types the project USES -
        # every type a structure of any list is of, and the types those hold -
        # and not the ones a list declares and nothing uses: those stay in their
        # own list's types file until somebody deletes them there.
        full = replace(model, struct_types=types_used_by(model.parameters,
                                                         model.struct_types))
        try:
            write_xml(full, self._config.output.xml_file,
                      emit_timestamp=self._config.codegen.emit_timestamp,
                      project_root=self._config.path.parent)
        except OSError as error:                 # a courtesy file, never fatal
            self._logger.warning("  could not write the model copy: %s", error)

        if drift.breaks_stored_data:
            self._logger.warning("  %s", drift.summary())

        self._report_abandoned_copies(generated, diagnostics)

        return PipelineResult(True, diagnostics, self._config.inputs.model_file,
                              generated, len(model.flatten()), drift)

    def _report_abandoned_copies(self, generated: List[Path],
                                 diagnostics: DiagnosticCollector) -> None:
        """An older copy of a generated file, sitting where output used to go.

        Changing ``output.code_directory`` does not move what the previous runs
        wrote: the old files stay exactly where they were, and from then on
        every build writes somewhere else.  Nothing about either file says so.
        Somebody then changes the company name, or the order of the lists, or
        anything at all, generates, opens the file they have always opened -
        and it has not changed, because nothing writes to it any more.  That is
        a very hard thing to work out from the inside, and it costs one walk of
        the project folder to say out loud.

        Only files this tool wrote are reported: the marker in the banner is
        what identifies one, so a header somebody wrote by hand that happens to
        share a name is never accused of being stale.
        """
        root = self._config.path.parent if self._config.path else None
        if root is None or not root.is_dir():
            return

        written = {path.resolve() for path in generated}
        by_name = {path.name: path for path in generated}
        skip = {"lib", ".git", ".svn", "__pycache__", "node_modules"}

        for folder, folders, files in os.walk(root):
            folders[:] = [name for name in folders if name not in skip]
            for name in files:
                if name not in by_name:
                    continue
                found = Path(folder) / name
                try:
                    if found.resolve() in written:
                        continue
                    head = found.read_text(encoding="utf-8",
                                           errors="replace")[:2000]
                except OSError:
                    continue
                if GENERATED_MARKER not in head:
                    continue
                diagnostics.warning(
                    "OUT001",
                    f"An older copy of {name} is still at {found}, and nothing "
                    f"writes to it any more.",
                    SourceLocation(file=str(found)),
                    hint=f"This build wrote {by_name[name]}. The old copy was "
                         f"left behind when 'output.code_directory' changed - "
                         f"delete it, or point 'code_directory' back at its "
                         f"folder.")


    def run(self, model_file: Optional[Path] = None) -> PipelineResult:
        """Read the model file(s) and produce the C files."""
        diagnostics = DiagnosticCollector()
        self._logger.info(banner("Reading the parameter list"))
        model = self.load_model(diagnostics, model_file)
        self._logger.info("  %d top level parameter(s), %d value(s) after flattening",
                          len(model), len(model.flatten()))

        self._logger.info(banner("Generating the C code"))
        return self.generate(model, diagnostics)

    def check(self, model_file: Optional[Path] = None) -> PipelineResult:
        """Validate the model without writing any file at all."""
        diagnostics = DiagnosticCollector()
        self._logger.info(banner("Checking the parameter list"))
        model = self.load_model(diagnostics, model_file)
        self._logger.info("  %d top level parameter(s), %d value(s) after flattening",
                          len(model), len(model.flatten()))
        ok = Validator(self._config).validate(model, diagnostics)
        # What was READ: the -m file when there is one, not the configured list
        # it replaced.
        read = [model_file] if model_file else list(self._config.inputs.model_files)
        return PipelineResult(ok, diagnostics, read[0] if read else None,
                              parameter_count=len(model.flatten()), model_files=read)


def render_diagnostics(diagnostics: DiagnosticCollector, verbose: bool) -> str:
    """Format the diagnostics for the console."""
    minimum = Severity.INFO if verbose else Severity.WARNING
    return diagnostics.render(minimum)
