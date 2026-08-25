"""Reshape sktime results into flat frames the CLI can serialise.

sktime returns probabilistic forecasts with MultiIndex columns and detection
segments as ``pd.Interval`` objects. Neither survives a CSV round trip, and
neither has a stable column count. These helpers flatten both into long form:
one row per observation, a fixed set of named columns, and the original time
index preserved. That schema is what ``run predict --interval`` and
``run detect`` emit, and it is part of the CLI contract.
"""

from __future__ import annotations

from typing import Any

#: Column-level names for ``predict_interval`` output, outermost first. Part of
#: the published output contract: melted interval results always have these
#: columns plus ``value``, whatever coverages were requested.
INTERVAL_LEVELS = ["variable", "coverage", "bound"]

#: Column-level names for ``predict_quantiles`` output. See
#: :data:`INTERVAL_LEVELS`.
QUANTILE_LEVELS = ["variable", "quantile"]

#: Column-level names for ``predict_var`` output, whose columns are flat.
VAR_LEVELS = ["variable"]


def _index_names(index) -> list[str]:
    """Name every level of an index, inventing names for unnamed ones.

    Melting needs named levels to restore the index afterwards, and sktime
    results often carry an unnamed index. A single unnamed level becomes
    ``time``, since that is what it always is here; unnamed levels of a
    ``MultiIndex`` become ``level_0``, ``level_1``, and so on.

    Parameters
    ----------
    index : pd.Index
        Index to name.

    Returns
    -------
    list of str
        One name per level, in order.
    """
    if index.nlevels == 1:
        return [index.name if index.name is not None else "time"]
    return [
        name if name is not None else f"level_{i}" for i, name in enumerate(index.names)
    ]


def melt(frame, levels: list[str]):
    """Melt column levels into long form, keeping the row index intact.

    This is what makes probabilistic output parseable. sktime returns
    intervals with columns ``(variable, coverage, bound)``, so asking for two
    coverages instead of one changes the column count. In long form the
    columns are fixed and extra levels add rows instead.

    Parameters
    ----------
    frame : pd.DataFrame
        Frame whose columns are to be melted. Flat columns are treated as a
        single level, so this works on ``predict_var`` output too.
    levels : list of str
        Names for the column levels, outermost first. Use the module
        constants: :data:`INTERVAL_LEVELS`, :data:`QUANTILE_LEVELS`, or
        :data:`VAR_LEVELS`.

    Returns
    -------
    pd.DataFrame
        One row per (index entry, column combination), with ``levels`` as
        columns plus ``value``, indexed as ``frame`` was.

    Examples
    --------
    An interval frame with two coverages melts to four rows per timepoint,
    with columns ``variable``, ``coverage``, ``bound``, ``value``.

    See Also
    --------
    widen : The opposite choice, keeping sktime's native column layout.
    """
    import pandas as pd

    flat = frame.copy()
    flat.columns = pd.MultiIndex.from_tuples(
        [tuple(col) if isinstance(col, tuple) else (col,) for col in frame.columns],
        names=levels,
    )
    index_names = _index_names(flat.index)
    flat.index = flat.index.set_names(index_names)
    long = flat.stack(levels, future_stack=True).rename("value").reset_index()
    return long.set_index(index_names)


def widen(frame):
    """Flatten MultiIndex columns into single strings joined by ``__``.

    Keeps sktime's native layout, one column per (variable, level)
    combination, at the cost of a column count that varies with the request.
    Use it when a downstream tool expects the wide shape.

    Parameters
    ----------
    frame : pd.DataFrame
        Frame with ``MultiIndex`` columns. A frame with flat columns is
        returned unchanged.

    Returns
    -------
    pd.DataFrame
        The same data with string column names, e.g. ``y__0.8__lower``.
    """
    import pandas as pd

    if not isinstance(frame.columns, pd.MultiIndex):
        return frame
    out = frame.copy()
    out.columns = ["__".join(str(part) for part in col) for col in frame.columns]
    return out


def segments_to_frame(segments):
    """Flatten a detector's segments into ``start`` and ``end`` columns.

    ``predict_segments`` may return intervals either as the index or as a
    column of ``pd.Interval`` objects, and no file format round-trips those.
    Detectors that instead return a dense label per timepoint need no
    flattening and pass through unchanged.

    Parameters
    ----------
    segments : pd.Series or pd.DataFrame
        A detector's segment result.

    Returns
    -------
    pd.DataFrame
        With ``start`` and ``end`` columns plus any other columns the result
        carried, indexed by segment number. If no intervals were found, the
        input frame unchanged.
    """
    import pandas as pd

    frame = segments.to_frame() if isinstance(segments, pd.Series) else segments.copy()

    intervals, source = None, None
    if isinstance(frame.index, pd.IntervalIndex):
        intervals, source = frame.index, "index"
    else:
        for col in frame.columns:
            if frame[col].map(lambda v: isinstance(v, pd.Interval)).all():
                intervals, source = pd.IntervalIndex(frame[col]), col
                break
    if intervals is None:
        return frame

    out = pd.DataFrame(
        {"start": intervals.left, "end": intervals.right},
        index=pd.RangeIndex(len(intervals), name="segment"),
    )
    for col in frame.columns:
        if col == source:
            continue
        out[str(col)] = frame[col].to_numpy()
    return out


def to_frame(result: Any, name: str = "value"):
    """Coerce any sktime result into a DataFrame that can be written out.

    Estimators return numpy arrays, Series, and DataFrames depending on
    scitype and method, and the output layer only handles frames.

    Parameters
    ----------
    result : np.ndarray, pd.Series or pd.DataFrame
        Whatever the estimator returned.
    name : str, default "value"
        Column name to use when the result has none of its own. A Series that
        already has a name keeps it.

    Returns
    -------
    pd.DataFrame
        The result as a frame.
    """
    import numpy as np
    import pandas as pd

    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, pd.Series):
        return result.rename(
            result.name if result.name is not None else name
        ).to_frame()
    if isinstance(result, np.ndarray) and result.ndim == 2:
        return pd.DataFrame(result)
    return pd.Series(result, name=name).to_frame()
