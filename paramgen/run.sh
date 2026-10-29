#!/bin/sh
# ===========================================================================
#  The parameter list code generator - everything it can do, in one place.
#
#  The Linux twin of run.bat, and it behaves exactly like it.  Start it and
#  it asks what you want:
#
#      1  Editor          open a project and edit its parameter lists
#      2  Generate code   write the C files of the project opened last
#      3  Tests           run every self test of the tool
#      4  Check this PC   is the Python on this machine complete enough?
#
#  This folder is the APP: copied once per machine, never written to while
#  you work.  The lists and the generated code belong to a PROJECT, which is
#  a folder somewhere else with a pl_project.json in it.
#
#  Straight to one of them, without the menu:
#      ./run.sh editor      ./run.sh tests
#      ./run.sh editor ../projects/demo
#      ./run.sh generate -c ../projects/demo --check
#
#  A folder copied over from Windows - a zip, a USB stick - loses the mark
#  that lets a file be started, and "./run.sh" then says "Permission denied".
#  Either start it as  sh run.sh  or mark it once with  chmod +x run.sh.
#  The file must keep Unix line endings: saved with Windows ones, the shell
#  reads every line with a stray character on the end and nothing works.
#
#  Plain POSIX sh on purpose, nothing bash-only: "sh run.sh" has to work on
#  every distribution, including the ones whose sh is dash.
#
#  Nothing is installed and nothing is downloaded: the tool uses only the
#  Python standard library, because the machines it runs on are offline.
#
#  This is the only file you ever start here.  bin/ holds the entry points,
#  src/ the code, templates/ what a new project is made of, docs/ the
#  manuals, tests/ the tool's own tests and var/ the state it writes.
# ===========================================================================

# The folder this file is in, followed through any symbolic link to it.
# run.bat always works from its own folder ("cd /d %~dp0"), so a relative
# path handed to an action - "editor ../projects/demo" - means the same thing
# on both systems: it is taken from here, not from wherever the terminal
# happened to be.  A link to this file in ~/bin must not change that.
here=$0
while [ -h "$here" ]; do
    link=$(readlink "$here")
    case $link in
        /*) here=$link ;;
        *)  here=$(dirname "$here")/$link ;;
    esac
done
cd "$(dirname "$here")" || exit 1

# A double-click in a file manager ("Run" / "Execute") starts this with no
# terminal at all: the menu would read an empty keyboard, quit at once, and
# the user would see nothing happen.  On Windows the same double-click opens
# a console window, so here the script opens a terminal window and starts
# itself again inside it.  Only then - no arguments (a double-click never has
# any), neither end a terminal, and a desktop to open a window on - so a
# script or a CI job that pipes this somewhere is never touched.
if [ $# -eq 0 ] && ! [ -t 0 ] && ! [ -t 1 ] \
        && { [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; }; then
    self="$(pwd)/$(basename "$here")"
    for terminal in x-terminal-emulator gnome-terminal konsole xfce4-terminal \
                    mate-terminal xterm; do
        command -v "$terminal" >/dev/null 2>&1 || continue
        # Each terminal spells "run this command" its own way.
        case $terminal in
            gnome-terminal)               exec "$terminal" -- sh "$self" ;;
            xfce4-terminal|mate-terminal) exec "$terminal" -x sh "$self" ;;
            *)                            exec "$terminal" -e sh "$self" ;;
        esac
    done
    # No terminal program found: carry on anyway, which is no worse than
    # not having tried.
fi

# Ctrl+C is how the editor is stopped, and it has to bring the menu back
# (bin/run.py catches it for exactly that).  But the key reaches every
# program in the terminal window, this script included, and a shell with no
# trap for it dies of it.  dash - the sh of Ubuntu and Debian - does so
# late: it lets the menu carry on and dies the moment the menu ends, so
# nothing below runs, not even the pause that keeps a failure on the screen.
# And any shell dies of a Ctrl+C in the middle of the pause, before it can
# switch the keyboard's echo back on - the window then shows nothing that is
# typed into it.  A trap, unlike ignoring the signal, is not inherited:
# Python still gets its Ctrl+C, and this script only waits for Python to
# finish, as cmd.exe does.
trap : INT

# What cmd.exe's "pause" does: wait for one key, whichever it is, and do not
# echo it.  A key that sends several characters (an arrow, F1) is swallowed
# whole, or the rest of it would land on the prompt after the window's
# program has ended: the terminal writes those characters in one go, and one
# read of up to 64 takes everything that is there - which is also why this is
# one read and not a byte and then a timed wait for more, which a terminal
# that does not implement "stty time" (WSL1's does not) waits on for ever.
# Not waiting on a keyboard (stdin redirected), it takes one character from
# wherever stdin points - at its end, none - exactly as "pause < file" does.
pause() {
    printf '%s' "Press any key to continue . . . "
    if [ -t 0 ]; then
        saved=$(stty -g)
        stty -icanon -echo min 1 time 0
        dd bs=64 count=1 >/dev/null 2>&1
        stty "$saved"
    else
        dd bs=1 count=1 >/dev/null 2>&1
    fi
    echo
}

# Python itself is the one thing that has to be there already, and "command
# not found" in a window that then closes is no help to anybody.  Linux calls
# it python3 - most distributions have no "python" at all, and on an older one
# "python" may still be Python 2 - so python3 is tried first, and whichever is
# found has to be new enough: otherwise the menu dies on its first line with a
# SyntaxError that says nothing about the real problem.
python=
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
               >/dev/null 2>&1; then
        python=$candidate
        break
    fi
done

if [ -z "$python" ]; then
    echo
    echo "    Python 3.11 or newer was not found on this machine."
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            echo "    ('$candidate' is $("$candidate" --version 2>&1), which is too old.)"
        fi
    done
    echo
    echo "    Install Python 3 with the package manager of this Linux - for"
    echo "    example  sudo apt install python3  or  sudo dnf install python3 -"
    echo "    then run this again."
    echo
    pause
    exit 9
fi

"$python" bin/run.py "$@"
exitcode=$?

# The menu already says how each action ended and waits for Enter itself, so
# the plain start needs no pause here.  The "./run.sh tests" form does - a
# window opened for it would close on the result - and so does any failure,
# which is the one message that must never scroll past into a closing window.
if [ -n "$1" ] || [ "$exitcode" -ne 0 ]; then
    echo
    pause
fi
exit "$exitcode"
