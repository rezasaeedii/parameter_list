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
    array itself - a commented-out sublist is somebody's note to themselves,
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


# -- one setting anywhere in the file ------------------------------------------
#
# The Project settings dialog changes any key of the file, not only the list of
# sublists - and the same promise holds: every comment, every other key and the
# way the file is laid out stay exactly as they were.  So the text is walked,
# the one value is replaced (or the key added where it is missing), and nothing
# else is touched.  (Asked for.)

#: How much deeper each level of a value the file did not have is indented.
_STEP = "  "


def set_json_value(text: str, path: Tuple[str, ...], value: object,
                   key_name: Optional[str] = None) -> str:
    """*text* with the value at *path* - ``("output", "base_name")`` - set to *value*.

    A key the file does not have is added at the end of its section, and a
    section it does not have at the end of the file.  *key_name* renames the
    last key while its value is replaced: the single ``model_file`` becomes the
    ``model_files`` list.  *text* has ``\\n`` line endings; a caller with a
    CRLF file converts it before and after.
    """
    start = _space(text, 0)
    if start >= len(text) or text[start] != "{":
        raise CodeGeneratorError("The project file does not hold a JSON object.")
    obj = start
    for depth, key in enumerate(path):
        members, close = _members(text, obj)
        member = next((item for item in members if item[0] == key), None)
        if member is None:
            # the rest of the path becomes one new member here
            nested: object = value
            for inner in reversed(path[depth + 1:]):
                nested = {inner: nested}
            return _insert_member(text, obj, members, close, key, nested)
        _, key_start, value_start, value_end = member
        if depth == len(path) - 1:
            indent = _line_indent(text, key_start)
            notes = (_comments_in(text[value_start + 1:value_end - 1])
                     if isinstance(value, list) and text[value_start] == "[" else None)
            key_text = (json.dumps(key_name) if key_name
                        else text[key_start:_skip_string(text, key_start)])
            return (text[:key_start] + key_text
                    + text[_skip_string(text, key_start):value_start]
                    + _render(value, indent, notes) + text[value_end:])
        if text[value_start] != "{":
            raise CodeGeneratorError(
                f"'{'.'.join(path[:depth + 1])}' in the project file is not an object.")
        obj = value_start
    return text


def remove_json_value(text: str, path: Tuple[str, ...]) -> str:
    """*text* without the member at *path*; unchanged when the file has none.

    The member's own line goes with it, and the comma that kept it apart from
    its neighbour - the one after it, or the one before when it was the last.
    A section the removal leaves with nothing in it, not even a comment, goes
    too: a key that means nothing has no place in the file.  (Asked for: an
    emptied tag description stayed in the file as "".)  *text* has ``\\n``
    line endings, as for :func:`set_json_value`.
    """
    start = _space(text, 0)
    if start >= len(text) or text[start] != "{":
        raise CodeGeneratorError("The project file does not hold a JSON object.")
    obj = start
    for depth, key in enumerate(path):
        members, close = _members(text, obj)
        index = next((number for number, item in enumerate(members) if item[0] == key), None)
        if index is None:
            return text
        if depth < len(path) - 1:
            value_start = members[index][2]
            if text[value_start] != "{":
                return text
            obj = value_start
            continue
        text = _cut_member(text, members, index)
        if depth > 0:
            members, close = _members(text, obj)
            if not members and not text[obj + 1:close].strip():
                return remove_json_value(text, path[:-1])
    return text


def _cut_member(text: str, members: list, index: int) -> str:
    """*text* without ``members[index]``, its line and its comma."""
    _, key_start, _, value_end = members[index]
    line_start = text.rfind("\n", 0, key_start) + 1
    own_line = not text[line_start:key_start].strip()
    end = value_end
    while end < len(text) and text[end] in " \t":
        end += 1
    has_comma = end < len(text) and text[end] == ","
    if has_comma:
        end += 1
        while end < len(text) and text[end] in " \t":
            end += 1
    if text.startswith("//", end):
        end = _skip_line_comment(text, end)        # a note on its line is its own
    if own_line and (end >= len(text) or text[end] == "\n"):
        start, end = line_start, min(end + 1, len(text))
    else:
        start = key_start
    cut = text[:start] + text[end:]
    if not has_comma and index > 0:
        # it was the last: the comma after the one before it goes instead
        comma = _space(text, members[index - 1][3])
        if comma < start and text[comma] == ",":
            cut = cut[:comma] + cut[comma + 1:]
    return cut


def _insert_member(text: str, obj: int, members: list, close: int,
                   key: str, value: object) -> str:
    """*text* with ``"key": value`` added as the last member of the object at *obj*."""
    if members:
        indent = _line_indent(text, members[0][1])
        last_end = members[-1][3]
        line_end = text.find("\n", last_end)
        line_end = len(text) if line_end == -1 else line_end
        rest = text[last_end:line_end].strip()
        member = f"{json.dumps(key)}: {_render(value, indent)}"
        # The rest of the last member's line is nothing, its comma or a note:
        # the new member goes on a line of its own below it.
        after_comma = rest[1:].strip() if rest.startswith(",") else rest
        if after_comma == "" or after_comma.startswith("//"):
            comma = "" if rest.startswith(",") else ","
            return (text[:last_end] + comma + text[last_end:line_end]
                    + "\n" + indent + member + text[line_end:])
        # everything on one line: right after the last value
        return text[:last_end] + ", " + member + text[last_end:]
    brace_indent = _line_indent(text, obj)
    indent = brace_indent + _STEP
    member = f"{json.dumps(key)}: {_render(value, indent)}"
    inside = text[obj + 1:close]
    if inside.strip():
        # only comments in it: they stay, below the new member
        return text[:obj + 1] + "\n" + indent + member + inside + text[close:]
    return text[:obj + 1] + "\n" + indent + member + "\n" + brace_indent + text[close:]


def _render(value: object, indent: str, notes: Optional[List[str]] = None) -> str:
    """*value* as JSON text for a member whose line starts with *indent*.

    Lists and objects one entry per line, the way the app writes its files.
    *notes* - comments that were inside a list being replaced - are kept below
    the new entries, exactly as ``rewrite_model_files`` keeps them.
    """
    inner = indent + _STEP
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = [f"{inner}{json.dumps(key)}: {_render(item, inner)}"
                 for key, item in value.items()]
        return "{\n" + ",\n".join(lines) + "\n" + indent + "}"
    if isinstance(value, list):
        lines = [f"{inner}{_render(item, inner)}" for item in value]
        body = ",\n".join(lines)
        if notes:
            body += ("\n" if body else "") + "\n".join(f"{inner}{note}" for note in notes)
        return "[\n" + body + "\n" + indent + "]" if body else "[]"
    return json.dumps(value, ensure_ascii=False)


def _space(text: str, index: int) -> int:
    """Index of the next character that is not whitespace or a comment."""
    while index < len(text):
        if text[index] in " \t\r\n":
            index += 1
        elif text.startswith("//", index):
            index = _skip_line_comment(text, index)
        elif text.startswith("/*", index):
            index = _skip_block_comment(text, index)
        else:
            break
    return index


def _value_end(text: str, index: int) -> int:
    """Index just past the JSON value that starts at *index*."""
    if index >= len(text):
        raise CodeGeneratorError("The project file ends where a value was expected.")
    if text[index] == '"':
        return _skip_string(text, index)
    if text[index] in "{[":
        depth = 0
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
            if char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
                if depth == 0:
                    return index + 1
            index += 1
        raise CodeGeneratorError("The project file ends inside an object or a list.")
    end = index
    while end < len(text) and text[end] not in ",}] \t\r\n/":
        end += 1
    return end


def _members(text: str, obj: int) -> Tuple[list, int]:
    """``(key, key start, value start, value end)`` for each member of the
    object whose ``{`` is at *obj*, and the index of its ``}``."""
    members = []
    index = _space(text, obj + 1)
    while index < len(text) and text[index] != "}":
        if text[index] == ",":                  # a trailing comma is JSONC
            index = _space(text, index + 1)
            continue
        if text[index] != '"':
            raise CodeGeneratorError(
                f"The project file has '{text[index]}' where a key was expected.")
        key_end = _skip_string(text, index)
        colon = _space(text, key_end)
        if colon >= len(text) or text[colon] != ":":
            raise CodeGeneratorError("The project file has a key without a ':' after it.")
        value_start = _space(text, colon + 1)
        value_end = _value_end(text, value_start)
        members.append((json.loads(text[index:key_end]), index, value_start, value_end))
        index = _space(text, value_end)
    if index >= len(text):
        raise CodeGeneratorError("The project file ends inside an object.")
    return members, index
