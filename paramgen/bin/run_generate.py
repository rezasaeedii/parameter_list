"""Entry point of the parameter-list code generator.

Usage (from anywhere; the configuration next to this file is the default)::

    python run_generate.py            # generates the C files
    python run_generate.py --check    # validates the lists, writes nothing

Nothing has to be installed - ``setup_environment.py`` only
checks that the Python on this machine is complete enough.  Everything else is
configured in ``pl_project.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running the script directly from any working directory.
# paramgen/bin/<this file> -> the code is in paramgen/src, which is put on the import
# path here.  Every entry point does exactly this and nothing else, so there
# is one obvious place to look when an import goes wrong.
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
