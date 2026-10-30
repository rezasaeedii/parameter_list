# pl_codegen

The generator: model, validation, offsets, C output.

Its only input is a **project file** and the XML models it names. It never
learns what wrote those XMLs - the editor in `../pl_gui/` does, and so could a
text editor. That is what makes the same model always produce the same C.

`app_home.py` is where the paramgen/project split lives: the app is three folders
up (`paramgen/src/pl_codegen` -> `paramgen/`), a project is somewhere else entirely, and
every path in a project file is resolved from the project file itself.

| folder | what is in it |
|---|---|
| `model/` | the parameter, the list, value types, tags, the structure types and the enumerations |
| `xml_model/` | model ⟷ XML: schema, reader, writer, and the types file (structures and enumerations) |
| `validation/` | one class per rule, and the collector that runs them |
| `layout/` | tag offsets, and the memory-layout drift check |
| `codegen/` | one builder per generated file |

A **structure type** is a `struct` declaration, in `model/struct_type.py`. A
structure parameter *names* one, so changing the type changes every parameter
that names it (`model/struct_sync.py`). The types of a parameter sublist live
next to it in `foo_types.xml`, which is what lets a sublist be handed to another
project with its structures intact. An **enumeration** (`model/enum_type.py`) lives
in the same file: a parameter of one is a value of its integer base type that may
hold only the enumeration's values.

`choices.py` holds the four drop-down lists. They belong to the machine, not to
a project, so they live in `paramgen/var/choices.json`.

Read `pipeline.py` first: it is the whole run, in order, on one screen.
