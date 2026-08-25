"""``sktime-cli data``: inspect, convert, split data files (mirrors inspect_data)."""

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
        False, "--long", help="Long-format panel; requires --id-col and --time-col."
    ),
    "id_col": typer.Option(None, "--id-col", help="Instance id column (long format)."),
    "time_col": typer.Option(None, "--time-col", help="Time column (long format)."),
}

# `scitype` and `mtype` are reported as top-level fields, so they are not
# repeated inside the metadata block. Everything else the check returns is
# passed through, so a field added upstream appears without a change here.
_PROMOTED_METADATA = ("scitype", "mtype")


def _scitype_check(obj):
    """Ask sktime to classify an object and describe it.

    Parameters
    ----------
    obj : pd.Series or pd.DataFrame
        The data to classify.

    Returns
    -------
    dict
        sktime's metadata, including ``scitype``, ``mtype``, and whatever
        descriptive fields the check computed.

    Raises
    ------
    CliError
        ``data_error`` when the object is not a recognized sktime container,
        carrying sktime's own explanation.
    """
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
        "metadata": {
            key: value
            for key, value in sorted(meta.items())
            if key not in _PROMOTED_METADATA
        },
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
        None,
        "--to",
        help=(
            "Output file format: csv|parquet|json|ts. "
            "npy works only with --to-mtype numpy3D."
        ),
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
    cv: str | None = typer.Option(
        None,
        "--cv",
        help='Splitter spec for k-fold output, e.g. "ExpandingWindowSplitter(fh=6)".',
    ),
    exog: Path | None = typer.Option(
        None, "--exog", help="Exogenous data file split alongside y."
    ),
    train_out: Path | None = typer.Option(
        None, "--train-out", help="Train output path (default: <stem>_train<suffix>)."
    ),
    test_out: Path | None = typer.Option(
        None, "--test-out", help="Test output path (default: <stem>_test<suffix>)."
    ),
    input_format: str | None = INPUT_OPTS["input_format"],
    index_col: str = INPUT_OPTS["index_col"],
    freq: str | None = INPUT_OPTS["freq"],
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Split a series into train/test files, or into cross-validation folds."""
    from sktime.split import temporal_train_test_split

    fmt = resolve_format(format_, json_)
    if cv and (fh or test_size or train_size):
        raise CliError(
            "usage", "--cv produces folds; it cannot be combined with --fh/--*-size"
        )
    if not cv:
        if fh and test_size:
            raise CliError("usage", "--fh and --test-size are mutually exclusive")
        if not (fh or test_size or train_size):
            raise CliError("usage", "pass --test-size, --train-size, --fh, or --cv")

    data = _io.read_any(path, input_format=input_format, index_col=index_col, freq=freq)
    y = data.obj
    if cv:
        _emit_folds(y, cv, path, train_out, test_out, fmt)
        return
    X = _io.read_any(exog, index_col=index_col, freq=freq).obj if exog else None

    kwargs = {
        "test_size": _io.parse_size(test_size),
        "train_size": _io.parse_size(train_size),
        "fh": _io.parse_fh(fh) if fh else None,
    }
    for flag, value in (
        ("--test-size", kwargs["test_size"]),
        ("--train-size", kwargs["train_size"]),
    ):
        _check_size(flag, value, len(y))
    if X is not None:
        if not len(y.index.intersection(X.index)):
            raise CliError(
                "data_error",
                "the --exog file does not cover the same index as the input series",
                hint="both files must span the same periods",
                detail=(
                    f"{path.name} spans {y.index[0]}..{y.index[-1]}, "
                    f"{exog.name} spans {X.index[0]}..{X.index[-1]}"
                ),
            )
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


def _check_size(flag: str, value, n_obs: int) -> None:
    """Reject a split size that cannot produce two non-empty parts.

    ``temporal_train_test_split`` accepts a size larger than the series and a
    negative one, writing an empty train file at exit 0 either way, which is
    silent data loss rather than a split.

    Parameters
    ----------
    flag : str
        The option being checked, named in the error.
    value : int, float or None
        The parsed size. ``None`` means the option was not given.
    n_obs : int
        Length of the series being split.

    Raises
    ------
    CliError
        ``usage`` when the size is not a positive count inside the series, or
        not a fraction strictly between 0 and 1.
    """
    if value is None:
        return
    if isinstance(value, float):
        if not 0 < value < 1:
            raise CliError(
                "usage",
                f"{flag} as a fraction must be between 0 and 1, got {value}",
            )
        return
    if value < 1:
        raise CliError("usage", f"{flag} must be 1 or more, got {value}")
    if value >= n_obs:
        raise CliError(
            "usage",
            f"{flag} is {value} but the series has only {n_obs} observations",
            hint="leave room for both parts, or pass a fraction such as 0.2",
        )


def _emit_folds(y, cv: str, path: Path, train_out, test_out, fmt: OutputFormat) -> None:
    """Write one train/test file pair per cross-validation fold.

    Parameters
    ----------
    y : pd.Series or pd.DataFrame
        The series to split.
    cv : str
        A splitter spec.
    path : Path
        The input file, used to name the outputs.
    train_out, test_out : Path or None
        Stems for the output names, defaulting to the input's.
    fmt : OutputFormat
        A concrete format from :func:`resolve_format`.

    Raises
    ------
    CliError
        ``usage`` if the spec is not a splitter; ``data_error`` if the
        splitter produced no folds, which usually means the window is larger
        than the series.
    """
    from sktime_cli._specs import build_estimator

    splitter = build_estimator(cv)
    if not hasattr(splitter, "split"):
        raise CliError(
            "usage",
            f"--cv needs a splitter, got {type(splitter).__name__}",
            hint="list splitters with: sktime-cli registry search splitter",
        )

    suffix = path.suffix or ".csv"
    train_stem = Path(train_out).with_suffix("") if train_out else path.with_suffix("")
    test_stem = Path(test_out).with_suffix("") if test_out else path.with_suffix("")

    folds, files = [], []
    for i, (train_idx, test_idx) in enumerate(splitter.split(y)):
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        train_path = train_stem.with_name(f"{train_stem.name}_fold{i}_train{suffix}")
        test_path = test_stem.with_name(f"{test_stem.name}_fold{i}_test{suffix}")
        written = _io.write_any(y_train, train_path) + _io.write_any(y_test, test_path)
        files += written
        folds.append(
            {
                "fold": i,
                "n_train": int(len(y_train)),
                "n_test": int(len(y_test)),
                "train": str(train_path),
                "test": str(test_path),
            }
        )

    if not folds:
        raise CliError(
            "data_error",
            f"{type(splitter).__name__} produced no folds for {len(y)} observations",
            hint="lower initial_window, or use a shorter horizon",
        )
    emit_record(
        {
            "splitter": str(splitter),
            "n_folds": len(folds),
            "folds": folds,
            "files": files,
        },
        fmt,
        quiet_value="\n".join(f["train"] + " " + f["test"] for f in folds),
    )
