"""``sktime-cli data`` — inspect, convert, split data files (mirrors inspect_data)."""

from __future__ import annotations

from pathlib import Path

import typer

from sktime_cli import _io
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._output import OutputFormat, emit_record, resolve_format

app = typer.Typer(no_args_is_help=True)

INPUT_OPTS = {
    "input_format": typer.Option(
        None,
        "--input-format",
        help="Override format inference: csv|parquet|json|ts|tsf|arff.",
    ),
    "index_col": typer.Option(
        "auto", "--index-col", help="Time index column name, or 'none'."
    ),
    "freq": typer.Option(
        None, "--freq", help="Pandas frequency for the index, e.g. M, D."
    ),
    "long": typer.Option(
        False, "--long", help="Long-format panel: needs --id-col/--time-col."
    ),
    "id_col": typer.Option(None, "--id-col", help="Instance id column (long format)."),
    "time_col": typer.Option(None, "--time-col", help="Time column (long format)."),
}

_METADATA_KEYS = [
    "is_univariate",
    "n_features",
    "feature_names",
    "is_equally_spaced",
    "has_nans",
    "n_instances",
    "n_panels",
    "is_one_series",
]


def _scitype_check(obj):
    from sktime.datatypes import check_is_scitype

    valid, msg, meta = check_is_scitype(
        obj, ["Series", "Panel", "Hierarchical"], return_metadata=True
    )
    if not valid:
        raise CliError("data_error", f"not a recognized sktime data container: {msg}")
    return meta


@app.command("inspect")
@handle_errors
def inspect(
    path: Path = typer.Argument(..., help="Data file to inspect."),
    input_format: str | None = INPUT_OPTS["input_format"],
    index_col: str = INPUT_OPTS["index_col"],
    freq: str | None = INPUT_OPTS["freq"],
    long: bool = INPUT_OPTS["long"],
    id_col: str | None = INPUT_OPTS["id_col"],
    time_col: str | None = INPUT_OPTS["time_col"],
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Report scitype, mtype, and metadata of a data file."""
    fmt = resolve_format(format_, json_)
    data = _io.read_any(
        path,
        input_format=input_format,
        index_col=index_col,
        freq=freq,
        long=long,
        id_col=id_col,
        time_col=time_col,
    )
    meta = _scitype_check(data.obj)
    record = {
        "path": str(path),
        "scitype": meta.get("scitype"),
        "mtype": meta.get("mtype"),
        "shape": list(getattr(data.obj, "shape", [len(data.obj)])),
        "metadata": {k: meta[k] for k in _METADATA_KEYS if k in meta},
    }
    index = data.obj.index
    record["index"] = {
        "type": type(index).__name__,
        "dtype": str(index.dtype),
        "start": str(index[0]) if len(index) else None,
        "end": str(index[-1]) if len(index) else None,
    }
    if data.y is not None:
        import pandas as pd

        labels = pd.Series(data.y)
        record["labels"] = {
            "n": int(len(labels)),
            "classes": sorted(str(c) for c in labels.unique()),
        }
    emit_record(record, fmt, quiet_value=record["mtype"])


@app.command("convert")
@handle_errors
def convert(
    path: Path = typer.Argument(..., help="Input data file."),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path."),
    to: str | None = typer.Option(
        None, "--to", help="Output file format: csv|parquet|json|ts|npy."
    ),
    to_mtype: str | None = typer.Option(
        None, "--to-mtype", help="Convert to an sktime mtype first, e.g. pd-multiindex."
    ),
    input_format: str | None = INPUT_OPTS["input_format"],
    index_col: str = INPUT_OPTS["index_col"],
    freq: str | None = INPUT_OPTS["freq"],
    long: bool = INPUT_OPTS["long"],
    id_col: str | None = INPUT_OPTS["id_col"],
    time_col: str | None = INPUT_OPTS["time_col"],
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Convert a data file between formats and/or sktime mtypes."""
    fmt = resolve_format(format_, json_)
    data = _io.read_any(
        path,
        input_format=input_format,
        index_col=index_col,
        freq=freq,
        long=long,
        id_col=id_col,
        time_col=time_col,
    )
    obj = data.obj
    if to_mtype:
        from sktime.datatypes import convert_to

        try:
            obj = convert_to(obj, to_type=to_mtype)
        except Exception as err:
            raise CliError(
                "data_error", f"mtype conversion to {to_mtype!r} failed: {err}"
            ) from err
    files = _io.write_any(obj, output, to, y=data.y)
    emit_record(
        {"input": str(path), "files": files, "mtype": to_mtype, "format": to},
        fmt,
        quiet_value=files[0],
    )


@app.command("split")
@handle_errors
def split(
    path: Path = typer.Argument(..., help="Input series file (csv/parquet/json)."),
    test_size: str | None = typer.Option(
        None, "--test-size", help="Test size: int count or 0.x fraction."
    ),
    train_size: str | None = typer.Option(
        None, "--train-size", help="Train size: int count or 0.x fraction."
    ),
    fh: str | None = typer.Option(
        None, "--fh", help="Forecasting horizon to size the test set, e.g. 1:12."
    ),
    exog: Path | None = typer.Option(
        None, "--exog", help="Exogenous data file split alongside y."
    ),
    train_out: Path | None = typer.Option(None, "--train-out"),
    test_out: Path | None = typer.Option(None, "--test-out"),
    input_format: str | None = INPUT_OPTS["input_format"],
    index_col: str = INPUT_OPTS["index_col"],
    freq: str | None = INPUT_OPTS["freq"],
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Split a series temporally into train and test files."""
    from sktime.split import temporal_train_test_split

    fmt = resolve_format(format_, json_)
    if fh and test_size:
        raise CliError("usage", "--fh and --test-size are mutually exclusive")
    if not (fh or test_size or train_size):
        raise CliError("usage", "pass --test-size, --train-size, or --fh")

    data = _io.read_any(path, input_format=input_format, index_col=index_col, freq=freq)
    y = data.obj
    X = _io.read_any(exog, index_col=index_col, freq=freq).obj if exog else None

    kwargs = {
        "test_size": _io.parse_size(test_size),
        "train_size": _io.parse_size(train_size),
        "fh": _io.parse_fh(fh) if fh else None,
    }
    if X is not None:
        y_train, y_test, X_train, X_test = temporal_train_test_split(y, X=X, **kwargs)
    else:
        y_train, y_test = temporal_train_test_split(y, **kwargs)

    suffix = path.suffix or ".csv"
    train_out = train_out or path.with_name(path.stem + "_train" + suffix)
    test_out = test_out or path.with_name(path.stem + "_test" + suffix)
    files = _io.write_any(y_train, train_out) + _io.write_any(y_test, test_out)
    record = {
        "train": str(train_out),
        "test": str(test_out),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }
    if X is not None:
        x_suffix = exog.suffix or ".csv"
        x_train_out = exog.with_name(exog.stem + "_train" + x_suffix)
        x_test_out = exog.with_name(exog.stem + "_test" + x_suffix)
        files += _io.write_any(X_train, x_train_out) + _io.write_any(X_test, x_test_out)
        record["exog_train"] = str(x_train_out)
        record["exog_test"] = str(x_test_out)
    record["files"] = files
    emit_record(record, fmt, quiet_value=f"{train_out} {test_out}")
