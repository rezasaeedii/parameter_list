"""The operating system's own Open and Browse-for-folder dialogs.

The editor runs in a browser, and a browser cannot hand a page a real path - a
file input gives a name and a blob, never a location a project file could
name.  So the dialogs used to be drawn by the page itself, one folder at a time
from the root of a drive, and that is not what anybody expects from a program:
every other one on the machine opens the dialog Windows draws, with its address
bar, its Quick access and its drives.  (Reported.)

So the server opens that dialog itself.  ``tkinter`` ships with Python, and on
Windows its file dialogs ARE the system's own (IFileDialog) - nothing has to be
installed and nothing is downloaded, which is the rule this tool lives by.  Off
Windows they are Tk's own dialogs.  Where there is no tkinter at all - a Linux
Python without its python3-tk package, a machine with no desktop - the editor
keeps its in-page dialog, which is why :func:`available` exists.

**The dialog runs in a process of its own.**  The server answers on many
threads, and Tk belongs to the one thread that made it; a second process keeps
Tk out of the server entirely, and a dialog that hangs or crashes cannot take
the editor down with it.  This file is that process too: run as a script, it
shows one dialog and prints the answer as one line of JSON.

``PL_EDITOR_NATIVE_DIALOGS=0`` leaves the in-page dialogs in charge, which is
what a machine without tkinter gets - and how that path is tried on a machine
that has it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

#: Set to 0 to use the editor's in-page dialogs instead.
SWITCH = "PL_EDITOR_NATIVE_DIALOGS"

#: What a dialog chooses.  "probe" shows nothing: it only proves that a dialog
#: COULD be shown here, which is what the tests ask.
KIND_FILE = "file"
KIND_FOLDER = "folder"
KIND_PROBE = "probe"

#: ``(label, patterns)`` - what the file dialog offers in its type list.
FileTypes = Sequence[Tuple[str, Sequence[str]]]


class NativeDialogUnavailable(Exception):
    """No dialog of the system's could be shown; the in-page one has to do."""


class DialogBusy(Exception):
    """A dialog is open already - one at a time, or they pile up behind each other."""


_one_at_a_time = threading.Lock()
_can_show: Optional[bool] = None


def available() -> bool:
    """Whether a dialog of the system's can be shown on this machine.

    The switch is read every time, so it can be turned off for a running test;
    whether tkinter is there is found out once.
    """
    if os.environ.get(SWITCH, "").strip() == "0":
        return False
    global _can_show
    if _can_show is None:
        _can_show = _has_tkinter_and_a_desktop()
    return _can_show


def _has_tkinter_and_a_desktop() -> bool:
    if importlib.util.find_spec("tkinter") is None:
        return False
    if os.name == "nt" or sys.platform == "darwin":
        return True
    # Linux and the like: a dialog needs a desktop to be drawn on.
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def ask(kind: str, title: str, start: Path, filetypes: FileTypes = ()) -> str:
    """Show one dialog and return what was chosen - ``""`` when it was cancelled.

    *start* is where it opens; a folder that is not there opens at the nearest
    one that is.  Raises :class:`NativeDialogUnavailable` when no dialog could
    be shown at all, and :class:`DialogBusy` while another one is still open.
    """
    if not available():
        raise NativeDialogUnavailable("This machine has no file dialog of its own "
                                      "the editor can use.")
    if not _one_at_a_time.acquire(blocking=False):
        raise DialogBusy("A file dialog is open already - finish that one first.")
    try:
        return _run({"kind": kind, "title": title, "start": str(_existing(start)),
                     "filetypes": [[label, list(patterns)] for label, patterns in filetypes]})
    finally:
        _one_at_a_time.release()


def _existing(start: Path) -> Path:
    """*start*, or the nearest folder above it that is there."""
    here = Path(start)
    while not here.is_dir() and here != here.parent:
        here = here.parent
    return here


def child_command(request: Dict[str, object]) -> List[str]:
    """The command that shows one dialog: this file, run by this same Python.

    The request travels as ASCII-only JSON, so a Persian folder name reaches
    the dialog intact whatever the console's code page is.
    """
    return [sys.executable, str(Path(__file__).resolve()),
            json.dumps(request, ensure_ascii=True)]


def _run(request: Dict[str, object]) -> str:
    try:
        done = subprocess.run(child_command(request), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    except OSError as error:
        raise NativeDialogUnavailable(f"The file dialog could not be started: {error}")
    lines = done.stdout.strip().splitlines()
    if done.returncode != 0 or not lines:
        reason = (done.stderr.strip().splitlines() or ["it ended without an answer"])[-1]
        raise NativeDialogUnavailable(f"The file dialog could not be shown: {reason}")
    try:
        answer = json.loads(lines[-1])
    except ValueError:
        raise NativeDialogUnavailable("The file dialog gave an answer that could not "
                                      "be read.") from None
    return str(answer.get("path") or "")


# -- the dialog process ------------------------------------------------------
def _show(request: Dict[str, object]) -> str:
    """Show the dialog *request* asks for and return the chosen path, or ``""``."""
    if os.name == "nt":
        # Without this Windows scales the dialog up as a bitmap on a high-DPI
        # screen, and every word in it is blurred.
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:                                  # noqa: BLE001 - cosmetic
            pass

    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    # The dialog belongs to this hidden window, and a window that stays on top
    # takes its dialog with it: started from a server in the background, it
    # would otherwise open BEHIND the editor and look like nothing happened.
    root.attributes("-topmost", True)
    root.update()
    try:
        kind = request.get("kind")
        if kind == KIND_PROBE:
            return ""
        options = {"parent": root, "title": str(request.get("title") or ""),
                   "initialdir": str(request.get("start") or "")}
        if kind == KIND_FOLDER:
            chosen = filedialog.askdirectory(mustexist=False, **options)
        else:
            filetypes = [(str(label), tuple(str(p) for p in patterns))
                         for label, patterns in request.get("filetypes") or []]
            chosen = filedialog.askopenfilename(filetypes=filetypes or [("All files", "*")],
                                                **options)
        # Tk answers with forward slashes, and with an empty tuple on some
        # platforms when cancelled.
        return os.path.normpath(chosen) if isinstance(chosen, str) and chosen else ""
    finally:
        root.destroy()


def main(argv: Sequence[str]) -> int:
    try:
        request = json.loads(argv[1])
    except (IndexError, ValueError):
        print("usage: native_dialog.py '<request as JSON>'", file=sys.stderr)
        return 2
    path = _show(request)
    print(json.dumps({"path": path}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
