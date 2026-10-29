"""The building blocks a generated C file is assembled from.

Every module here holds ONE small class that knows how to write ONE kind of C
construct, and nothing else.  Each class has an ``__init__`` and one or more
``generate...`` methods that simply return a piece of text:

    include.py         #include <x>  /  #include "x"
    define.py          #define NAME VALUE
    comment.py         /* ... */, doxygen blocks, function separators
    enum.py            typedef enum { ... } eName;
    variable.py        extern int x;  /  int x;
    function.py        prototypes and function bodies
    table.py           ASCII tables (used to draw the parameter list in a comment)
    file_banner.py     the doxygen banner at the top of a file
    file_footer.py     the "EOF" line at the bottom
    include_guard.py   #ifndef / #define / #endif
    cpp_guard.py       extern "C" { ... }
    section_marker.py  /* Includes ------------------------------------ */

The file builders in ``codegen/files/`` call these one after another with
``text += ...``, so a whole generated file can be read top to bottom in one
Python function.
"""

from .comment import Comment
from .cpp_guard import CppGuard
from .define import Define
from .enum import Enum
from .file_banner import FileBanner
from .file_footer import FileFooter
from .function import Function
from .include import Include
from .include_guard import IncludeGuard
from .section_marker import SectionMarker
from .table import Table
from .variable import Variable

__all__ = [
    "Comment", "CppGuard", "Define", "Enum", "FileBanner", "FileFooter",
    "Function", "Include", "IncludeGuard", "SectionMarker", "Table", "Variable",
]
