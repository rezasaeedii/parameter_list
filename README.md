# Parameter List Code Generator

A toolset for defining parameter lists and generating the corresponding C/C++
source and header files.

The project consists of the application used to create and manage parameter
lists, together with the libraries required to use the generated parameter-list
structures in the target application.

## Project structure

| Folder | Description |
|---|---|
| `paramgen/` | Main application for editing parameter lists and generating the corresponding C/C++ source and header files. |
| `parameter_descriptor/` | Runtime library used with the generated code to work with parameter descriptors and parameter-list structures. |
| `smart_data/` | Runtime library used with the generated code to work with parameter values and smart-data structures. |
| `test_smart_data/` | Sample project in the `smart_data` format: a sublist with arrays, a structure and enumerations, and the code generated from it. |
| `test_param_table/` | Sample project in the `param_table` format: two sub-system sublists and the `nsrParamTables.h` generated from them. |

The generated code can be integrated with the `smart_data` and
`parameter_descriptor` libraries to use the parameter-list structure in the
target application. Open a sample project in the editor (`paramgen/run.bat`,
**Project ▾ ▸ Open project…**) to see a complete one.

## Documentation

The main application documentation is located in:

`paramgen/docs/`

It contains the **User Manual**, **Developer Manual**, and usage examples.

For a quick introduction to the application, its commands, project structure,
and how to run it, see:

`paramgen/README.md`

The `paramgen/docs/` directory provides more detailed information for both users
and developers, including examples of how the generated code and libraries
are used.