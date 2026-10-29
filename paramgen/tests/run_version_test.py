# -*- coding: utf-8 -*-
"""Does bin/set_version.py change the version, and nothing else?

Run it with::

    python tests/run_version_test.py

Every case works on a copy of ``src/pl_codegen/__init__.py`` in a temporary
folder: the tool's own version is never touched by its tests.
"""
import contextlib
import importlib.util
import io
import pathlib
import shutil
import sys
import tempfile

APP = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "src"))

from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,  # noqa: E402
                                      colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils               # noqa: E402

_logging_utils._colour_enabled = colour_supported()

# bin/ is a folder of scripts, not a package on the import path: the tool is
# loaded from its file, the way set_version.bat runs it.
_spec = importlib.util.spec_from_file_location("set_version", APP / "bin" / "set_version.py")
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

REAL = APP / "src" / "pl_codegen" / "__init__.py"


def copy_of_init(folder: pathlib.Path) -> pathlib.Path:
    target = folder / "__init__.py"
    shutil.copyfile(REAL, target)
    return target


def refused(version: str, target: pathlib.Path) -> bool:
    try:
        tool.set_version(version, target)
    except tool.VersionError:
        return True
    return False


# ---- the cases --------------------------------------------------------------
def test_the_new_version_is_written(folder):
    target = copy_of_init(folder)
    before = target.read_bytes()
    old = tool.current_version(target)
    tool.set_version("01.01.85", target)
    after = target.read_bytes()
    expected = before.replace(f'__version__ = "{old}"'.encode(),
                              b'__version__ = "01.01.85"')
    return (tool.current_version(target) == "01.01.85" and after == expected,
            "only the text between the quotes changed")


def test_line_endings_survive(folder):
    target = folder / "__init__.py"
    target.write_bytes(b'"""doc"""\r\n\r\n__version__ = "1.0.0"\r\n__tool_name__ = "x"\r\n')
    tool.set_version("02.03.04", target)
    return (target.read_bytes()
            == b'"""doc"""\r\n\r\n__version__ = "02.03.04"\r\n__tool_name__ = "x"\r\n',
            "CRLF stays CRLF")


def test_a_malformed_version_changes_nothing(folder):
    target = copy_of_init(folder)
    before = target.read_bytes()
    wrong = ["1.1.85", "01.01", "01.01.855", "aa.bb.cc", "01-01-85", "01.01.85.",
             " 01.01.85x", ""]
    every = all(refused(version, target) for version in wrong)
    return (every and target.read_bytes() == before,
            f"{len(wrong)} wrong spellings refused, file untouched")


def test_no_version_line_changes_nothing(folder):
    target = folder / "__init__.py"
    for text in ('__tool_name__ = "x"\n',
                 '__version__ = "1.0.0"\n__version__ = "1.0.0"\n'):
        target.write_text(text, encoding="utf-8")
        if not refused("01.01.85", target) or target.read_text(encoding="utf-8") != text:
            return False, f"not refused: {text!r}"
    return True, "a missing or doubled line is refused"


def test_the_same_version_writes_nothing(folder):
    target = copy_of_init(folder)
    old = tool.current_version(target)
    tool.set_version("07.07.07", target)
    stamp = target.stat().st_mtime_ns
    tool.set_version("07.07.07", target)
    return target.stat().st_mtime_ns == stamp and old != "07.07.07", "no rewrite"


def test_the_command_line(folder):
    """main() with an argument, and with the answer typed at the prompt."""
    target = copy_of_init(folder)
    saved = tool.INIT_FILE
    tool.INIT_FILE = target
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            given = tool.main(["11.22.33"]) == 0 and tool.current_version(target) == "11.22.33"
            bad = tool.main(["1.2.3"]) == 1 and tool.current_version(target) == "11.22.33"
            sys.stdin = io.StringIO("44.55.66\n")
            typed = tool.main([]) == 0 and tool.current_version(target) == "44.55.66"
            sys.stdin = io.StringIO("\n")
            empty = tool.main([]) == 0 and tool.current_version(target) == "44.55.66"
    finally:
        tool.INIT_FILE = saved
        sys.stdin = sys.__stdin__
    return (given and bad and typed and empty,
            f"argument {given}, refused {bad}, typed {typed}, Enter {empty}")


def test_the_real_file_has_one_version_line(folder):
    return bool(tool.current_version(REAL)), f"version {tool.current_version(REAL)}"


def test_nothing_else_writes_the_version_by_hand(folder):
    """Everything that shows the version must READ it, never repeat it.

    A second copy of the number anywhere in the app would keep showing the old
    one after set_version.bat - which is exactly what the tool promises cannot
    happen.  The manuals and the tests' own sample lists are not the app.
    """
    version = tool.current_version(REAL)
    places = [APP / "run.bat", APP / "run.sh", APP / "README.md"]
    places += sorted((APP / "src").rglob("*.py")) + sorted((APP / "src").rglob("*.js"))
    places += sorted((APP / "src").rglob("*.html")) + sorted((APP / "bin").glob("*.*"))
    places += sorted((APP / "templates").glob("*.*"))
    found = [path.relative_to(APP).as_posix() for path in places
             if path.is_file() and path != REAL
             and f'"{version}"' in path.read_text(encoding="utf-8", errors="replace")]
    return not found, ", ".join(found) or f'"{version}" is written only in __init__.py'


CASES = [
    ("the new version is written", test_the_new_version_is_written),
    ("line endings survive", test_line_endings_survive),
    ("a malformed version changes nothing", test_a_malformed_version_changes_nothing),
    ("no version line changes nothing", test_no_version_line_changes_nothing),
    ("the same version writes nothing", test_the_same_version_writes_nothing),
    ("the command line", test_the_command_line),
    ("the real file has one version line", test_the_real_file_has_one_version_line),
    ("nothing else writes the version by hand", test_nothing_else_writes_the_version_by_hand),
]


def main() -> int:
    failures = 0
    for title, test in CASES:
        with tempfile.TemporaryDirectory(prefix="pl_version_") as raw:
            try:
                ok, note = test(pathlib.Path(raw))
            except Exception as error:            # noqa: BLE001
                ok, note = False, f"blew up: {error!r}"
        mark = paint("PASS", GREEN) if ok else paint("FAIL", BOLD + BRIGHT_RED)
        print(f"  [{mark}] {title:<42} {note}")
        failures += 0 if ok else 1

    print()
    if failures:
        print(paint(f"{failures} of {len(CASES)} version case(s) FAILED.", BOLD + BRIGHT_RED))
        return 1
    print(paint(f"All {len(CASES)} version cases passed.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
