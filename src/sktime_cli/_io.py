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
    """The result of reading a data file.

    Attributes
    ----------
    obj : pd.Series or pd.DataFrame
        The data itself, in an mtype sktime accepts. A Series scitype comes
        back as a ``pd.Series`` or single-index ``pd.DataFrame``; Panel and
        Hierarchical scitypes come back as a ``pd.DataFrame`` with a
        ``MultiIndex``.
    y : pd.Series or None
        Class or target labels, when the file format carries them alongside
        the data. Only ``.ts`` and ``.arff`` files do; otherwise ``None``.
    kind : {"series", "panel", "hierarchical"}
        Which sktime scitype ``obj`` holds. Callers use this to decide whether
        the data can fill a given estimator's ``y`` or ``X``.
    """

    obj: Any
    y: Any | None
    kind: str


def _read_tabular(path: Path, input_format: str | None):
    """Read a csv, parquet, or json file into a raw :class:`pandas.DataFrame`.

    No index or scitype interpretation happens here; the frame is returned as
    the file describes it, and :func:`read_any` gives it meaning.

    Parameters
    ----------
    path : Path
        File to read.
    input_format : str or None
        Format override. When ``None`` the format is taken from the file
        suffix.

    Returns
    -------
    pd.DataFrame
        The file's contents, with a ``RangeIndex`` unless the format carries
        its own index (json "split" orient does).

    Raises
    ------
    CliError
        ``usage`` if the format is not one of csv, parquet, or json;
        ``data_error`` if a json file does not use the "split" orient;
        ``missing_dependency`` if parquet support is not installed.
    """
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
    """Restore a serialized index to a usable pandas index type.

    JSON has no way to record that a label was a timestamp or a period, so a
    round trip through a file leaves the index as strings. This tries integer,
    then datetime, then period, and leaves the index untouched when none of
    them apply.

    Parameters
    ----------
    index : sequence
        Index labels as read from the file.
    freq : str or None
        Pandas frequency alias to convert to, e.g. ``"M"``. When ``None`` the
        frequency is inferred, and the index stays a ``DatetimeIndex`` if it
        cannot be.

    Returns
    -------
    pd.Index
        The most specific index type the labels support.
    """
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
    """Move a column of ``df`` into the index and give it a time dtype.

    Parameters
    ----------
    df : pd.DataFrame
        Frame as read from the file.
    index_col : str
        Name of the column to use as the time index. ``"auto"`` takes the
        first column, but leaves the frame alone if that column is not
        time-like. ``"none"`` leaves the ``RangeIndex`` in place.
    freq : str or None
        Pandas frequency alias for the resulting ``PeriodIndex``. When
        ``None`` the frequency is inferred; if it cannot be, a
        ``DatetimeIndex`` is kept, which most estimators accept.

    Returns
    -------
    pd.DataFrame
        The frame, indexed by time where that was possible.

    Raises
    ------
    CliError
        ``not_found`` if ``index_col`` names a column the file does not have;
        ``data_error`` if a named column is neither integer nor datetime, or
        if an explicit ``freq`` cannot be applied.
    """
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
    """Convert a long-format time column to a valid sktime index level.

    sktime requires the innermost level of a Panel or Hierarchical index to be
    a time index, so a column of date strings has to be converted before it
    becomes part of the ``MultiIndex``.

    Parameters
    ----------
    series : pd.Series
        The time column.
    freq : str or None
        Pandas frequency alias for the resulting periods. When ``None`` the
        frequency is inferred, falling back to timestamps.

    Returns
    -------
    pd.Series
        The column as integers, periods, or timestamps.

    Raises
    ------
    CliError
        ``data_error`` if the column is neither integer nor datetime-like.
    """
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
    """Build a Panel or Hierarchical frame from long-format rows.

    Long format is one row per (instance, timepoint); sktime wants those as
    index levels instead of columns.

    Parameters
    ----------
    df : pd.DataFrame
        Frame of long-format rows.
    id_col : str or None
        Name of the instance id column, or several separated by commas. More
        than one id level makes the result Hierarchical rather than Panel.
        Defaults to the first column.
    time_col : str or None
        Name of the time column. Defaults to the column after the id columns.
    freq : str or None
        Pandas frequency alias for the time level.

    Returns
    -------
    ReadData
        With ``kind`` set to ``"panel"`` for a single id level, or
        ``"hierarchical"`` for several.

    Raises
    ------
    CliError
        ``not_found`` if a named column is absent; the error lists the columns
        the file does have.
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
    """Read any supported data file into an sktime-compatible pandas object.

    This is the single entry point for reading data. sktime's own loaders
    handle ``.ts``, ``.tsf``, and ``.arff``; csv, parquet, and json are read
    here, because sktime has no ingestion for them.

    Parameters
    ----------
    path : str or Path
        File to read.
    input_format : str or None
        Format override: ``csv``, ``parquet``, ``json``, ``ts``, ``tsf``, or
        ``arff``. When ``None`` the format comes from the file suffix.
    index_col : str, default "auto"
        Name of the time index column for tabular formats. ``"auto"`` uses the
        first column when it is time-like; ``"none"`` keeps a ``RangeIndex``.
    freq : str or None
        Pandas frequency alias, e.g. ``"M"``. Forces the index to a
        ``PeriodIndex`` at that frequency instead of inferring one.
    long : bool, default False
        Read tabular data as long-format panel rows rather than as a wide
        series. Requires ``id_col`` and ``time_col``, or takes the first two
        columns.
    id_col : str or None
        Instance id column for long format; several may be given separated by
        commas, which produces Hierarchical rather than Panel data.
    time_col : str or None
        Time column for long format.

    Returns
    -------
    ReadData
        The data, any labels the file carried, and which scitype it is.

    Raises
    ------
    CliError
        ``not_found`` if the file or a named column is absent; ``usage`` for
        an unsupported format; ``data_error`` if the contents cannot be
        interpreted.

    See Also
    --------
    write_any : The inverse operation.
    """
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
    """Write a pandas or numpy object to a file.

    Parameters
    ----------
    obj : pd.Series, pd.DataFrame or np.ndarray
        The data to write. A ``Series`` is promoted to a one-column frame, and
        an unnamed index is named ``index`` so the file round-trips.
    path : str or Path
        Destination. Parent directories are created as needed.
    file_format : str or None
        Format override: ``csv``, ``parquet``, ``json``, ``ts``, or ``npy``.
        When ``None`` the format comes from the file suffix, defaulting to csv.
    y : array-like, optional
        Labels to embed alongside the data. Only ``.ts`` carries them; other
        formats ignore this, and callers write labels to a separate file.

    Returns
    -------
    list of str
        Paths actually written. This is a list because a format may not use
        the exact path given: ``.npy`` forces its own suffix.

    Raises
    ------
    CliError
        ``usage`` for a format that cannot represent ``obj``, such as a numpy
        array to anything but ``.npy``; ``missing_dependency`` if parquet
        support is not installed.

    Notes
    -----
    A ``PeriodIndex`` is converted to timestamps for parquet, which has no
    period type. Reading it back gives a ``DatetimeIndex`` unless ``freq`` is
    passed to :func:`read_any`.
    """
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
    if isinstance(obj.index, pd.MultiIndex):
        # unnamed levels write as blank CSV headers, which cannot be read back
        # with --long; name them positionally so the round trip works
        obj = obj.rename_axis(
            [
                name if name is not None else f"level_{i}"
                for i, name in enumerate(obj.index.names)
            ]
        )
    elif obj.index.name is None:
        obj = obj.rename_axis("index")

    if suffix == "csv":
        _reject_nested(obj, suffix)
        obj.to_csv(path)
        return [str(path)]
    if suffix == "parquet":
        _reject_nested(obj, suffix)
        frame = obj.copy()
        if isinstance(frame.index, pd.PeriodIndex):
            frame.index = frame.index.to_timestamp()
        try:
            frame.to_parquet(path)
        except ImportError as err:
            raise missing_dependency("writing parquet", "pyarrow") from err
        return [str(path)]
    if suffix == "json":
        _reject_nested(obj, suffix)
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


def _reject_nested(obj, suffix: str) -> None:
    """Refuse to write a nested panel to a format that cannot hold one.

    sktime's ``nested_univ`` mtype stores a whole Series in each cell. Writing
    that to a flat format silently produces cells holding the *text* of a
    Series, which reads back as unusable object data. Failing here is the
    difference between a clear error and quiet data loss.

    Parameters
    ----------
    obj : pd.DataFrame
        The object about to be written.
    suffix : str
        The target format, named in the error.

    Raises
    ------
    CliError
        ``usage`` naming the conversion that makes the data writable.
    """
    import pandas as pd

    if not isinstance(obj, pd.DataFrame):
        return
    nested = [
        str(col)
        for col in obj.columns
        if obj[col].dtype == object
        and obj[col].map(lambda v: isinstance(v, pd.Series)).any()
    ]
    if nested:
        raise CliError(
            "usage",
            f"nested panel column(s) {', '.join(nested)} cannot be written as {suffix}",
            hint=(
                "convert to a flat mtype first: "
                "--to-mtype pd-multiindex (long) or --to-mtype numpy3D with .npy"
            ),
        )


def write_ts(X, path: Path, y=None) -> str:
    """Write a Panel, and optionally its labels, to one ``.ts`` file.

    sktime's ``write_panel_to_tsfile`` writes into a directory named after the
    problem, so this writes to a temporary directory and moves the single file
    it produced to ``path``.

    Parameters
    ----------
    X : pd.DataFrame
        Panel data to write.
    path : Path
        Destination ``.ts`` file.
    y : array-like, optional
        Class or target labels to embed.

    Returns
    -------
    str
        The path written.

    Raises
    ------
    CliError
        ``internal`` if sktime produced no file, which would mean its writer
        changed behaviour.
    """
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
    """Make one index or column label JSON-serializable.

    Numbers, strings, and booleans pass through so they keep their type in the
    output; tuples become lists, which is how a ``MultiIndex`` entry is
    represented; anything else becomes its string form.
    """
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_label(v) for v in value]
    return str(value)


def parse_fh(text: str):
    """Parse the ``--fh`` option into a :class:`ForecastingHorizon`.

    Parameters
    ----------
    text : str
        One of three forms: ``"1:12"`` for an inclusive range, ``"1,2,12"``
        for an explicit list, or ``"6"`` for a single step.

    Returns
    -------
    ForecastingHorizon
        A relative horizon, counted from the end of the training data.

    Raises
    ------
    CliError
        ``usage`` if the text matches none of the three forms. The message
        shows all three.
    """
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
