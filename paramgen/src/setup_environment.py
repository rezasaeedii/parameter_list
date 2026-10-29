"""One-click environment check.

Run this once before the first use: start ``run.bat`` on Windows (a double
click) or ``run.sh`` on Linux and choose *Check this PC*, or say it up front
from a terminal: ``run.bat setup`` / ``./run.sh setup``.

There is nothing to install.  The tool is the graphical editor and the code
generator, and both of them use **only the Python standard library** - no
``pip``, no ``requirements.txt``, no internet.  That is a deliberate property of
a decision, not an accident: the company machines are offline, and a tool that
needs a package is a tool that cannot be used there.

So this script does exactly one useful thing: it tells you, in plain words,
whether the Python on this machine is new enough and complete enough to run the
tool - and if it is not, which part is missing and what to do about it.
"""

from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path
from typing import List, Optional, Tuple

MINIMUM_PYTHON = (3, 11)
TOOLS_DIR = Path(__file__).resolve().parent

#: Standard library modules the editor and the generator rely on.  They ship
#: with Python; the check exists to give a clear message on a stripped-down or
#: embedded Python installation, where some of them can genuinely be absent.
STANDARD_MODULES: List[Tuple[str, str]] = [
    ("xml.etree.ElementTree", "reading and writing the parameter sublist XML files"),
    ("http.server", "the local web server behind the graphical editor"),
    ("json", "the configuration file and the editor API"),
    ("webbrowser", "opening the editor in the default browser"),
    ("dataclasses", "the model classes"),
    ("argparse", "the command line of run_generate.py"),
]


def _print_header() -> None:
    print("=" * 78)
    print("Parameter list code generator - environment check")
    print("=" * 78)
    print(f"Python      : {platform.python_version()} ({sys.executable})")
    print(f"Platform    : {platform.system()} {platform.release()}")
    print(f"App folder  : {TOOLS_DIR.parent}")
    print()


def _red(text: str, colour: Optional[bool] = None) -> str:
    """*text* in red, so a refusal cannot be read past - on a console only.

    The colour rules are the tool's own (``logging_utils``: ``NO_COLOR``, a
    real console, the Windows escape-sequence switch), imported here rather
    than at the top: the checks below are what decide whether the tool can be
    imported at all, and a broken copy must still get its message - plain.
    *colour* forces it on or off; ``None`` decides from the console.
    """
    try:
        from pl_codegen import logging_utils
    except Exception:                                  # noqa: BLE001 - reported later
        return text
    if colour is None:
        colour = logging_utils.colour_supported()
    if not colour:
        return text
    return f"{logging_utils.BOLD}{logging_utils.BRIGHT_RED}{text}{logging_utils.RESET}"


def check_python_version(colour: Optional[bool] = None) -> bool:
    """Whether this Python is new enough to run the tool.

    When it is not, that is the one thing worth reading on the screen: nothing
    the tool offers - the editor, the generator, the tests - will work with it.
    So it is said in red, and the check stops there.
    """
    if sys.version_info >= MINIMUM_PYTHON:
        return True
    wanted = f"{MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}"
    for line in (f"ERROR: Python {wanted} or newer is required, but "
                 f"{platform.python_version()} is running.",
                 f"       The tool does not work with this Python: the editor, the "
                 f"generator and the tests",
                 f"       all need {wanted} or newer.",
                 f"       Install Python {wanted} or newer from python.org and run "
                 f"this check again."):
        print(_red(line, colour))
    return False


def check_standard_modules() -> bool:
    """The editor and the generator need these - and only these."""
    print("Checking the standard library modules the tool uses:")
    ok = True
    for name, reason in STANDARD_MODULES:
        try:
            importlib.import_module(name)
            print(f"  [ok]      {name:<24} - {reason}")
        except ImportError:
            print(f"  [MISSING] {name:<24} - {reason}")
            ok = False
    if not ok:
        print("\nERROR: this Python installation is incomplete. Install the official\n"
              "       Python distribution from python.org and run this script again.")
    return ok


def check_tool_imports() -> bool:
    """Import the tool itself, which is the check that actually matters."""
    print("\nChecking the tool:")
    sys.path.insert(0, str(TOOLS_DIR))
    for module, reason in (("pl_codegen.pipeline", "the code generator"),
                           ("pl_gui.server", "the graphical editor")):
        try:
            importlib.import_module(module)
            print(f"  [ok]      {module:<24} - {reason}")
        except Exception as error:                   # noqa: BLE001 - report anything
            print(f"  [FAILED]  {module:<24} - {type(error).__name__}: {error}")
            print("\nERROR: the tool folder looks incomplete. Copy it again in full.")
            return False
    return True


def _print_footer() -> None:
    # Said the way THIS machine starts the tool.  It used to tell a Linux user
    # to double-click run.bat, and "python run.py" - which only works from
    # inside bin/, and on most Linux machines not at all: they have python3.
    # The launcher works from the app folder on both, with the same arguments.
    # Importing the tool is safe here: the footer is only printed once
    # check_tool_imports() has passed.
    from pl_codegen.app_home import LAUNCHER

    commands = (("editor", "the graphical editor"),
                ("generate", "generate the C files"),
                ("tests", "run every self test"),
                ("generate --check", "validate the sublists, write nothing"))
    width = max(len(f"{LAUNCHER} {command}") for command, _what in commands)
    start = "Double-click" if LAUNCHER.endswith(".bat") else "Start"

    print()
    print("-" * 78)
    print("Everything is ready - no package needs to be installed.")
    print(f"{start}  {LAUNCHER}  and choose what you want, or from a terminal:")
    for command, what in commands:
        print(f"  {f'{LAUNCHER} {command}':<{width}}  - {what}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that this machine can run the parameter list tool. "
                    "Nothing is installed and nothing is downloaded.")
    parser.add_argument("--check-only", action="store_true",
                        help="accepted for compatibility; this script only ever checks")
    parser.parse_args()

    _print_header()
    if not check_python_version():
        return 2
    if not check_standard_modules():
        return 2
    if not check_tool_imports():
        return 2
    _print_footer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
