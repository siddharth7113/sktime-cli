"""Resolve ``--data`` into the objects a workflow needs.

``--data`` is either a file path or a dataset id. Reading it yields a neutral
container; which slot each object fills (``y`` vs ``X``) is decided by the
estimator's scitype, not by the file, so the same panel file can train a
classifier (as ``X``) or a global forecaster (as ``y``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from sktime_cli import _datasets, _io
from sktime_cli._errors import CliError


class Input(NamedTuple):
    """Data resolved from ``--data``, before roles are assigned."""

    obj: Any  # the main data object: Series, DataFrame, Panel or Hierarchical
    labels: Any | None  # class/target labels carried alongside (.ts, .arff, datasets)
    exog: Any | None  # exogenous X, from --exog
    kind: str  # "series" | "panel" | "hierarchical"


class ReadOptions(NamedTuple):
    """The ``--index-col``/``--freq``/``--long`` family, threaded as one value."""

    index_col: str = "auto"
    freq: str | None = None
    long: bool = False
    id_col: str | None = None
    time_col: str | None = None


def _split_target(obj, target: str, source: str):
    """Split a wide frame into (y, X) on ``--target``."""
    import pandas as pd

    if not isinstance(obj, pd.DataFrame) or target not in obj.columns:
        raise CliError("not_found", f"target column {target!r} not in {source}")
    rest = obj.drop(columns=[target])
    return obj[target], (rest if rest.shape[1] else None)


def load(
    data: str,
    opts: ReadOptions | None = None,
    target: str | None = None,
    exog: Path | None = None,
) -> Input:
    """Resolve ``--data`` (a file path or a dataset id) into an ``Input``."""
    opts = opts or ReadOptions()
    path = Path(data)
    if path.exists():
        return _load_file(path, opts, target, exog)
    return _load_dataset(data, exog, opts)


def _load_file(
    path: Path, opts: ReadOptions, target: str | None, exog: Path | None
) -> Input:
    read = _io.read_any(
        path,
        index_col=opts.index_col,
        freq=opts.freq,
        long=opts.long,
        id_col=opts.id_col,
        time_col=opts.time_col,
    )
    obj, labels = read.obj, read.y
    exog_obj = None
    if target is not None:
        obj, exog_obj = _split_target(obj, target, str(path))
    if exog is not None:
        exog_obj = _io.read_any(exog, index_col=opts.index_col, freq=opts.freq).obj
    return Input(obj=obj, labels=labels, exog=exog_obj, kind=read.kind)


def _load_dataset(data: str, exog: Path | None, opts: ReadOptions) -> Input:
    source, canonical = _datasets.resolve(data)
    loaded = _datasets.load(source, canonical)
    exog_obj = (
        _io.read_any(exog, index_col=opts.index_col, freq=opts.freq).obj
        if exog is not None
        else loaded.get("X")
    )
    if loaded["task"] == "forecasting":
        y = loaded["y"]
        return Input(obj=y, labels=None, exog=exog_obj, kind=_kind_of(y))
    return Input(
        obj=loaded["X"], labels=loaded["y"], exog=exog_obj, kind=_kind_of(loaded["X"])
    )


def _kind_of(obj) -> str:
    """Classify a pandas object as series, panel, or hierarchical by index depth."""
    import pandas as pd

    index = getattr(obj, "index", None)
    if isinstance(index, pd.MultiIndex):
        return "panel" if index.nlevels == 2 else "hierarchical"
    return "series"


def _has_non_numeric(obj) -> list[str]:
    """Return the names of non-numeric columns, which no estimator accepts as y."""
    import pandas as pd

    if isinstance(obj, pd.Series):
        return [] if pd.api.types.is_numeric_dtype(obj) else [str(obj.name)]
    if isinstance(obj, pd.DataFrame):
        return [
            str(col)
            for col in obj.columns
            if not pd.api.types.is_numeric_dtype(obj[col])
        ]
    return []


def as_endogenous(inp: Input, source: str):
    """Return ``obj`` as forecasting ``y``, with a CLI-level error if it cannot be.

    The common mistake is pointing ``--data`` at a long-format panel without
    ``--long``, which leaves the instance id sitting in the frame as a string
    column. sktime raises a type error deep inside ``fit``; this turns it into
    an actionable message naming the flags that fix it.
    """
    obj = inp.obj
    bad = _has_non_numeric(obj)
    if bad:
        raise CliError(
            "data_error",
            f"non-numeric column(s) in the target data: {', '.join(bad)}",
            hint=(
                "for a long-format panel pass --long --id-col ID --time-col TIME; "
                "to forecast one column of a wide file pass --target COLUMN"
            ),
            detail=source,
        )
    return obj
