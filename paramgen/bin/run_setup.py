"""Entry point of the environment check.

    cd tools
    python run_setup.py

Like every other ``run_*.py`` in this folder it is deliberately three lines
long: the real work lives in a module (:mod:`setup_environment`) and this file
only exists so that **every user-facing action has the same shape**::

    run_gui.py       run.py editor      the graphical editor
    run_generate.py  run.py generate    generate the C files
    run_tests.py     run.py tests       run every self test
    run_setup.py     run.py setup       check this machine

Nobody has to remember which of them is a script and which is a module.  Which
of them a person wants is a different question, and ``run.py`` - the one thing
in this folder that is meant to be double-clicked - asks it instead of leaving
the folder to be guessed at.
"""

from __future__ import annotations

import sys
from pathlib import Path

# paramgen/bin/<this file> -> the code is in paramgen/src, which is put on the import
# path here.  Every entry point does exactly this and nothing else, so there
# is one obvious place to look when an import goes wrong.
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "src"))

from setup_environment import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
