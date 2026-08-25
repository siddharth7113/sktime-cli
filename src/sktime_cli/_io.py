"""Time series file IO: csv/parquet/json plus sktime's .ts/.tsf/.arff readers.

Conventions (documented in SKILL.md):
- wide CSV: first column is the time index (override with --index-col);
  datetime-like indexes become PeriodIndex when a frequency is given or
  inferable; a single remaining column is squeezed to a Series;
- long CSV (--long): --id-col/--time-col become a pandas MultiIndex
  (sktime's pd-multiindex Panel mtype);
- JSON files use pandas "split" orient: {"index", "columns", "data"};
- .ts files carry X and optional class labels y.

sktime itself has no csv/parquet ingestion; this module owns that layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

from sktime_cli._errors import CliError, missing_dependency


class ReadData(NamedTuple):
    """Result of reading a data file."""

    obj: Any  # Series/DataFrame (Series scitype) or Panel/Hierarchical frame
    y: Any | None  # class labels when the file carries them (.ts/.arff)
    kind: str  # "series" | "panel" | "hierarchical"


def _read_tabular(path: Path, input_format: str | None):
    import pandas as pd

    suffix = (input_format or path.suffix.lstrip(".")).lower()
    if suffix == "csv":
        return pd.read_csv(path)
    if suffix == "parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as err:
            raise missing_dependency("reading parquet", "pyarrow") from err
    if suffix == "json":
        payload = json.loads(path.read_text())
        try:
            return pd.DataFrame(
                payload["data"], index=payload["index"], columns=payload["columns"]
            )
        except (KeyError, TypeError) as err:
            raise CliError(
                "data_error",
                f"{path}: JSON must use pandas 'split' orient "
                '({"index": [...], "columns": [...], "data": [[...]]})',
            ) from err
    raise CliError("usage", f"unsupported file format: {suffix}")


def _coerce_index(index, freq: str | None):
    """Coerce a string index (from JSON) back to int/Period/Datetime."""
    import pandas as pd

    try:
        return pd.Index([int(v) for v in index])
    except (ValueError, TypeError):
        pass
    try:
        converted = pd.DatetimeIndex(pd.to_datetime(list(index)))
    except (ValueError, TypeError):
        return index
    try:
        return converted.to_period(freq) if freq else converted.to_period()
    except ValueError:
        return converted


def _set_time_index(df, index_col: str, freq: str | None):
    """Turn the index column into a Range/Period/Datetime index."""
    import pandas as pd

    if index_col == "none":
        return df
    if index_col in ("auto", None, ""):
        col = df.columns[0]
    elif index_col in df.columns:
        col = index_col
    else:
        raise CliError("not_found", f"index column {index_col!r} not in file")

    series = df[col]
    if pd.api.types.is_integer_dtype(series):
        return df.set_index(col)
    try:
        idx = pd.to_datetime(series)
    except (ValueError, TypeError):
        if index_col in ("auto", None, ""):
            return df  # first column is not time-like: keep RangeIndex
        raise CliError(
            "data_error", f"index column {col!r} is neither integer nor datetime"
        ) from None
    df = df.drop(columns=[col]).set_index(pd.DatetimeIndex(idx, name=col))
    try:
        df.index = df.index.to_period(freq) if freq else df.index.to_period()
    except ValueError:
        if freq:
            raise CliError("data_error", f"cannot apply frequency {freq!r}") from None
        # frequency not inferable: DatetimeIndex is fine for most estimators
    return df


def _coerce_time_level(series, freq: str | None):
    """Coerce a long-format time column to an sktime-valid time index level."""
    import pandas as pd

    if pd.api.types.is_integer_dtype(series):
        return series
    try:
        stamps = pd.to_datetime(series)
    except (ValueError, TypeError):
        raise CliError(
            "data_error",
            f"time column {series.name!r} is neither integer nor datetime",
            hint="pass --time-col to name the right column",
        ) from None
    try:
        return stamps.dt.to_period(freq) if freq else stamps.dt.to_period()
    except (ValueError, AttributeError):
        # frequency not inferable: a DatetimeIndex level is valid for sktime too
        return stamps


def _read_long(df, id_col: str | None, time_col: str | None, freq: str | None):
    """Build a MultiIndex Panel/Hierarchical frame from long-format rows.

    ``--id-col`` accepts a comma-separated list; more than one id level makes
    the result Hierarchical rather than Panel.
    """
    id_cols = (
        [c.strip() for c in id_col.split(",") if c.strip()]
        if id_col
        else [str(df.columns[0])]
    )
    time_col = time_col or str(df.columns[len(id_cols)])
    for col in [*id_cols, time_col]:
        if col not in df.columns:
            raise CliError(
                "not_found",
                f"column {col!r} not in file",
                hint=f"available columns: {', '.join(map(str, df.columns))}",
            )
    df = df.copy()
    df[time_col] = _coerce_time_level(df[time_col], freq)
    df = df.set_index([*id_cols, time_col]).sort_index()
    return ReadData(df, None, "panel" if len(id_cols) == 1 else "hierarchical")


def read_any(
    path: str | Path,
    input_format: str | None = None,
    index_col: str = "auto",
    freq: str | None = None,
    long: bool = False,
    id_col: str | None = None,
    time_col: str | None = None,
) -> ReadData:
    """Read a data file into a pandas object in an sktime-compatible mtype."""
    path = Path(path)
    if not path.exists():
        raise CliError("not_found", f"file not found: {path}")
    suffix = (input_format or path.suffix.lstrip(".")).lower()

    if suffix == "ts":
        from sktime.datasets import load_from_tsfile

        X, y = load_from_tsfile(str(path), return_y=True)
        return ReadData(X, y, "panel")
    if suffix == "arff":
        from sktime.datasets import load_from_arff_to_dataframe

        X, y = load_from_arff_to_dataframe(str(path))
        return ReadData(X, y, "panel")
    if suffix == "tsf":
        from sktime.datasets import load_tsf_to_dataframe

        df, _meta = load_tsf_to_dataframe(str(path))
        return ReadData(df, None, "hierarchical")

    df = _read_tabular(path, suffix)
    if suffix == "json" and not long:
        # split-orient JSON carries its own index; do not consume a column
        df.index = _coerce_index(df.index, freq)
        if df.shape[1] == 1:
            return ReadData(df.iloc[:, 0], None, "series")
        return ReadData(df, None, "series")
    if long:
        return _read_long(df, id_col, time_col, freq)

    df = _set_time_index(df, index_col, freq)
    if df.shape[1] == 1:
        return ReadData(df.iloc[:, 0], None, "series")
    return ReadData(df, None, "series")


def write_any(
    obj,
    path: str | Path,
    file_format: str | None = None,
    y=None,
) -> list[str]:
    """Write a pandas/numpy object to a file; returns list of files written."""
    import numpy as np
    import pandas as pd

    path = Path(path)
    suffix = (file_format or path.suffix.lstrip(".") or "csv").lower()
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(obj, np.ndarray):
        if suffix not in ("npy", ""):
            raise CliError("usage", "numpy arrays can only be written as .npy")
        np.save(path.with_suffix(".npy"), obj)
        return [str(path.with_suffix(".npy"))]

    if isinstance(obj, pd.Series):
        obj = obj.to_frame()
    if obj.index.name is None and not isinstance(obj.index, pd.MultiIndex):
        obj = obj.rename_axis("index")

    if suffix == "csv":
        obj.to_csv(path)
        return [str(path)]
    if suffix == "parquet":
        frame = obj.copy()
        if isinstance(frame.index, pd.PeriodIndex):
            frame.index = frame.index.to_timestamp()
        try:
            frame.to_parquet(path)
        except ImportError as err:
            raise missing_dependency("writing parquet", "pyarrow") from err
        return [str(path)]
    if suffix == "json":
        payload = {
            "index": [_label(i) for i in obj.index],
            "columns": [_label(c) for c in obj.columns],
            "data": json.loads(obj.to_json(orient="values")),
        }
        path.write_text(json.dumps(payload, default=str))
        return [str(path)]
    if suffix == "ts":
        return [write_ts(obj, path, y=y)]
    raise CliError("usage", f"unsupported output format: {suffix}")


def write_ts(X, path: Path, y=None) -> str:
    """Write a Panel (with optional labels) to a single .ts file."""
    import shutil
    import tempfile

    from sktime.datasets import write_panel_to_tsfile

    path = Path(path)
    problem = path.stem or "data"
    with tempfile.TemporaryDirectory() as tmp:
        write_panel_to_tsfile(X, path=tmp, target=y, problem_name=problem)
        produced = list(Path(tmp).rglob("*.ts"))
        if not produced:
            raise CliError("internal", "sktime did not produce a .ts file")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced[0]), path)
    return str(path)


def _label(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_label(v) for v in value]
    return str(value)


def parse_fh(text: str):
    """Parse --fh: "1:12" (inclusive), "1,2,12", or "6" -> ForecastingHorizon."""
    from sktime.forecasting.base import ForecastingHorizon

    text = text.strip()
    try:
        if ":" in text:
            start, _, stop = text.partition(":")
            values = list(range(int(start), int(stop) + 1))
            if not values:
                raise ValueError("empty range")
        elif "," in text:
            values = [int(part) for part in text.split(",")]
        else:
            values = [int(text)]
    except ValueError as err:
        raise CliError(
            "usage",
            f"invalid --fh {text!r}: use '1:12', '1,2,12', or '6'",
        ) from err
    return ForecastingHorizon(values, is_relative=True)


def parse_size(text: str | None):
    """Parse --test-size/--train-size: int count or float fraction."""
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError as err:
            raise CliError(
                "usage", f"invalid size {text!r}: use an int count or 0.x fraction"
            ) from err
