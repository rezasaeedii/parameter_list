"""Parameter-list code generator.

This package reads a parameter list as XML, checks it, and writes the C files.
It knows nothing about where the XML came from - the graphical editor in
``pl_gui`` writes it, and a person with a text editor could write it too.
That separation is what makes the tool predictable: the same model always
produces the same C, whoever wrote the model.

Everything under here is deliberately split into small, single-responsibility
modules, so that changing one aspect of the generated code means finding and
editing exactly one file:

    config.py          -> how the tool is configured
    errors.py          -> how problems are reported
    naming.py          -> how C identifiers are derived from parameter names
    pipeline.py        -> the run: XML -> model -> checks -> offsets -> files
    model/             -> the in-memory description of a parameter list
    xml_model/         -> model  <-> XML (the source of truth on disk)
    validation/        -> model  -> diagnostics
    layout/            -> model  -> the MemoryOffset of every tag
    codegen/           -> model  -> C source/header files

Anything that knows about the editor - a dialog, an undo stack, an HTTP route -
belongs *outside* this package, in ``pl_gui``.
"""

__version__ = "01.01.01"
__tool_name__ = "parameter_list_code_generator"

__all__ = ["__version__", "__tool_name__"]
