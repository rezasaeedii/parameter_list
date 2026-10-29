"""Small console-logging helper shared by the whole tool.

Colour is here for one reason: an ERROR has to be findable in a wall of
output.  A run that generates nothing prints its reason somewhere among the
INFO lines, and on a black-and-white console the reader has to *read* every
line to find it.  In red they find it without reading anything.

The rules the colour follows:

* only when the output is a real console - a redirected log file or a CI job
  gets plain text, because escape sequences in a file are noise nobody asked
  for;
* the ``NO_COLOR`` environment variable turns it off, which is the convention
  every other tool honours;
* Windows 10 needs virtual terminal processing switched on before it draws
  escape sequences at all, so that is done once, here, and the colour is
  dropped if the console refuses.
"""

from __future__ import annotations

import logging
import os
import sys

_LOGGER_NAME = "pl_codegen"
_FORMAT = "%(levelname)-8s %(message)s"

# -- the palette ------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
BRIGHT_RED = "\033[91m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"
GREY = "\033[90m"

#: One colour per level.  DEBUG is grey because it is background noise the
#: reader skims; WARNING and ERROR are the two the eye should catch.
_LEVEL_COLOURS = {
    logging.DEBUG: GREY,
    logging.INFO: "",
    logging.WARNING: YELLOW,
    logging.ERROR: BRIGHT_RED,
    logging.CRITICAL: BOLD + BRIGHT_RED,
}

_colour_enabled: bool = False


def _enable_windows_ansi() -> bool:
    """Switch on virtual terminal processing; ``False`` if the console refuses.

    Windows 10 consoles understand ANSI escapes but do not act on them until
    ENABLE_VIRTUAL_TERMINAL_PROCESSING is set on the handle.  Without this the
    user sees the raw escape sequences, which is worse than no colour at all.
    """
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)   # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:       # noqa: BLE001 - any failure just means "no colour"
        return False


def _use_utf8() -> None:
    """Let this process print the characters the tool actually uses.

    The Windows console still defaults to cp1252, which cannot encode a '▾'
    or a Persian path - and a UnicodeEncodeError while REPORTING a problem
    hides the problem behind a traceback about printing it.  Python 3.7+ can
    re-open the stream; anything older keeps what it had.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_use_utf8()


def colour_supported(stream=None) -> bool:
    """Whether *stream* is a console that should be given colour."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    return _enable_windows_ansi()


def paint(text: str, colour: str) -> str:
    """Wrap *text* in *colour*, or return it unchanged when colour is off."""
    if not _colour_enabled or not colour:
        return text
    return f"{colour}{text}{RESET}"


class _ColourFormatter(logging.Formatter):
    """Colours the level name, and an ERROR's whole line.

    Only the level name is painted for the quieter levels: a wall of coloured
    prose is as hard to read as no colour at all.  An error is the exception -
    it is the line the reader is looking for, so the whole line carries the
    colour.
    """

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not _colour_enabled:
            return text
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        if not colour:
            return text
        if record.levelno >= logging.ERROR:
            return f"{colour}{text}{RESET}"
        # paint the level name only, so the message stays readable
        name = record.levelname
        return text.replace(name, f"{colour}{name}{RESET}", 1)


def setup_logging(verbose: bool = False, quiet: bool = False,
                  colour: bool | None = None) -> logging.Logger:
    """Configure and return the tool-wide logger.

    *colour* forces colour on or off; ``None`` means "decide from the stream",
    which is what every entry point of the tool passes.
    """
    global _colour_enabled
    _colour_enabled = colour_supported() if colour is None else bool(colour)

    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_ColourFormatter(_FORMAT))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    """Return the tool-wide logger (already configured by :func:`setup_logging`)."""
    return logging.getLogger(_LOGGER_NAME)


def banner(text: str, colour: str = CYAN) -> str:
    """Return a simple visual separator used between pipeline stages."""
    rule = "=" * 78
    return f"\n{paint(rule, colour)}\n{paint(text, colour)}\n{paint(rule, colour)}"
