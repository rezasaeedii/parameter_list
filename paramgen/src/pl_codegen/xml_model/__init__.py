"""The XML format that separates the editor from the generator.

    the editor writes the XML   ->   the generator reads it and writes the C

The generator never learns where the XML came from.  That is the whole point:
the graphical editor writes it, a person with a text editor could write it, and
either way the same model produces the same C.  Anything else that wants to
write one has to agree with :mod:`schema` and with nothing else.
"""

from . import schema
from .xml_reader import read_xml
from .xml_writer import model_to_element, write_xml

__all__ = ["schema", "read_xml", "write_xml", "model_to_element"]
