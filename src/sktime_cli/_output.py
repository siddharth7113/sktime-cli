"""Output formatting: ``--format auto|human|agent|json|quiet`` dispatch.

Contract (documented in SKILL.md):
- results go to stdout, everything else (logs, warnings, errors) to stderr;
- ``json`` emits exactly one JSON document per invocation, no envelope;
- ``agent`` emits tab-separated values with a header row, never truncated;
- ``auto`` resolves to ``human`` on a TTY and ``agent`` otherwise.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any


class OutputFormat(str, Enum):
    """The five output formats of the CLI.

    Attributes
    ----------
    auto
        Resolve at runtime: ``human`` on a TTY, ``agent`` otherwise.
    human
        Rich tables, for reading in a terminal.
    agent
        Tab-separated values with a header row, never truncated.
    json
        Exactly one JSON document per invocation, with no envelope.
    quiet
        The single most useful value and nothing else, for shell capture.
    """

    auto = "auto"
    human = "human"
    agent = "agent"
    json = "json"
    quiet = "quiet"


# root-level choice, set by the app callback; leaf commands may override
_root_format: OutputFormat = OutputFormat.auto


def set_root_format(fmt: OutputFormat) -> None:
    """Record the format chosen by the root-level ``--format`` or ``--json``.

    Parameters
    ----------
    fmt : OutputFormat
        The root choice, which leaf commands fall back to when they were not
        given their own.
    """
    global _root_format
    _root_format = fmt


def resolve_format(
    leaf_format: OutputFormat = OutputFormat.auto, leaf_json: bool = False
) -> OutputFormat:
    """Resolve the format actually in force for this command.

    Precedence runs leaf option, then root option, then whether stdout is a
    terminal. Every command calls this first.

    Parameters
    ----------
    leaf_format : OutputFormat, default auto
        The subcommand's own ``--format``.
    leaf_json : bool, default False
        The subcommand's own ``--json`` shorthand.

    Returns
    -------
    OutputFormat
        A concrete format, never ``auto``.

    Raises
    ------
    CliError
        ``usage`` if ``--json`` was combined with a conflicting ``--format``.
    """
    from sktime_cli._errors import CliError

    if leaf_json and leaf_format not in (OutputFormat.auto, OutputFormat.json):
        raise CliError("usage", "cannot combine --json with --format " + leaf_format)
    fmt = OutputFormat.json if leaf_json else leaf_format
    if fmt == OutputFormat.auto:
        fmt = _root_format
    if fmt == OutputFormat.auto:
        fmt = OutputFormat.human if sys.stdout.isatty() else OutputFormat.agent
    return fmt


def json_default(obj: Any) -> Any:
    """Serialize the pandas and numpy types ``json`` does not know.

    Parameters
    ----------
    obj : Any
        A value the encoder could not handle.

    Returns
    -------
    Any
        A numpy scalar as its Python equivalent, so numbers stay numbers;
        anything else as its string form, which covers ``Period``,
        ``Timestamp``, and ``Path``.
    """
    if hasattr(obj, "item"):  # numpy scalars
        try:
            return obj.item()
        except (ValueError, TypeError):
            pass
    return str(obj)  # pd.Period, Timestamp, Path, classes, ...


def _dump(payload: Any) -> str:
    """Serialize a payload to compact JSON, tolerating pandas and numpy types."""
    return json.dumps(payload, default=json_default)


def _cell(value: Any) -> str:
    """Render one value for a human or agent table cell.

    Strings pass through so they are not quoted; everything else is JSON, so a
    nested list or dict stays machine-readable inside a flat cell.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return _dump(value)


def emit_record(
    record: dict, fmt: OutputFormat, quiet_value: Any | None = None
) -> None:
    """Write a single result object to stdout in the chosen format.

    Use this for describe, manifest, and version style output: one thing with
    named fields. For a list of such things use :func:`emit_table`, and for
    data use :func:`emit_frame`.

    Parameters
    ----------
    record : dict
        The result. Key order is preserved in every format.
    fmt : OutputFormat
        A concrete format from :func:`resolve_format`.
    quiet_value : Any, optional
        What ``quiet`` prints. When ``None``, ``quiet`` prints nothing, which
        is correct for commands whose value is their side effect.
    """
    if fmt == OutputFormat.json:
        print(_dump(record))
    elif fmt == OutputFormat.agent:
        for key, value in record.items():
            print(f"{key}\t{_cell(value)}")
    elif fmt == OutputFormat.quiet:
        if quiet_value is not None:
            print(quiet_value)
    else:  # human
        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(overflow="fold")
        for key, value in record.items():
            table.add_row(key, _cell(value))
        Console().print(table)


def emit_table(
    rows: list[dict],
    fmt: OutputFormat,
    columns: list[str] | None = None,
    quiet_key: str | None = None,
) -> None:
    """Write a list of result objects to stdout in the chosen format.

    Use this for search and list style output.

    Parameters
    ----------
    rows : list of dict
        The results. All rows should share a shape.
    fmt : OutputFormat
        A concrete format from :func:`resolve_format`.
    columns : list of str, optional
        Which keys to show, in order. Defaults to the keys of the first row.
    quiet_key : str, optional
        Which key ``quiet`` prints, one row per line, so the output pipes into
        another command. When ``None``, ``quiet`` prints nothing.

    Notes
    -----
    The human format prints a result count to stderr, keeping stdout to the
    table itself.
    """
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    if not columns and fmt == OutputFormat.agent:
        # an empty result still owes agent format a header line: a script that
        # skips line 1 must not silently consume its first row of data
        columns = ["name"]
    if fmt == OutputFormat.json:
        print(_dump(rows))
    elif fmt == OutputFormat.agent:
        print("\t".join(columns))
        for row in rows:
            print("\t".join(_cell(row.get(c)) for c in columns))
    elif fmt == OutputFormat.quiet:
        if quiet_key:
            for row in rows:
                print(row.get(quiet_key, ""))
    else:  # human
        from rich.console import Console
        from rich.table import Table

        table = Table(box=None, header_style="bold")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*(_cell(row.get(c)) for c in columns))
        Console().print(table)
        Console(stderr=True).print(f"[dim]{len(rows)} result(s)[/dim]")


def emit_frame(frame, fmt: OutputFormat, file=None) -> None:
    """Write a pandas result to stdout in the chosen format.

    Use this for data: predictions, transformed series, evaluation folds.

    Parameters
    ----------
    frame : pd.Series or pd.DataFrame
        The data. A Series is promoted to a one-column frame.
    fmt : OutputFormat
        A concrete format from :func:`resolve_format`.
    file : file-like, optional
        Where to write. Defaults to stdout.

    Notes
    -----
    The json format uses pandas "split" orient, ``{"index", "columns",
    "data"}``, which is what :func:`sktime_cli._io.read_any` reads back. The
    agent and quiet formats emit CSV, with a header only for agent.
    """
    import pandas as pd

    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    out = file or sys.stdout
    if fmt == OutputFormat.json:
        payload = {
            "index": [_index_label(i) for i in frame.index],
            "columns": [_index_label(c) for c in frame.columns],
            "data": json.loads(frame.to_json(orient="values")),
        }
        print(_dump(payload), file=out)
    elif fmt == OutputFormat.human:
        from rich.console import Console
        from rich.table import Table

        table = Table(box=None, header_style="bold")
        index_name = frame.index.name or "index"
        table.add_column(str(index_name), style="cyan")
        for col in frame.columns:
            table.add_column(str(col), justify="right")
        for idx, row in frame.iterrows():
            table.add_row(str(idx), *(_cell(v) for v in row))
        Console(file=out if file else None).print(table)
    else:  # agent and quiet: plain CSV, header only for agent
        csv = frame.to_csv(header=(fmt == OutputFormat.agent))
        out.write(csv)


def _index_label(value: Any) -> Any:
    """Make one index or column label JSON-friendly.

    Numbers stay numbers rather than becoming strings, so a consumer can index
    on them; a ``MultiIndex`` entry becomes a list.
    """
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, tuple):  # MultiIndex entry
        return [_index_label(v) for v in value]
    return str(value)


def print_error(payload: dict, human: bool) -> None:
    """Write an error to stderr, styled for a human or as JSON for a machine.

    Errors always go to stderr, whatever the output format, so a caller
    reading stdout gets either a result or nothing.

    Parameters
    ----------
    payload : dict
        The envelope from :meth:`sktime_cli._errors.CliError.to_dict`.
    human : bool
        Render with colour and labels rather than as JSON.
    """
    if human:
        from rich.console import Console
        from rich.markup import escape

        console = Console(stderr=True)
        body = payload["error"]
        # Escape every interpolated field. Error text carries square brackets
        # routinely, in package extras such as sktime[dev] and in spec strings
        # such as fh=[1,2,3], and Rich would read those as markup tags and
        # drop them. A hint that silently loses an extra is worse than no hint.
        console.print(
            f"[bold red]error[/bold red] ({escape(body['code'])}): "
            f"{escape(body['message'])}"
        )
        if body.get("hint"):
            console.print(f"[yellow]hint[/yellow]: {escape(body['hint'])}")
        if body.get("detail"):
            console.print(f"[dim]{escape(body['detail'])}[/dim]")
    else:
        print(_dump(payload), file=sys.stderr)
