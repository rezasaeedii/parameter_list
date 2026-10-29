# -*- coding: utf-8 -*-
"""Every claim the documentation makes that the code can check.

Run it with::

    python tests/run_docs_test.py

Three kinds of check:

  * a phrase that describes something that no longer exists - a button that was
    renamed, a folder that moved, a file whose name changed;
  * a name the docs quote that ought to exist in the source, and does not;
  * the launchers the docs tell people to start: ``run.sh``, the Linux twin of
    ``run.bat``, has to reach Linux in a shape Linux can run.

Docs that name a thing nobody can find are worse than no docs: the reader goes
looking, does not find it, and stops trusting the rest.
"""
import pathlib
import re
import sys
import zipfile

APP = pathlib.Path(__file__).resolve().parent.parent
ROOT = APP.parent
sys.path.insert(0, str(APP / "src"))

from pl_codegen.logging_utils import (BOLD, BRIGHT_RED, GREEN,  # noqa: E402
                                      colour_supported, paint)
import pl_codegen.logging_utils as _logging_utils               # noqa: E402

_logging_utils._colour_enabled = colour_supported()

#: text that must not appear anywhere any more -> what it is now
GONE = {
    "tools/": "paramgen/",
    "tools\\\\": "paramgen\\",
    "plcogen": "paramgen",
    "codegen_config.json": "pl_project.json",
    "model_snapshot": "full_parameter_list",
    "last_build_file": "full_parameter_list_file",
    "last_build/": "full_parameter_list/",
    "snapshot_file": "full_parameter_list_file",
    ".types.xml": "_types.xml",
    "_structures.xml": "_types.xml",
    "StructTemplates": "the structures file beside the list",
    "Save as a type": "Structure types…",
    "Save '": "Structure types…",
    "save_template": "create_struct_type / update_struct_type",
    "apply_template": "use_struct_type",
    "delete_template": "delete_struct_type",
    "useTemplate": "useType",
    "editTemplates": "editTypes",
    "state.templates": "state.structTypes",
    "tree.js": "grid.js",
    "run_gui.bat": "run.bat",
    "run_tests.bat": "run.bat tests",
    "run_setup.bat": "run.bat setup",
    "run_generate.bat": "run.bat generate",
    "+ Sub-structure": "the field table of a structure type",
    "Lists ▾": "the ☰ button",
    "btn-view-tree": "there is one view now",
    "btn-save-template": "btn-edit-type",
    "phase2": "there is one phase",
    "فاز دو": "there is one phase",
    "GS Name": "User Name",
    "GS name": "User name",
    # 'pl_app\run.bat' written through a step that ate the backslash: the '\r'
    # became a line break, and three places in the user manual told people to
    # double-click "tools un.bat".
    "\nun.bat": "run.bat",
}

#: files the docs are allowed to name, checked against the tree
KNOWN_PATHS = re.compile(
    r"\b(?:pl_app/|plcogen/|paramgen/)?(?:src/|bin/|tests/|docs/|templates/)?"
    r"(?:pl_codegen|pl_gui)?/?[\w/]+\.(?:py|js|css|html|json|c|h|xml|bat|sh)\b")

WHERE = [
    APP / "README.md",
    APP / "src" / "pl_codegen" / "README.md",
    APP / "docs" / "parameter_list_user_manual_fa.docx",
    APP / "templates" / "pl_project.json",
    APP / "run.bat",
    APP / "run.sh",
]
WHERE += sorted((APP / "docs" / "manual_source" / "parts").glob("*.html"))
WHERE += sorted((APP / "docs" / "manual_source").glob("notes_*.py"))
WHERE += sorted((APP / "docs" / "manual_source").glob("build_*.py"))

#: sections the manual marks as history: they name old things ON PURPOSE
HISTORY = re.compile(r"<!-- HISTORY-BLOCK.*?/HISTORY-BLOCK -->", re.S)


def read_doc(path: pathlib.Path) -> str:
    """The text of a documentation file.

    A Word file is a zip: the words are in ``word/document.xml``, one ``<w:t>``
    per run, and the invisible direction marks the Persian text carries around
    Latin words are dropped so that a phrase can be found in it.
    """
    if path.suffix != ".docx":
        return HISTORY.sub("", path.read_text(encoding="utf-8"))
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = xml.replace("</w:p>", "\n")
    text = "".join(a or b for a, b in re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>|(\n)", xml))
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                         ("&apos;", "'")):
        text = text.replace(entity, char)
    return text.replace("‎", "").replace("‏", "")


def check_the_launchers() -> int:
    """``run.sh`` has to reach a Linux machine in a shape Linux can run.

    The tool is built on Windows, where nothing ever starts run.sh - so it can
    break here without anybody noticing, and the one file a Linux user starts
    is then the one that does not start:

      * saved by a Windows editor, every line ends in CR LF.  Linux reads the
        first line as "/bin/sh\\r" ("bad interpreter: No such file or
        directory") and every command after it with a stray character on the
        end;
      * its first line is what makes "./run.sh" work at all;
      * ``trap : INT`` is load-bearing (the comment above it in run.sh says
        why): without it a Ctrl+C in the pause leaves the terminal showing
        nothing that is typed, and dash - Ubuntu's sh - dies of the Ctrl+C that
        stopped the editor the moment the menu ends.

    Returns the number of problems found.
    """
    script = APP / "run.sh"
    if not script.is_file():
        print("  MISSING  paramgen/run.sh - the Linux twin of run.bat")
        return 1

    data = script.read_bytes()
    found = 0
    carriage_returns = data.count(b"\r")
    if carriage_returns:
        print(f"  CRLF     paramgen/run.sh has {carriage_returns} Windows line "
              f"ending(s) and Linux cannot run it. Save it with Unix (LF) "
              f"line endings.")
        found += 1
    if not data.startswith(b"#!/bin/sh\n"):
        print("  START    paramgen/run.sh does not begin with '#!/bin/sh' - "
              "'./run.sh' needs that line to know what runs it.")
        found += 1
    if b"\ntrap : INT\n" not in data:
        print("  TRAP     paramgen/run.sh has lost its 'trap : INT' line - see the "
              "comment that was above it.")
        found += 1
    return found


def main() -> int:
    problems = 0
    for path in WHERE:
        if not path.is_file():
            continue
        text = read_doc(path)
        # Two files name old things legitimately: the pitfalls chapter is ABOUT
        # what changed, and the file-by-file reference is generated from the
        # code itself, so by construction it says what the code says.
        if path.name == "p05_reference.html":
            continue
        # words a file is allowed to still use, because it is ABOUT the change:
        # the (now gone) pitfalls chapter explained what moved, and the
        # manual's glossary names the old field on purpose, for a reader who
        # still has a project that says GS Name.
        exempt = {
            "p07_pitfalls.html": ("Save as a type", "StructTemplates",
                                  "save_template", "apply_template",
                                  "codegen_config.json", "tools/"),
            "parameter_list_user_manual_fa.docx": ("GS Name", "GS name"),
        }.get(path.name, ())
        for stale, instead in GONE.items():
            if stale in text:
                if stale in exempt:
                    continue
                count = text.count(stale)
                print(f"  STALE  {path.relative_to(ROOT)}: {count} x {stale!r}"
                      f"  ->  {instead}")
                problems += count

    # ---- names the docs quote that must exist -------------------------
    print()
    tree = {p.relative_to(APP).as_posix() for p in APP.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}
    quoted = set()
    for path in WHERE:
        if not path.is_file() or path.suffix not in (".html", ".md", ".docx"):
            continue
        text = read_doc(path)
        for match in KNOWN_PATHS.findall(text):
            name = match.lstrip("/")
            for app_folder in ("paramgen/", "plcogen/", "pl_app/"):   # its name, and the old ones
                if name.startswith(app_folder):
                    name = name[len(app_folder):]
            quoted.add(name)

    missing = []
    for name in sorted(quoted):
        if name in tree:
            continue
        # a bare file name is fine if something in the tree ends with it
        if any(item.endswith("/" + name) or item == name for item in tree):
            continue
        missing.append(name)

    interesting = [n for n in missing
                   if n.startswith(("src/", "bin/", "tests/", "docs/", "templates/",
                                    "pl_codegen/", "pl_gui/"))]
    for name in interesting:
        print(f"  NO SUCH FILE  {name}")
    problems += len(interesting)

    # ---- the launchers -------------------------------------------------
    print()
    broken = check_the_launchers()

    print()
    if problems or broken:
        if problems:
            print(paint(f"{problems} stale reference(s) in the documentation.",
                        BOLD + BRIGHT_RED))
        if broken:
            print(paint(f"{broken} problem(s) with run.sh, the Linux launcher.",
                        BOLD + BRIGHT_RED))
        return 1
    print(paint("The documentation names nothing that no longer exists, and "
                "run.sh is fit to start on Linux.", GREEN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
