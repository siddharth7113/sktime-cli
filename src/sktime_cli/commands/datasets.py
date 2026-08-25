"""``sktime-cli datasets``: list and fetch datasets (mirrors list_available_data)."""

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
    source: str | None = typer.Option(None, "--source", help="builtin|ucr|tsf|fpp3."),
    task: str | None = typer.Option(
        None, "--task", help="forecaster|classifier|regressor (sktime scitype names)."
    ),
    name: str | None = typer.Option(
        None, "--name", "-n", help="Substring match on dataset name."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """List available datasets across all sources."""
    fmt = resolve_format(format_, json_)
    if source not in (None, "builtin", *_datasets.REMOTE_SOURCES):
        raise CliError(
            "usage", f"unknown --source {source!r}: use builtin|ucr|tsf|fpp3"
        )
    tasks = _datasets.known_tasks()
    if task is not None and task not in tasks:
        raise CliError(
            "usage",
            f"unknown --task {task!r}",
            hint=f"use one of: {', '.join(tasks)}",
        )
    rows = _datasets.listing(source=source, task=task, contains=name)
    emit_table(
        rows,
        fmt,
        columns=["name", "source", "task", "offline", "installable"],
        quiet_key="name",
    )


@app.command("describe")
@handle_errors
def describe(
    name: str = typer.Argument(..., help="Dataset id, e.g. airline or ucr:ArrowHead."),
    no_load: bool = typer.Option(
        False,
        "--no-load",
        help="Report tag metadata only, without loading the data.",
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Describe a dataset: task, shape, and tag metadata."""
    fmt = resolve_format(format_, json_)
    source, canonical = _datasets.resolve(name)
    record: dict = {"name": canonical, "source": _datasets.display_source(source)}

    if source in _datasets.REMOTE_SOURCES:
        record["task"] = "classifier" if source == "ucr" else "forecaster"
        record["note"] = "remote dataset; fetch it with: sktime-cli datasets load " + (
            f"{source}:{canonical}"
        )
        emit_record(record, fmt, quiet_value=canonical)
        return

    if source == "object":
        # dataset objects carry shape, frequency and split counts as tags, so
        # the description is answerable from metadata alone
        entry = _datasets.object_index()[canonical]
        record["task"] = _datasets.task_of(entry)
        record["installable"] = entry.get("installable", True)
        if entry.get("python_dependencies"):
            record["python_dependencies"] = entry["python_dependencies"]
        record.update(_datasets.describe_tags(entry))
        if no_load or not record["installable"]:
            emit_record(record, fmt, quiet_value=canonical)
            return
    elif no_load:
        emit_record(record, fmt, quiet_value=canonical)
        return

    loaded = _datasets.load(source, canonical)
    record["task"] = loaded["task"]
    if "y" in loaded and loaded["task"] == "forecaster":
        y = loaded["y"]
        record["shape"] = list(getattr(y, "shape", [len(y)]))
        record["index_type"] = type(y.index).__name__
    if "X" in loaded and loaded["X"] is not None:
        X = loaded["X"]
        record["X_shape"] = list(X.shape)
    if "y" in loaded and loaded["task"] in ("classifier", "regressor"):
        import pandas as pd

        y = pd.Series(loaded["y"])
        record["n_instances"] = int(len(y))
        if loaded["task"] == "classifier":
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

    default_ext = "ts" if task in ("classifier", "regressor") else "csv"
    ext = (file_format or default_ext).lower()
    if output is None:
        stem = (
            canonical
            if source not in _datasets.REMOTE_SOURCES
            else f"{source}_{canonical}"
        )
        output = (output_dir or Path.cwd()) / f"{stem}.{ext}"

    files: list[str] = []
    manifest: dict = {
        "dataset": canonical,
        "source": _datasets.display_source(source),
        "task": task,
    }

    if task in ("classifier", "regressor"):
        X, y = loaded["X"], loaded["y"]
        if ext == "ts":
            files += _io.write_any(X, output, "ts", y=y)
        else:
            # non-.ts formats cannot hold nested panels or carry labels inline:
            # flatten to long form, and write y beside X
            from sktime.datatypes import convert_to

            files += _io.write_any(convert_to(X, to_type="pd-multiindex"), output, ext)
            if y is not None:
                import pandas as pd

                labels = output.with_name(output.stem + "_y" + output.suffix)
                files += _io.write_any(pd.Series(y, name="target"), labels, ext)
                manifest["labels"] = str(labels)
        manifest["n_instances"] = int(len(X))
        import pandas as pd

        if task == "classifier":
            manifest["classes"] = sorted(str(c) for c in pd.Series(y).unique())
    else:
        y = loaded["y"]
        import pandas as pd

        if isinstance(y.index, pd.MultiIndex):
            # long layout, but still in the format that was asked for
            files += _io.write_any(y, output, ext)
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
