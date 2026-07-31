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
    """The five output formats of the CLI."""

    auto = "auto"
    human = "human"
    agent = "agent"
    json = "json"
    quiet = "quiet"


# root-level choice, set by the app callback; leaf commands may override
_root_format: OutputFormat = OutputFormat.auto


def set_root_format(fmt: OutputFormat) -> None:
    """Record the format chosen via root-level ``--format``/``--json``."""
    global _root_format
    _root_format = fmt


def resolve_format(
    leaf_format: OutputFormat = OutputFormat.auto, leaf_json: bool = False
) -> OutputFormat:
    """Resolve the effective format from leaf options, root options, and TTY."""
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
    """JSON fallback serializer for pandas/numpy scalar types."""
    if hasattr(obj, "item"):  # numpy scalars
        try:
            return obj.item()
        except (ValueError, TypeError):
            pass
    return str(obj)  # pd.Period, Timestamp, Path, classes, ...


def _dump(payload: Any) -> str:
    return json.dumps(payload, default=json_default)


def _cell(value: Any) -> str:
    """Render one value for human/agent cells."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return _dump(value)


def emit_record(
    record: dict, fmt: OutputFormat, quiet_value: Any | None = None
) -> None:
    """Emit a single result object (describe/manifest/version-style output)."""
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
    """Emit a list of result objects (search/list-style output)."""
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
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
    """Emit a pandas Series/DataFrame result (predictions, folds, data)."""
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
    """Make an index/column label JSON-friendly, keeping numbers as numbers."""
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, tuple):  # MultiIndex entry
        return [_index_label(v) for v in value]
    return str(value)


def print_error(payload: dict, human: bool) -> None:
    """Print an error object to stderr, styled for humans or JSON for machines."""
    if human:
        from rich.console import Console

        console = Console(stderr=True)
        body = payload["error"]
        console.print(f"[bold red]error[/bold red] ({body['code']}): {body['message']}")
        if body.get("hint"):
            console.print(f"[yellow]hint[/yellow]: {body['hint']}")
        if body.get("detail"):
            console.print(f"[dim]{body['detail']}[/dim]")
    else:
        print(_dump(payload), file=sys.stderr)
