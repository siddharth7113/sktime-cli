"""Shared command decorator and reusable option definitions.

``handle_errors`` is the single choke point turning any failure into the
documented stderr contract + exit code, both under the console script and
under ``typer.testing.CliRunner``.
"""

from __future__ import annotations

import functools
import os
import sys
import traceback
from importlib.util import find_spec

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

    This reads ``sys.argv`` directly rather than the resolved format, because a
    command can fail before its options are parsed, and an error still has to
    obey the contract.

    Returns
    -------
    bool
        True when a machine format was asked for, or when nothing was asked for
        and stdout is not a terminal. An explicit ``--format human`` wins over
        the terminal check, so redirecting human output to a file still gets
        human errors.
    """
    requested = _requested_format()
    if requested is not None:
        return requested in ("json", "agent")
    return not sys.stdout.isatty()


def _requested_format() -> str | None:
    """Return the format named on the command line, if one was.

    Returns
    -------
    str or None
        The format name, or ``None`` when the caller did not choose one and the
        terminal should decide.
    """
    argv = sys.argv[1:]
    if "--json" in argv:
        return "json"
    for i, arg in enumerate(argv):
        if arg.startswith("--format="):
            return arg.split("=", 1)[1]
        if arg == "--format" and i + 1 < len(argv):
            return argv[i + 1]
    return None


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


@functools.lru_cache(maxsize=1)
def _sktime_root() -> str | None:
    """Locate the directory sktime is imported from.

    Returns
    -------
    str or None
        The absolute, normalised path of sktime's package directory, or None
        if sktime cannot be located.
    """
    try:
        spec = find_spec("sktime")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    return os.path.normcase(os.path.dirname(os.path.abspath(spec.origin)))


def _in_sktime(filename: str) -> bool:
    """Report whether a traceback frame was raised from inside sktime.

    Containment is tested against sktime's real package directory rather than
    by looking for ``"sktime"`` in the path. A substring test misreads any
    frame whose path merely passes through a directory named after sktime, and
    installing the CLI under a directory called ``sktime_cli`` does exactly
    that: every genuine sktime frame in the virtualenv below it then looks like
    CLI code and gets reported as an internal bug.

    Parameters
    ----------
    filename : str
        A traceback frame's filename.

    Returns
    -------
    bool
        True when the frame lies inside sktime's package directory.
    """
    root = _sktime_root()
    if root is None:
        return False
    path = os.path.normcase(os.path.abspath(filename))
    return path == root or path.startswith(root + os.sep)


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
    from_sktime = any(_in_sktime(frame.filename) for frame in frames)
    where = frames[-1] if frames else None
    return CliError(
        code="sktime_error" if from_sktime else "internal",
        message=f"{type(err).__name__}: {err}",
        detail=f"raised at {where.filename}:{where.lineno}" if where else None,
    )


def install_usage_error_contract() -> None:
    """Make Click's own usage errors obey the CLI's error contract.

    An unknown option or a missing argument is rejected before the command
    function runs, so ``handle_errors`` never sees it and the failure printed as
    styled text even under ``--json``. That broke the promise that every failure
    is one JSON object on stderr, for exactly the errors an agent hits most
    while learning the surface.

    Typer renders these through ``rich_utils.rich_format_error`` when rich is
    installed, and through ``UsageError.show`` otherwise, so both are wrapped.
    Human output is unchanged: the originals still run whenever the format is
    not a machine one.
    """
    _patch_rich_format_error()
    _patch_usage_error_show()


def _usage_error_payload(err) -> dict:
    """Build the error envelope for a Click usage error."""
    message = err.format_message() if hasattr(err, "format_message") else str(err)
    code = "usage" if getattr(err, "exit_code", 2) == 2 else "internal"
    command = getattr(getattr(err, "ctx", None), "command_path", None)
    return CliError(code, message).to_dict(_command_path() or command)


def _patch_rich_format_error() -> None:
    """Wrap Typer's rich error renderer, which is used when rich is installed."""
    try:
        from typer import rich_utils
    except ImportError:  # pragma: no cover - rich is a hard dependency of typer
        return
    if getattr(rich_utils.rich_format_error, "_sktime_cli_patched", False):
        return
    original = rich_utils.rich_format_error

    def rich_format_error(err, *args, **kwargs):
        if not _machine_errors():
            return original(err, *args, **kwargs)
        print_error(_usage_error_payload(err), human=False)
        return None

    rich_format_error._sktime_cli_patched = True
    rich_utils.rich_format_error = rich_format_error


def _patch_usage_error_show() -> None:
    """Wrap the plain Click renderer, used when rich markup is switched off.

    Typer only vendors Click as ``typer._click`` from 0.26, and the declared
    floor is older, so this import has to be optional. Nothing is lost when it
    is missing: the rich renderer above is the one Typer actually calls, and it
    has existed for far longer.
    """
    try:
        from typer._click.exceptions import UsageError
    except ImportError:  # typer < 0.26 does not vendor click
        return

    if getattr(UsageError, "_sktime_cli_patched", False):
        return
    original = UsageError.show

    def show(self, file=None):
        if not _machine_errors():
            return original(self, file)
        print_error(_usage_error_payload(self), human=False)
        return None

    UsageError.show = show
    UsageError._sktime_cli_patched = True


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
