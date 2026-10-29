"""The one way into the tool: a menu of everything it can do.

    run.bat                    # the menu - or just double-click it
    ./run.sh                   # the same menu, on Linux
    run.bat editor             # straight to one action, no menu
    run.bat generate --check   # anything after the action goes to it

Both launchers find a Python, go to their own folder and start this file with
whatever they were given, so from bin/ the same is ``python run.py editor``
(``python3`` on Linux).

There used to be four batch files next to each other - one per action - and a
folder of look-alike files is a question, not an answer: somebody opening it
for the first time has to guess which one they want, and somebody who has used
it for a year still opens the wrong one now and then.  One door with the
actions written on it is easier to find and impossible to get wrong.

Each action is still its own ``run_*.py``, run as a separate process.  That is
deliberate:

  * the editor blocks until Ctrl+C, and Ctrl+C must stop the editor and bring
    the menu back - not kill the menu with it;
  * an action that crashes leaves the menu standing;
  * every action keeps its own exit code, its own arguments and its own
    ``--help``, so nothing here has to know what any of them do.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence

#: The app folder - this file sits at the top of it.
# paramgen/bin/<this file> -> the code is in paramgen/src, which is put on the import
# path here.  Every entry point does exactly this and nothing else, so there
# is one obvious place to look when an import goes wrong.
APP_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR / "src"))

from pl_codegen import __version__                                    # noqa: E402
from pl_codegen.app_home import (LAUNCHER, last_project,          # noqa: E402
                                 project_name)
from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, CYAN, GREEN,  # noqa: E402
                                      GREY, YELLOW, colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils                     # noqa: E402

_logging_utils._colour_enabled = colour_supported()


class Action(NamedTuple):
    """One thing the tool can do, as the menu shows it."""

    key: str                #: the number typed to choose it
    names: Sequence[str]    #: what it may be typed as instead of the number
    title: str              #: the short name in the menu
    what: str               #: the line next to the title
    script: str             #: the run_*.py that does it
    arguments: Sequence[str] = ()   #: arguments that action always wants
    #: exit code -> what to say afterwards.  ``None`` is "any other code".
    endings: Dict[Optional[int], str] = {}


ACTIONS: List[Action] = [
    Action("1", ("editor", "gui", "e"), "Editor",
           "open a project and edit its parameter lists",
           "run_gui.py",
           endings={0: "The editor has stopped.",
                    None: "The editor could not start. Try another port:\n"
                          f"      {LAUNCHER} editor -p 8800"}),

    Action("2", ("generate", "gen", "code", "g"), "Generate code",
           "write the C files of the project opened last",
           "run_generate.py", ("-v",),
           endings={0: "Done - the C files are in the project's output folder.",
                    1: "The parameter lists have problems, so nothing was written.\n"
                       "      Fix the rows listed above and run this again.",
                    None: "The tool could not run. Check the project file and "
                          "the paths in it."}),

    Action("3", ("tests", "test", "t"), "Tests",
           "run every self test of the tool",
           "run_tests.py",
           endings={0: "All tests passed.",
                    None: "SOME TESTS FAILED - scroll up to see which.\n"
                          "      Do not deliver the tool in this state."}),

    Action("4", ("setup", "check", "s"), "Check this PC",
           "is the Python on this machine complete enough?",
           "run_setup.py",
           endings={0: "Ready. Choose 1 to open the editor.",
                    None: "This Python installation cannot run the tool. The "
                          "message above says which part is missing."}),
]

QUIT = ("0", "q", "quit", "exit", "bye")


def find(typed: str) -> Optional[Action]:
    """The action the user meant, by number or by name."""
    typed = typed.strip().lower()
    for action in ACTIONS:
        if typed == action.key or typed in action.names:
            return action
    return None


def show_menu() -> None:
    rule = "=" * 78
    print(f"\n{paint(rule, CYAN)}")
    print(paint(f"  Parameter list code generator {__version__}", CYAN + BOLD))
    print(paint(rule, CYAN))

    # Which project the actions below would act on. Two projects can share a
    # parameter list, so "which one am I about to generate?" is a real
    # question and the menu answers it before it is asked.
    project = last_project()
    print(paint(f"  project: {project_name(project)}  ({project.parent})" if project
                else "  no project yet - choose 1 and open or make one", GREY))
    print()
    for action in ACTIONS:
        print(f"   {paint(action.key, BOLD + GREEN)}  "
              f"{action.title:<16}{paint(action.what, GREY)}")
    print()
    print(f"   {paint('0', BOLD)}  Quit")
    print()


def run(action: Action, extra: Sequence[str] = ()) -> int:
    """Run one action as its own process and return its exit code."""
    script = BIN_DIR / action.script
    if not script.is_file():
        print(paint(f"\n{action.script} is missing. Copy the app folder again "
                    f"in full.", BRIGHT_RED))
        return 2

    command = [sys.executable, str(script), *action.arguments, *extra]
    # Named, not spelled out in full: it is the line the reader would type
    # themselves, and an absolute path to a file in this very folder is not.
    shown = " ".join([action.script, *action.arguments, *extra])
    print(paint(f"\n> python {shown}\n", GREY))
    # The child writes straight to this console, so anything still sitting in
    # our own buffer would appear after it - the header printed under the
    # output it heads.
    sys.stdout.flush()
    try:
        return subprocess.call(command, cwd=str(APP_DIR))
    except KeyboardInterrupt:
        # The editor is stopped exactly this way, so it is a normal ending
        # here and not a failure: say so, and come back to the menu.
        print(paint("\nStopped.", YELLOW))
        return 0


def report(action: Action, code: int, plain: bool = True) -> None:
    """The closing line of an action, in its own words.

    Only for the action as the menu runs it.  ``run.py generate --check``
    writes no file, so "the C files are in the project's output folder" would
    be a plain lie; the action has already said how it went, and saying it
    again from out here - wrongly - is worse than saying nothing.
    """
    if not plain:
        return
    message = action.endings.get(code, action.endings.get(None, ""))
    if not message:
        return
    colour = GREEN if code == 0 else BRIGHT_RED
    print(f"\n    {paint(message, colour)}")


def menu() -> int:
    """Ask, run, ask again - until the user quits."""
    while True:
        show_menu()
        try:
            typed = input(paint("  Select an option [1]: ", BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if typed.lower() in QUIT:
            return 0

        # Enter on its own opens the editor: it is what somebody who
        # double-clicked the launcher came here for.
        chosen = find(typed or "1")
        if chosen is None:
            print(paint(f"\n  '{typed}' is not one of the choices. Type a number "
                        f"from the list, or 0 to quit.", YELLOW))
            continue

        report(chosen, run(chosen))
        try:
            input(paint("\n  Press Enter for the menu. ", GREY))
        except (EOFError, KeyboardInterrupt):
            print()
            return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Everything the parameter list tool can do, in one place. "
                    "With no action it asks.",
        epilog="Actions:\n" + "\n".join(
            f"  {action.key}  {'/'.join(action.names):<22}{action.what}"
            for action in ACTIONS) +
        "\n\nAnything after the action is passed on to it:\n"
        f"  {LAUNCHER} generate --check\n"
        f"  {LAUNCHER} editor -p 8800",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", nargs="?",
                        help="which action to run; omit it for the menu")
    parser.add_argument("rest", nargs=argparse.REMAINDER,
                        help="arguments for that action")
    arguments = parser.parse_args(argv)

    if not arguments.action:
        return menu()

    chosen = find(arguments.action)
    if chosen is None:
        known = ", ".join(action.names[0] for action in ACTIONS)
        print(paint(f"'{arguments.action}' is not an action. Try one of: {known}.",
                    BRIGHT_RED))
        return 2

    code = run(chosen, arguments.rest)
    report(chosen, code, plain=not arguments.rest)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
