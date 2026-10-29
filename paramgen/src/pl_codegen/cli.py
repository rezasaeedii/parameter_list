"""Command line interface of the parameter-list code generator.

It reads the XML model(s) named in the configuration and writes the C files.
The lists are normally edited in the graphical editor, so this is
the command line, and it is what a build script or a CI job calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Sequence

import argparse

from . import __tool_name__, __version__
from .app_home import PROJECT_FILE_NAME, last_project, project_file_in
from .config import Config
from .errors import CodeGeneratorError, Severity
from .logging_utils import (BOLD, BRIGHT_RED, GREEN, YELLOW, banner, paint,
                            setup_logging)
from .pipeline import Pipeline, render_diagnostics
from .validation.rules import ALL_RULES

EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_TOOL_ERROR = 2


def resolve_config_path(given: Optional[Path]) -> Path:
    """Which project to build.

    The app is installed once and every project lives somewhere else, so there
    is no project file "next to the script" any more.  Three answers, in the
    order somebody means them:

      1. the one named on the command line - and a *folder* means the project
         file in it, because that is what somebody drags in;
      2. the project in the current folder, which is what a build script
         invoked from a project root means;
      3. the project the editor had open last, which is what somebody who has
         just been editing means.

    With none of the three there is nothing to build, and saying so beats
    guessing.
    """
    if given is not None:
        given = Path(given).expanduser()
        return project_file_in(given) if given.is_dir() else given

    local = project_file_in(Path("."))
    if local.is_file():
        return local

    remembered = last_project()
    if remembered is not None:
        return remembered

    raise CodeGeneratorError(
        f"No project to build.\n"
        f"Name one:  python run_generate.py -c path/to/{PROJECT_FILE_NAME}\n"
        f"or run from inside a project folder,\n"
        f"or open a project in the editor once and it will be remembered.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_generate.py",
        description="Generates the parameter-list C code of one project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_generate.py                     # the project opened last\n"
            "  python run_generate.py -c ../projects/demo # a project folder\n"
            "  python run_generate.py -m other.xml        # generate from another sub list\n"
            "  python run_generate.py --check             # validate only, write nothing\n"
            ))

    parser.add_argument("-c", "--config", type=Path, default=None, metavar="PROJECT",
                        help=f"the project to build: its folder, or its "
                             f"{PROJECT_FILE_NAME}. Default: the {PROJECT_FILE_NAME} of "
                             f"the current folder, otherwise the project opened last "
                             f"in the editor")
    parser.add_argument("-m", "--model", type=Path, metavar="FILE",
                        help="a parameter sub list (XML) to use instead of the "
                             "configured one(s)")
    parser.add_argument("--check", action="store_true",
                        help="validate the input only; write no file at all")
    parser.add_argument("--list-rules", action="store_true",
                        help="print every validation rule and exit")
    parser.add_argument("-W", "--warnings-as-errors", action="store_true",
                        help="treat warnings as errors")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="also show informational diagnostics")
    parser.add_argument("-q", "--quiet", action="store_true", help="only show problems")
    parser.add_argument("--version", action="version",
                        version=f"{__tool_name__} {__version__}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    logger = setup_logging(verbose=arguments.verbose, quiet=arguments.quiet)

    if arguments.list_rules:
        print("Validation rules:")
        width = max(len(rule_class.rule_id) for rule_class in ALL_RULES)
        for rule_class in ALL_RULES:
            print(f"  {rule_class.rule_id:<{width}}  {rule_class.description}")
        return EXIT_OK

    try:
        config = Config.load(resolve_config_path(arguments.config))
    except CodeGeneratorError as error:
        logger.error("%s", error)
        return EXIT_TOOL_ERROR

    if arguments.warnings_as_errors:
        config.validation.treat_warnings_as_errors = True


    logger.info("%s v%s", __tool_name__, __version__)
    logger.info("configuration: %s", config.path)
    logger.info("input: %s", _describe_input(config))

    try:
        pipeline = Pipeline(config)
        if arguments.check:
            result = pipeline.check(arguments.model)
        else:
            result = pipeline.run(arguments.model)
    except CodeGeneratorError as error:
        logger.error("%s", error)
        return EXIT_TOOL_ERROR

    if not arguments.quiet or not result.success:
        _print_summary(result, arguments.verbose)
    return EXIT_OK if result.success else EXIT_VALIDATION_FAILED


def _describe_input(config) -> str:
    """One line saying exactly which files the run will read."""
    files = config.inputs.model_files
    if not files:
        return "no parameter sub list configured"
    if len(files) == 1:
        return f"parameter sub list {files[0]}"
    listing = "".join(f"\n         - {path}" for path in files)
    return f"{len(files)} parameter sub lists, merged:{listing}"


def _print_drift(drift) -> None:
    """Say, loudly, when this run moved something a board may already store.

    It is printed before the file list, because by the time somebody has read
    "7 files written" they have stopped reading.
    """
    if drift is None or not drift.report():
        return

    # Red for a move, yellow for a list that merely grew: the first is a board
    # in the field reading the wrong address, the second is a note.
    colour = BRIGHT_RED if drift.breaks_stored_data else YELLOW
    rule = paint("=" * 78, colour)
    print()
    print(rule)
    if drift.breaks_stored_data:
        print(paint("  WARNING - THE MEMORY LAYOUT CHANGED SINCE THE LAST BUILD",
                    BOLD + BRIGHT_RED))
    else:
        print(paint("  The parameter list changed since the last build", YELLOW))
    print(rule)
    for line in drift.report():
        print(line)
    print(rule)


def _print_summary(result, verbose: bool) -> None:
    diagnostics = result.diagnostics
    print(banner("Diagnostics"))
    print(render_diagnostics(diagnostics, verbose))
    print()
    print(diagnostics.summary())

    if result.success:
        _print_drift(result.drift)
        if result.generated_files:
            print(f"\nGenerated {len(result.generated_files)} file(s) for "
                  f"{result.parameter_count} value(s):")
            for path in result.generated_files:
                print(f"  {path}")
        elif len(result.model_files) == 1:
            print(f"\nParameter sub list: {result.model_files[0]}  "
                  f"({result.parameter_count} value(s))")
        elif result.model_files:
            print(f"\n{len(result.model_files)} parameter sub lists, merged "
                  f"({result.parameter_count} value(s)):")
            for path in result.model_files:
                print(f"  {path}")
        print(paint("\nDone.", GREEN))
    else:
        print(paint("\nCode generation was aborted because the model contains errors.",
                    BOLD + BRIGHT_RED))
        if diagnostics.count(Severity.ERROR) == 0:
            print(paint("(warnings are treated as errors)", YELLOW))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
