"""C code generation: model -> ``.c`` / ``.h`` files.

Two folders, and that is the whole design:

    blocks/   one small class per C construct (include, define, comment, ...)
    files/    one class per generated file, whose ``generate()`` writes the
              file top to bottom with ``text += ...``

``c_style.py`` reads the company layout out of ``c.json`` so the generated files
match the VS Code snippet the developers use.

Which files a run produces depends on the project's ``output.format``:
``builders_for()`` answers that, and it is the only place the two formats are
told apart.
"""

from .c_style import CStyle
from .files import FileBuilder, builders_for

__all__ = ["CStyle", "FileBuilder", "builders_for"]
