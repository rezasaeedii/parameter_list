# Parameter list code generator — the app

Edit a project's parameter sublists in a browser, generate its `.c` / `.h` files.
Nothing is installed: the Python standard library only, because the machines
this runs on are offline.

This folder is the **app**. It is copied once onto a machine and never changes
while you work. The sublists and the generated code belong to a
**project**, which is a folder somewhere else with a `pl_project.json` in it.

**Start here:** double-click **`run.bat`** on Windows, or start **`run.sh`** on
Linux — the only thing in this folder you ever run, and the two behave exactly
alike. It asks what you want:

| | |
|---|---|
| `1` | **Editor** — open a project and edit its parameter sublists |
| `2` | **Generate code** — write the C files of the project opened last |
| `3` | **Tests** — run every self test of the tool |
| `4` | **Check this PC** — is the Python here complete enough? (run once) |

Or say it up front, from a terminal:

```
run.bat tests
run.bat editor ..\projects\demo
run.bat generate -c ..\projects\demo --check
```

```
./run.sh tests
./run.sh editor ../projects/demo
./run.sh generate -c ../projects/demo --check
```

Anything after the action is passed on to it; each one also has its own
`--help`. A relative path is taken from this folder, on both systems.

**On Linux**, `run.sh` finds `python3` (3.11 or newer) itself. A folder copied
over from Windows — a zip, a USB stick — loses the mark that lets a file be
started, so run it as `sh run.sh`, or mark it once with `chmod +x run.sh`. It
must keep its Unix line endings: saved with Windows ones it does not start at
all, and `tests/run_docs_test.py` says so.

In the editor: `Ctrl+S` saves, `Ctrl+G` generates. **Project ▾** in the top bar
opens, creates and closes projects; **Structure types…** declares the `struct`
types the parameters are built from, and **Enum types…** the enumerations - a
value that may hold only its named values; **⚙ ▸ Project settings…** edits
`pl_project.json` itself.

A **project** is a folder with a `pl_project.json` in it — the **parameter
sublists** it is built from (the XML files that together make its parameter list), in
what order, **what kind of code it generates** and where that goes.
`output.format` picks the kind:

| | |
|---|---|
| `smart_data` | the `cg_` files: smart-data objects and the descriptor table |
| `param_table` | one `nsrParamTables.h` of `ADD_PARAM()` lines, for the older firmware |

The parameter sublists are the same XML either way, so a sublist can be used by
both — but `param_table` has no structures, arrays or enumerations, so a sublist using
them is an error there and fine in the other. Every path in
it is relative to the file itself, so the folder can be moved or handed on. Each
parameter sublist `foo.xml` carries its structure types and enumerations beside it
in `foo_types.xml`, so a sublist can be taken into another project intact.

| folder | what is in it |
|---|---|
| `bin/` | the entry points — one small file per action |
| `src/` | the code: `pl_codegen/` (the generator) and `pl_gui/` (the editor) |
| `tests/` | the tool's own tests |
| `templates/` | what a new project is made of: `pl_project.json`, `c.json`, and the company `choices.json` |
| `docs/` | the Persian user and developer manuals (Word + PDF) and the C usage example |
| `var/` | what the app writes: recent projects, and this machine's drop-down lists |

The C library the generated code plugs into — smart data and the parameter
descriptor — is not inside this folder at all: it is `smart_data/` and
`parameter_descriptor/`, next to `paramgen/` in this same repository (see the
top-level README). It **stays there**: a project is not given a copy of it.
The library belongs to the firmware, so where it lives in a firmware tree, and
which version of it that tree is on, is the firmware's business and not this
tool's. Copy the two folders in by hand when a project needs them.

The four drop-down lists (system names, parameter modes, types, data types) are
the **company's**, not a project's: they live in `var/choices.json` and every
project on this machine reads the same one.
