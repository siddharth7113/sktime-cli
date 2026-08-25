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

# column names for each probabilistic result, in column-level order
INTERVAL_LEVELS = ["variable", "coverage", "bound"]
QUANTILE_LEVELS = ["variable", "quantile"]
VAR_LEVELS = ["variable"]


def _index_names(index) -> list[str]:
    """Names for every index level, filling in ``time``/``level_i`` as needed."""
    if index.nlevels == 1:
        return [index.name if index.name is not None else "time"]
    return [
        name if name is not None else f"level_{i}" for i, name in enumerate(index.names)
    ]


def melt(frame, levels: list[str]):
    """Melt column levels into long form, keeping the row index intact.

    ``levels`` names the column levels of ``frame``, outermost first. The
    result has those names as columns plus ``value``, indexed exactly as
    ``frame`` was.
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
    """Join MultiIndex column levels with ``__`` for a CSV-safe wide frame."""
    import pandas as pd

    if not isinstance(frame.columns, pd.MultiIndex):
        return frame
    out = frame.copy()
    out.columns = ["__".join(str(part) for part in col) for col in frame.columns]
    return out


def segments_to_frame(segments):
    """Flatten a detector's segment result into ``start``/``end``/``label`` rows.

    ``predict_segments`` returns a Series or frame whose values (or index) are
    ``pd.Interval`` objects, which no file format round-trips.
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
    """Coerce any sktime result (array, Series, frame) into a DataFrame."""
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
