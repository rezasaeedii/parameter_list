"""Writing one setting back into ``pl_project.json``, comments and all.

The editor lets the user choose *which* parameter lists take part in a build and
*in what order*, and that choice has to end up in the configuration file - it is
what ``run_generate.py`` reads, and the two must never disagree.

The obvious way to do that would be ``json.load`` / ``json.dump``, and it is the
wrong way for a file somebody may have written comments into: the tool reads
JSONC, projects made before the file became plain JSON came with a page of
comments, and a round trip through ``json`` would silently delete them the first
time somebody pressed a button in the editor.  So this module edits the *text*
instead, replacing exactly the one array it is asked to replace and touching
nothing else in the file.

What it writes is plain JSON - a comma between entries and none after the last
- so a file the app made stays one that any JSON editor opens without an error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from pl_codegen.errors import CodeGeneratorError


def rewrite_model_files(config_path: Path, names: List[str], *,
                        key: str = "model_files", indent: str = "  ") -> None:
    """Replace the ``inputs.model_files`` array of *config_path* with *names*.

    Every comment in the file survives, including the ones written inside the
    array itself - a commented-out sub list is somebody's note to themselves,
    not something a button press should throw away.  Those comments are gathered
    and written back *below* the new entries: after a reorder there is no line
    left for a trailing comment to sit on, so keeping the note and admitting it
    is now a note about the list as a whole beats guessing where it belonged.
    """
    text = config_path.read_text(encoding="utf-8")
    span = _array_span(text, key)
    if span is None:
        raise CodeGeneratorError(
            f"Could not find an \"{key}\" array in '{config_path}'.\n"
            f"Add one to the 'inputs' section and try again.")

    start, end = span
    lead = _line_indent(text, start) + indent
    kept = _comments_in(text[start + 1:end])

    # A trailing comma after the last entry is JSONC, not JSON: every JSON
    # editor underlined the project file in red after the first change of lists.
    last = len(names) - 1
    lines = [f"{lead}{json.dumps(name)}{',' if index < last else ''}"
             for index, name in enumerate(names)]
    lines += [f"{lead}{comment}" for comment in kept]
    body = "\n" + "\n".join(lines) + "\n" + _line_indent(text, start) if lines else ""

    config_path.write_text(text[:start] + "[" + body + "]" + text[end + 1:],
                           encoding="utf-8", newline="\n")


def _comments_in(body: str) -> List[str]:
    """Every comment written inside the array, in order, one entry per comment.

    A ``//`` inside a file name is part of the name and not a comment, so the
    text is walked rather than split on the marker.
    """
    kept: List[str] = []
    index = 0
    while index < len(body):
        if body[index] == '"':
            index = _skip_string(body, index)
            continue
        if body.startswith("//", index):
            end = _skip_line_comment(body, index)
            kept.append(body[index:end].strip())
            index = end
            continue
        if body.startswith("/*", index):
            end = _skip_block_comment(body, index)
            kept.append(" ".join(body[index:end].split()))
            index = end
            continue
        index += 1
    return kept


def _array_span(text: str, key: str) -> Optional[Tuple[int, int]]:
    """Index of the ``[`` and the matching ``]`` of ``"key": [ ... ]``.

    Both halves of this are done by walking the text rather than by matching a
    pattern, and for the same reason: the file is full of comments, and a
    commented-out ``// "model_files": [ ... ]`` - exactly the note somebody
    leaves behind when they try something out - looks identical to the real
    setting.  Rewriting inside that comment would produce a file that no longer
    parses, so the walk skips comments and strings while it looks for the key
    and again while it counts the brackets.
    """
    start = _find_key(text, key)
    if start is None:
        return None

    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == '"':
            index = _skip_string(text, index)
            continue
        if text.startswith("//", index):
            index = _skip_line_comment(text, index)
            continue
        if text.startswith("/*", index):
            index = _skip_block_comment(text, index)
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return start, index
        index += 1
    return None


def _find_key(text: str, key: str) -> Optional[int]:
    """Index of the ``[`` that opens the real ``"key": [`` - never one in a comment."""
    needle = f'"{key}"'
    index = 0
    while index < len(text):
        char = text[index]
        if text.startswith("//", index):
            index = _skip_line_comment(text, index)
            continue
        if text.startswith("/*", index):
            index = _skip_block_comment(text, index)
            continue
        if char != '"':
            index += 1
            continue

        end = _skip_string(text, index)
        if text[index:end] != needle:
            index = end
            continue

        # the key itself, in code and not in a comment: the '[' has to be the
        # next thing after the colon, or this is a different setting
        after = end
        while after < len(text) and text[after] in " \t\r\n":
            after += 1
        if after < len(text) and text[after] == ":":
            after += 1
            while after < len(text) and text[after] in " \t\r\n":
                after += 1
            if after < len(text) and text[after] == "[":
                return after
        index = end
    return None


def _skip_line_comment(text: str, index: int) -> int:
    end = text.find("\n", index)
    return len(text) if end == -1 else end


def _skip_block_comment(text: str, index: int) -> int:
    end = text.find("*/", index + 2)
    return len(text) if end == -1 else end + 2


def _skip_string(text: str, index: int) -> int:
    """Index just past the JSON string that starts at *index*."""
    index += 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index + 1
        index += 1
    return index


def _line_indent(text: str, index: int) -> str:
    """The whitespace at the start of the line *index* is on."""
    line_start = text.rfind("\n", 0, index) + 1
    stripped = text[line_start:index].lstrip()
    return text[line_start:index - len(stripped)] if stripped else text[line_start:index]
