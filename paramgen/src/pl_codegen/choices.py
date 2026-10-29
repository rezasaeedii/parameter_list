"""The drop-down lists - the company's own vocabulary.

``SYSTEM NAMES``, ``PARAM MODES``, ``TYPE`` and ``VALUE TYPES`` are the four
lists the editor offers.  They belong to **the company**, not to any one
project: ``SYS_AC_POWER`` means the same thing in every project on the machine,
and a project that carried its own copy would drift from the others the first
time somebody added a sub-system to one of them.

So they live with the app, in ``paramgen/var/choices.json``, and every project on
the machine reads the same file.  The defaults ship in
``paramgen/templates/choices.json`` and are copied out on first use, which is what
makes "restore the company defaults" a real button rather than a promise.

A parameter list written before this still has its own ``<Defines>`` section;
it is read, and used to seed the app's file the first time, so nothing is lost
on the way over.  Nothing writes ``<Defines>`` back out any more.

The names of ``SYSTEM NAMES`` and ``PARAM MODES`` are ``#define``s in the
generated code, and each can be given a number: the dialog takes them as
``SYS_NAV = 16``, and the file keeps them under ``"numbers"``, beside the
lists, so a list stays a plain list of names::

    "systemNames": ["SYS_UNKNOWN", "SYS_NAV"],
    "numbers": {"systemNames": {"SYS_UNKNOWN": 0, "SYS_NAV": 16}}
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from .app_home import TEMPLATES_DIR, VAR_DIR
from .model.defines import (COLUMN_PARAM_MODES, COLUMN_SYSTEM_NAMES, COLUMN_TYPES,
                            COLUMN_VALUE_TYPES, DEFINE_NUMBER_MAX, DEFINE_NUMBER_MIN,
                            GENERATED_DEFINES, Defines)
from .model.types import VALUE_TYPES

#: Where the machine's lists live once somebody has edited them.
CHOICES_FILE = VAR_DIR / "choices.json"

#: What ships with the app, and what "restore the defaults" goes back to.
CHOICES_TEMPLATE = TEMPLATES_DIR / "choices.json"

#: The four lists, and the key each has in the JSON file.
COLUMNS = {
    "paramTypes": COLUMN_TYPES,
    "systemNames": COLUMN_SYSTEM_NAMES,
    "paramModes": COLUMN_PARAM_MODES,
    "valueTypes": COLUMN_VALUE_TYPES,
}

#: The company's own, as a last resort: a machine whose template file has been
#: deleted still has to be able to open a project.
FALLBACK: Dict[str, List[str]] = {
    "paramTypes": ["MONITORING", "SETTING", "COMMAND"],
    "systemNames": ["SYS_UNKNOWN"],
    "paramModes": ["PARAM_MODE_NONE", "PARAM_MODE_USER"],
    "valueTypes": list(VALUE_TYPES),
}


#: The keys of the lists whose names are numbered ``#define``s.
NUMBERED = tuple(key for key, column in COLUMNS.items() if column in GENERATED_DEFINES)

#: Where the file keeps their numbers.
NUMBERS_KEY = "numbers"


def default_choices() -> Dict[str, List[str]]:
    """What the app ships with - the "restore the defaults" answer."""
    data = _read(CHOICES_TEMPLATE)
    return {key: list(data.get(key) or FALLBACK[key]) for key in COLUMNS}


def default_defines() -> Defines:
    """:func:`default_choices` as the model wants it, numbers included."""
    data = _read(CHOICES_TEMPLATE)
    defines = Defines()
    for key, column in COLUMNS.items():
        _take(defines, data, key, column, FALLBACK[key])
    return defines


def load_choices() -> Defines:
    """The machine's lists, as the model wants them.

    The user's file wins; the shipped template fills anything it does not
    mention, so a list added to the app later shows up without anybody having
    to re-save.  A list's numbers come from the same file as the list.
    """
    shipped = _read(CHOICES_TEMPLATE)
    mine = _read(CHOICES_FILE)

    defines = Defines()
    for key, column in COLUMNS.items():
        values = mine.get(key)
        source = mine if isinstance(values, list) and values else shipped
        _take(defines, source, key, column, FALLBACK[key])
    return defines


def _take(defines: Defines, data: Dict[str, object], key: str, column: str,
          fallback: List[str]) -> None:
    """One list of *data* - and its numbers - into *defines*."""
    values = data.get(key)
    if not isinstance(values, list) or not values:
        values = fallback
    defines.values[column] = [str(item).strip() for item in values if str(item).strip()]
    if key not in NUMBERED:
        return
    given = data.get(NUMBERS_KEY)
    given = given.get(key) if isinstance(given, dict) else None
    if not isinstance(given, dict):
        return
    numbers = {}
    for name, number in given.items():
        # a number edited into the file by hand is kept as long as it is a
        # whole number at all: out of range is the validation's to say
        if isinstance(number, int) and not isinstance(number, bool):
            numbers[str(name).strip()] = number
    if numbers:
        defines.numbers[column] = numbers


def parse_numbered(lines: List[str]) -> Tuple[List[str], Dict[str, int]]:
    """What the dialog's box says: ``SYS_NAV = 16`` per line -> names and numbers.

    A line without ``=`` is a name that takes the number after the one above
    it, so it gets no entry in the numbers.  A number may be written in decimal
    or in hex (``0x10``), negative too (``-1``), and has to fit the 32-bit tag
    it is stored in.
    Raises ``ValueError`` naming the line when one cannot be read.
    """
    names: List[str] = []
    numbers: Dict[str, int] = {}
    for line_number, raw in enumerate(lines, start=1):
        line = str(raw).strip()
        if not line:
            continue
        if "=" not in line:
            names.append(line)
            continue
        name, _, text = (part.strip() for part in line.partition("="))
        if not name:
            raise ValueError(f"Line {line_number} ('{line}') has a number but no "
                             f"name. Write it as NAME = number.")
        if not text:                     # 'SYS_NAV =' - a number left out
            names.append(name)
            continue
        digits = text.rstrip("uU")
        try:
            number = int(digits, 0)
        except ValueError:
            try:
                number = int(digits, 10)   # '016': base 0 refuses a leading zero
            except ValueError:
                raise ValueError(
                    f"'{text}' after {name} is not a whole number. Write it as "
                    f"{name} = 16 (or 0x10, or -1), or leave the number out to take "
                    f"the one after the line above.") from None
        if number < DEFINE_NUMBER_MIN or number > DEFINE_NUMBER_MAX:
            raise ValueError(f"{name} = {text} does not fit: the number is stored in a "
                             f"32-bit tag, so it has to be {DEFINE_NUMBER_MIN} to "
                             f"{DEFINE_NUMBER_MAX}.")
        names.append(name)
        numbers[name] = number
    return names, numbers


def save_choices(defines: Defines) -> None:
    """Write the machine's lists back - the numbers somebody gave included."""
    data: Dict[str, object] = {key: list(defines.get(column))
                               for key, column in COLUMNS.items()}
    numbers = {}
    for key in NUMBERED:
        column = COLUMNS[key]
        given = {name: defines.number_of(column, name) for name in defines.get(column)
                 if defines.number_of(column, name) is not None}
        if given:
            numbers[key] = given
    if numbers:
        data[NUMBERS_KEY] = numbers
    try:
        CHOICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHOICES_FILE.write_text(json.dumps(data, indent=2) + "\n",
                                encoding="utf-8", newline="\n")
    except OSError:
        # A read-only app folder is somebody's deliberate choice.  It costs the
        # change, and the caller has already been told it was saved - so this
        # is the one place that has to stay quiet rather than crash the editor.
        pass


def seed_from(defines: Optional[Defines]) -> None:
    """Take a file's own ``<Defines>`` as the machine's, if it has none yet.

    The one-time hand-over: the first project opened on a machine that has
    never had a choices file gives it its lists, so nothing anybody had typed
    into a parameter list is lost when the lists moved to the app.
    """
    if CHOICES_FILE.is_file() or defines is None:
        return
    if not any(defines.get(column) for column in COLUMNS.values()):
        return

    shipped = default_defines()
    merged = Defines()
    for key, column in COLUMNS.items():
        own = list(defines.get(column))
        merged.values[column] = own or list(shipped.get(column))
        # a list taken from the template keeps the template's numbers too
        if not own and column in shipped.numbers:
            merged.numbers[column] = dict(shipped.numbers[column])
    save_choices(merged)


def _read(path) -> Dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
