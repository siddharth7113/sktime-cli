"""Shared command decorator and reusable option definitions.

``handle_errors`` is the single choke point turning any failure into the
documented stderr contract + exit code, both under the console script and
under ``typer.testing.CliRunner``.
"""

from __future__ import annotations

import functools
import sys
import traceback

import typer

from sktime_cli._errors import CliError
from sktime_cli._output import OutputFormat, print_error

FORMAT_OPT = typer.Option(
    OutputFormat.auto,
    "--format",
    envvar="SKTIME_CLI_FORMAT",
    help="Output format: auto|human|agent|json|quiet.",
)
JSON_OPT = typer.Option(False, "--json", help="Shorthand for --format json.")


def _machine_errors() -> bool:
    """Decide if errors should be JSON: explicit machine format, or no TTY."""
    argv = sys.argv[1:]
    if "--json" in argv or "--format=json" in argv or "--format=agent" in argv:
        return True
    for i, arg in enumerate(argv[:-1]):
        if arg == "--format" and argv[i + 1] in ("json", "agent"):
            return True
    return not sys.stdout.isatty()


_ROOT_VALUE_FLAGS = ("--format", "--cache-dir")


def _command_path() -> str:
    """Best-effort ``<group> <command>`` string for error objects, from argv."""
    tokens: list[str] = []
    skip_next = False
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("-"):
            skip_next = arg in _ROOT_VALUE_FLAGS
            continue
        tokens.append(arg)
        if len(tokens) == 2:
            break
    return " ".join(tokens)


def _emit(err: CliError) -> None:
    print_error(err.to_dict(_command_path() or None), human=not _machine_errors())


def _classify(err: Exception) -> CliError:
    """Wrap an unexpected exception, attributing sktime-internal failures."""
    frames = traceback.extract_tb(err.__traceback__)
    from_sktime = any(
        "sktime" in frame.filename and "sktime_cli" not in frame.filename
        for frame in frames
    )
    where = frames[-1] if frames else None
    return CliError(
        code="sktime_error" if from_sktime else "internal",
        message=f"{type(err).__name__}: {err}",
        detail=f"raised at {where.filename}:{where.lineno}" if where else None,
    )


def handle_errors(func):
    """Decorate a command: CliError and unexpected errors -> contract output."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (typer.Exit, typer.Abort):
            raise
        except CliError as err:
            _emit(err)
            raise typer.Exit(err.exit_code) from None
        except ModuleNotFoundError as err:
            cli_err = CliError(
                code="missing_dependency",
                message=f"missing package: {err.name}",
                hint=f"uv pip install {err.name}",
            )
            _emit(cli_err)
            raise typer.Exit(cli_err.exit_code) from None
        except Exception as err:  # noqa: BLE001 - the documented catch-all
            cli_err = _classify(err)
            _emit(cli_err)
            raise typer.Exit(cli_err.exit_code) from None

    return wrapper
