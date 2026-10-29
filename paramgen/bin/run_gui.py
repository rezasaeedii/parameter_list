"""Starts the graphical parameter-list editor.

    cd tools
    python run_gui.py

The editor runs entirely on this machine:

  * the server binds to 127.0.0.1, the loopback interface, so nothing on the
    network can reach it;
  * the pages reference no external file, so nothing leaves the machine;
  * when a Chromium based browser is installed, the editor opens in its own
    window - no address bar, no tabs - started with every background-networking
    switch turned off.  Otherwise the default browser is used.

Close the window and press Ctrl+C here to stop the server.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# paramgen/bin/<this file> -> the code is in paramgen/src, which is put on the import
# path here.  Every entry point does exactly this and nothing else, so there
# is one obvious place to look when an import goes wrong.
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen.app_home import PROJECT_FILE_NAME, last_project  # noqa: E402
from pl_codegen.errors import CodeGeneratorError  # noqa: E402
from pl_codegen.logging_utils import setup_logging  # noqa: E402
from pl_gui.server import GuiServer           # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parameter list editor. Opens one project at a time.")
    parser.add_argument("project", nargs="?", type=Path,
                        help=f"the project to open: its folder, or its "
                             f"{PROJECT_FILE_NAME}. Default: the one opened last")
    parser.add_argument("-c", "--config", type=Path, default=None,
                        help="the same thing, spelled as an option")
    parser.add_argument("-p", "--port", type=int, default=8765, help="port to listen on")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open anything; just print the address")
    parser.add_argument("--tab", action="store_true",
                        help="open a tab in the default browser instead of a "
                             "separate application window")
    arguments = parser.parse_args()

    setup_logging()

    # No project is a normal way to start: the editor shows its start screen
    # with the recent projects on it, which is exactly what a machine that has
    # just had the app copied onto it should see.
    chosen = arguments.project or arguments.config or last_project()
    try:
        server = GuiServer(chosen, port=arguments.port)
    except CodeGeneratorError as error:
        print(error)
        return 2

    server.serve_forever(open_browser=not arguments.no_browser,
                         app_window=not arguments.tab)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
