"""Sets the version number of ParamGen - for whoever maintains the tool.

    python bin/set_version.py              asks for it
    python bin/set_version.py 01.01.85     takes it from here

Not one of the user-facing actions behind ``run.py``: nobody who only edits
parameter lists ever needs it, so it is started on its own, through
``set_version.bat`` beside it.

The version is written in exactly one place, the ``__version__`` line of
``src/pl_codegen/__init__.py``, and everything that shows it reads it from
there: the first line of the run.bat menu, ``run.bat generate --version``, the
header of every generated C file and the ``generatorVersion`` of every list
the editor saves.  So that one line is all this changes - the manuals are the
maintainer's to update by hand.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# paramgen/bin/<this file> -> the version is in paramgen/src/pl_codegen.
APP_DIR = Path(__file__).resolve().parent.parent
INIT_FILE = APP_DIR / "src" / "pl_codegen" / "__init__.py"

#: Three pairs of digits separated by dots, the way the company numbers its
#: releases: 01.01.85.
VERSION_FORMAT = re.compile(r"\d{2}\.\d{2}\.\d{2}")

#: How a version is written, said the same way in every message.
EXAMPLE = "01.01.85"

#: The one line that holds the version.
VERSION_LINE = re.compile(r'^(__version__ = ")([^"\r\n]*)(")', re.MULTILINE)


class VersionError(Exception):
    """The version could not be set; the message says why."""


def check_format(version: str) -> None:
    if not VERSION_FORMAT.fullmatch(version):
        raise VersionError(
            f"'{version}' is not a valid version. Use three pairs of digits "
            f"separated by dots, like {EXAMPLE}.")


def current_version(init_file: Path = INIT_FILE) -> str:
    """The version the tool has now."""
    found = VERSION_LINE.findall(_read(init_file))
    if len(found) != 1:
        raise VersionError(f"{init_file} has {len(found)} __version__ lines, not one.")
    return found[0][1]


def set_version(version: str, init_file: Path = INIT_FILE) -> str:
    """Writes *version* into *init_file* and returns the version it replaced.

    Only the text between the quotes changes: every other byte of the file,
    line endings included, is written back exactly as it was read.  Nothing is
    written at all when the version is malformed or the line is not there
    exactly once.
    """
    check_format(version)
    text = _read(init_file)
    found = VERSION_LINE.findall(text)
    if len(found) != 1:
        raise VersionError(f"{init_file} has {len(found)} __version__ lines, not one.")
    old = found[0][1]
    if old != version:
        new_text = VERSION_LINE.sub(lambda match: match.group(1) + version + match.group(3),
                                    text)
        with open(init_file, "w", encoding="utf-8", newline="") as handle:
            handle.write(new_text)
    return old


def _read(init_file: Path) -> str:
    # newline="" keeps CRLF as CRLF, so the file is written back unchanged
    with open(init_file, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def main(argv: list) -> int:
    # INIT_FILE read here, not bound as a default, so a test can point the
    # whole tool at a copy and never touch the real file
    init_file = INIT_FILE
    try:
        current = current_version(init_file)
        print(f"  ParamGen is version {current} now.")
        print()
        if argv:
            version = argv[0].strip()
        else:
            print("  Type the new version as three pairs of digits, like xx.xx.xx")
            print(f"  Press Enter on its own to keep {current}.")
            print()
            # a byte-order mark is what PowerShell puts in front of text piped
            # into a program; it is not part of what anybody typed
            version = input("  New version: ").strip().lstrip("﻿")
            print()
            if not version:
                print(f"  Nothing changed; ParamGen stays at {current}.")
                return 0
        old = set_version(version, init_file)
    except VersionError as error:
        print(f"  {error}")
        print("  Nothing changed.")
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("  Nothing changed.")
        return 1

    if old == version:
        print(f"  ParamGen is already version {version}; nothing changed.")
        return 0
    print(f"  Done: ParamGen is now version {version} (it was {old}).")
    print()
    print("  The run.bat menu and 'run.bat generate --version' show it right away.")
    print("  Generated files and saved sublists carry it from the next time they")
    print("  are generated or saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
