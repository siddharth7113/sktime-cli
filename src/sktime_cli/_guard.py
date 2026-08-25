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

from sktime_cli._errors import CliError, from_module_not_found
from sktime_cli._output import OutputFormat, print_error

FORMAT_OPT = typer.Option(
    OutputFormat.auto,
    "--format",
    envvar="SKTIME_CLI_FORMAT",
    help="Output format: auto|human|agent|json|quiet.",
)
JSON_OPT = typer.Option(False, "--json", help="Shorthand for --format json.")


def _machine_errors() -> bool:
    """Decide whether errors should be JSON rather than styled text.

    This reads ``sys.argv`` directly rather than the resolved format, because
    a command can fail before its options are parsed, and an error still has
    to obey the contract.

    Returns
    -------
    bool
        True when a machine format was asked for, or stdout is not a terminal.
    """
    argv = sys.argv[1:]
    if "--json" in argv or "--format=json" in argv or "--format=agent" in argv:
        return True
    for i, arg in enumerate(argv[:-1]):
        if arg == "--format" and argv[i + 1] in ("json", "agent"):
            return True
    return not sys.stdout.isatty()


_ROOT_VALUE_FLAGS = ("--format", "--cache-dir")


def _command_path() -> str:
    """Recover the ``<group> <command>`` string for an error object.

    Read from ``sys.argv`` for the same reason as :func:`_machine_errors`: the
    failure may predate parsing. Best-effort by nature, so callers treat an
    empty result as "unknown" rather than an error.

    Returns
    -------
    str
        Up to two non-option tokens, e.g. ``"run fit"``. Empty if there are
        none.
    """
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
    """Write one error to stderr in the form the caller can consume."""
    print_error(err.to_dict(_command_path() or None), human=not _machine_errors())


def _classify(err: Exception) -> CliError:
    """Wrap an unexpected exception, attributing it to sktime or to the CLI.

    The distinction matters to whoever reads the error: ``sktime_error`` means
    the CLI asked sktime to do something and sktime refused, while
    ``internal`` means the CLI itself broke and the report is a bug.
    Attribution is by walking the traceback for a frame inside sktime.

    Parameters
    ----------
    err : Exception
        The exception that escaped a command.

    Returns
    -------
    CliError
        Coded ``sktime_error`` or ``internal``, carrying the exception type,
        its message, and the file and line it was raised from.
    """
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
    """Turn any failure in a command into the documented error contract.

    Every command is wrapped in this. It is the single place a failure becomes
    a JSON object on stderr and a meaningful exit code, which is what lets an
    agent branch on the outcome rather than parse a traceback.

    Parameters
    ----------
    func : callable
        The command function.

    Returns
    -------
    callable
        The wrapped function. It raises ``typer.Exit`` with the code from
        :data:`sktime_cli._errors.EXIT_CODES` instead of propagating.

    Notes
    -----
    ``typer.Exit`` and ``typer.Abort`` pass through, since they are control
    flow rather than failures. Import errors get their package named by
    :func:`sktime_cli._errors.from_module_not_found`. Everything else is
    classified by :func:`_classify`; nothing escapes as a traceback.
    """

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
            cli_err = from_module_not_found(err, _command_path() or "this command")
            _emit(cli_err)
            raise typer.Exit(cli_err.exit_code) from None
        except Exception as err:  # noqa: BLE001 - the documented catch-all
            cli_err = _classify(err)
            _emit(cli_err)
            raise typer.Exit(cli_err.exit_code) from None

    return wrapper
