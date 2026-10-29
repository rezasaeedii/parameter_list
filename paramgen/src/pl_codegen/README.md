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
| `model/` | the parameter, the list, value types, tags, and the structure types |
| `xml_model/` | model ⟷ XML: schema, reader, writer, and the structures file |
| `validation/` | one class per rule, and the collector that runs them |
| `layout/` | tag offsets, and the memory-layout drift check |
| `codegen/` | one builder per generated file |

A **structure type** is a `struct` declaration, in `model/struct_type.py`. A
structure parameter *names* one, so changing the type changes every parameter
that names it (`model/struct_sync.py`). The types of a parameter sub list live
next to it in `foo_types.xml`, which is what lets a sub list be handed to another
project with its structures intact.

`choices.py` holds the four drop-down lists. They belong to the machine, not to
a project, so they live in `paramgen/var/choices.json`.

Read `pipeline.py` first: it is the whole run, in order, on one screen.
