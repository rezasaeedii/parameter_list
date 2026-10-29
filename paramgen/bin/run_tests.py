"""Runs every test, in order, and reports one verdict.

    python bin/run_tests.py

This is what to run after any change to the tool.  It is deliberately a plain
script: no test framework to install, and it works on a machine with no
internet.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# paramgen/bin/<this file> -> the code is in paramgen/src, which is put on the import
# path here.  Every entry point does exactly this and nothing else, so there
# is one obvious place to look when an import goes wrong.
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, CYAN,  # noqa: E402
                                            GREEN, YELLOW, colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils  # noqa: E402

# The suites run as child processes, so each one decides for itself; this
# one only needs colour for its own headings and its own verdict.
_logging_utils._colour_enabled = colour_supported()

# A Windows console prints the box drawing below happily, but as soon as the
# output is sent anywhere else - "python run_tests.py > log.txt", a CI job, a
# pipe into more - Python falls back to the ANSI code page, which has no '=' or
# '-' box characters, and the run dies with UnicodeEncodeError before a single
# suite has started.  Replacing the unencodable characters keeps the log
# readable and, far more importantly, keeps the tests running.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

SUITES = [
    ("validation rules", "tests/run_validation_test.py"),
    ("the editor", "tests/run_editor_test.py"),
    ("every project setting", "tests/run_settings_test.py"),
    ("the project settings dialog", "tests/run_project_settings_test.py"),
    ("the documentation", "tests/run_docs_test.py"),
    ("setting the version", "tests/run_version_test.py"),
    ("structure types", "tests/run_struct_test.py"),
    ("the parameter-table format", "tests/run_paramtable_test.py"),
    ("generated code compiles and runs", "tests/run_compile_test.py"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_tests.py",
        description="Runs every self test, in order, and reports one "
                    "verdict. Needs no test framework and no internet.",
        epilog="Suites:\n  " + "\n  ".join(f"{title:<34} {script}"
                                            for title, script in SUITES),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-l", "--list", action="store_true",
                        help="print the suites that would run, and stop")
    arguments = parser.parse_args()

    if arguments.list:
        for title, script in SUITES:
            found = (APP_DIR / script).is_file()
            mark = paint("ok ", GREEN) if found else paint("MISSING", BRIGHT_RED)
            print(f"  [{mark}] {title:<34} {script}")
        return 0

    failures = []
    skipped = []
    ran = 0
    for title, script in SUITES:
        path = APP_DIR / script
        if not path.is_file():
            print(paint(f"-- {title}: {script} not found, skipped\n", YELLOW))
            skipped.append(title)
            continue
        print(paint(f"== {title}  ({script})", CYAN))
        result = subprocess.run([sys.executable, str(path)], cwd=APP_DIR)
        print()
        ran += 1
        if result.returncode != 0:
            failures.append(title)

    if failures:
        print(paint(f"{len(failures)} suite(s) FAILED: " + ", ".join(failures),
                    BOLD + BRIGHT_RED))
        return 1
    # A suite that was not there did not pass; saying so keeps a half-copied
    # folder from looking like a healthy one.
    print(paint(f"All {ran} suite(s) passed.", GREEN)
          + (paint(f"  {len(skipped)} were missing: " + ", ".join(skipped), YELLOW)
             if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
