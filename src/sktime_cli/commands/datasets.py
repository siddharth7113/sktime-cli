"""``sktime-cli datasets`` — list and fetch datasets (mirrors list_available_data)."""

from __future__ import annotations

from pathlib import Path

import typer

from sktime_cli import _datasets, _io
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._output import OutputFormat, emit_record, emit_table, resolve_format

app = typer.Typer(no_args_is_help=True)


@app.command("list")
@handle_errors
def list_(
    source: str | None = typer.Option(
        None, "--source", help="builtin|ucr|tsf|fpp3|objects."
    ),
    task: str | None = typer.Option(
        None, "--task", help="forecasting|classification|regression."
    ),
    name: str | None = typer.Option(
        None, "--name", "-n", help="Substring match on dataset name."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """List available datasets across all sources."""
    fmt = resolve_format(format_, json_)
    if source not in (None, "builtin", "ucr", "tsf", "fpp3", "objects"):
        raise CliError(
            "usage", f"unknown --source {source!r}: use builtin|ucr|tsf|fpp3|objects"
        )
    rows = _datasets.listing(source=source, task=task, contains=name)
    emit_table(
        rows, fmt, columns=["name", "source", "task", "offline"], quiet_key="name"
    )


@app.command("describe")
@handle_errors
def describe(
    name: str = typer.Argument(..., help="Dataset id, e.g. airline or ucr:ArrowHead."),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Describe a dataset: task, shape, and metadata (no download for remote)."""
    fmt = resolve_format(format_, json_)
    source, canonical = _datasets.resolve(name)
    record: dict = {"name": canonical, "source": source}

    if source != "builtin":
        record["task"] = "classification" if source == "ucr" else "forecasting"
        record["note"] = "remote dataset; fetch it with: sktime-cli datasets load " + (
            f"{source}:{canonical}"
        )
        emit_record(record, fmt, quiet_value=canonical)
        return

    loaded = _datasets.load(source, canonical)
    record["task"] = loaded["task"]
    if "y" in loaded and loaded["task"] == "forecasting":
        y = loaded["y"]
        record["shape"] = list(getattr(y, "shape", [len(y)]))
        record["index_type"] = type(y.index).__name__
    if "X" in loaded and loaded["X"] is not None:
        X = loaded["X"]
        record["X_shape"] = list(X.shape)
    if "y" in loaded and loaded["task"] in ("classification", "regression"):
        import pandas as pd

        y = pd.Series(loaded["y"])
        record["n_instances"] = int(len(y))
        if loaded["task"] == "classification":
            record["classes"] = sorted(str(c) for c in y.unique())
    emit_record(record, fmt, quiet_value=canonical)


@app.command("load")
@handle_errors
def load(
    name: str = typer.Argument(..., help="Dataset id, e.g. airline or ucr:ArrowHead."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (default: <name>.<ext> in cwd)."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Directory for default-named output files."
    ),
    split: str | None = typer.Option(
        None, "--split", help="train|test (classification datasets with splits)."
    ),
    file_format: str | None = typer.Option(
        None, "--file-format", help="csv|parquet|json|ts (default by task)."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Fetch a dataset and write it to a file; prints a JSON manifest."""
    fmt = resolve_format(format_, json_)
    if split and split.lower() not in ("train", "test"):
        raise CliError("usage", f"--split must be train or test, got {split!r}")
    source, canonical = _datasets.resolve(name)
    loaded = _datasets.load(source, canonical, split=split)
    task = loaded["task"]

    default_ext = "ts" if task in ("classification", "regression") else "csv"
    ext = (file_format or default_ext).lower()
    if output is None:
        stem = canonical if source == "builtin" else f"{source}_{canonical}"
        output = (output_dir or Path.cwd()) / f"{stem}.{ext}"

    files: list[str] = []
    manifest: dict = {"dataset": canonical, "source": source, "task": task}

    if task in ("classification", "regression"):
        X, y = loaded["X"], loaded["y"]
        if ext == "ts":
            files += _io.write_any(X, output, "ts", y=y)
        else:
            raise CliError(
                "usage",
                f"{task} datasets are panels; only --file-format ts is "
                "supported in v0.0.1",
            )
        manifest["n_instances"] = int(len(X))
        import pandas as pd

        if task == "classification":
            manifest["classes"] = sorted(str(c) for c in pd.Series(y).unique())
    else:
        y = loaded["y"]
        import pandas as pd

        if isinstance(y.index, pd.MultiIndex):
            frame = y.reset_index()
            frame.to_csv(output, index=False)
            files.append(str(output))
            manifest["layout"] = "long"
        else:
            files += _io.write_any(y, output, ext)
        if loaded.get("X") is not None:
            x_path = output.with_name(output.stem + "_X" + output.suffix)
            files += _io.write_any(loaded["X"], x_path, ext)
        manifest["shape"] = list(getattr(y, "shape", [len(y)]))
        if "metadata" in loaded:
            manifest["metadata"] = loaded["metadata"]

    manifest["files"] = files
    emit_record(manifest, fmt, quiet_value=files[0] if files else None)
