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
    """Data resolved from ``--data``, before roles are assigned.

    Roles are deliberately not decided here. The same panel file is ``X`` for
    a classifier and ``y`` for a global forecaster, so the estimator's scitype
    picks the slots, not the file.

    Attributes
    ----------
    obj : pd.Series or pd.DataFrame
        The main data object: a Series, or a Panel or Hierarchical frame.
    labels : pd.Series or None
        Class or target labels that came with the data, from a ``.ts`` file or
        a classification dataset. ``None`` when the source carried none.
    exog : pd.DataFrame or None
        Exogenous data from ``--exog``, or a dataset's own exogenous columns.
    kind : {"series", "panel", "hierarchical"}
        The scitype of ``obj``.
    """

    obj: Any
    labels: Any | None
    exog: Any | None
    kind: str


class ReadOptions(NamedTuple):
    """The file-reading options, grouped so they thread through as one value.

    Every ``run`` command exposes this same family of flags, and they are
    passed unchanged from the command layer down to :func:`_io.read_any`.
    Grouping them keeps that hand-off from becoming six positional arguments.

    Attributes
    ----------
    index_col : str, default "auto"
        Time index column for tabular files, or ``"none"`` to keep a
        ``RangeIndex``.
    freq : str or None
        Pandas frequency alias for the index, e.g. ``"M"``.
    long : bool, default False
        Read the file as long-format panel rows.
    id_col : str or None
        Instance id column(s) for long format, comma-separated for a
        hierarchy.
    time_col : str or None
        Time column for long format.
    """

    index_col: str = "auto"
    freq: str | None = None
    long: bool = False
    id_col: str | None = None
    time_col: str | None = None


def _split_target(obj, target: str, source: str):
    """Split a wide frame into endogenous and exogenous parts on ``--target``.

    Parameters
    ----------
    obj : pd.DataFrame
        A wide frame holding the target and its exogenous columns.
    target : str
        Name of the column to use as ``y``.
    source : str
        What ``--data`` named, used only in the error message.

    Returns
    -------
    tuple
        ``(y, X)``, where ``X`` is ``None`` if no columns remained.

    Raises
    ------
    CliError
        ``not_found`` if ``obj`` is not a frame or has no such column.
    """
    import pandas as pd

    if not isinstance(obj, pd.DataFrame) or target not in obj.columns:
        raise CliError("not_found", f"target column {target!r} not in {source}")
    rest = obj.drop(columns=[target])
    return obj[target], (rest if rest.shape[1] else None)


def _looks_like_path(data: str) -> bool:
    """Report whether ``--data`` reads as a filename rather than a dataset id.

    This decides which error a miss produces. ``--data sales.csv`` that does
    not exist is a missing file, not an unknown dataset, and saying so points
    at the real problem.

    Parameters
    ----------
    data : str
        The raw ``--data`` value.

    Returns
    -------
    bool
        True for anything with a path separator or a file suffix. A namespaced
        dataset id such as ``ucr:ArrowHead`` is never a path.
    """
    if "/" in data or "\\" in data:
        return True
    if ":" in data:  # namespaced dataset id, e.g. ucr:ArrowHead
        return False
    return Path(data).suffix != ""


def _missing_data_file(data: str) -> CliError:
    """Build the error for a ``--data`` path that does not exist.

    When the filename stem happens to name a dataset, the hint offers the
    command that would fetch it, which is usually what the caller meant.

    Parameters
    ----------
    data : str
        The path that was not found.

    Returns
    -------
    CliError
        A ``not_found`` error, with a hint that either fetches the dataset or
        points at the dataset listing.
    """
    from sktime_cli import _datasets

    stem = Path(data).stem
    try:
        _datasets.resolve(stem)
    except CliError:
        hint = "pass an existing file, or a dataset name: sktime-cli datasets list"
    else:
        hint = f"fetch it first: sktime-cli datasets load {stem} --output {data}"
    return CliError("not_found", f"file not found: {data}", hint=hint)


def load(
    data: str,
    opts: ReadOptions | None = None,
    target: str | None = None,
    exog: Path | None = None,
) -> Input:
    """Resolve ``--data`` into the data a workflow will run on.

    The single entry point for ``--data``, which accepts either a file path or
    a dataset id.

    Parameters
    ----------
    data : str
        A path to a data file, or a dataset id such as ``airline`` or
        ``ucr:ArrowHead``.
    opts : ReadOptions, optional
        File-reading options. Defaults to reading a wide file with an inferred
        time index.
    target : str or None
        Column of a wide file to use as the target, with the rest becoming
        exogenous data.
    exog : Path or None
        Separate file of exogenous data, which overrides anything ``target``
        or the dataset supplied.

    Returns
    -------
    Input
        The data with roles still unassigned.

    Raises
    ------
    CliError
        ``not_found`` for a missing file or unknown dataset, ``usage`` for an
        ambiguous dataset name, ``data_error`` for contents that cannot be
        read.
    """
    opts = opts or ReadOptions()
    path = Path(data)
    if path.exists():
        return _load_file(path, opts, target, exog)
    if _looks_like_path(data):
        raise _missing_data_file(data)
    return _load_dataset(data, exog, opts)


def _load_file(
    path: Path, opts: ReadOptions, target: str | None, exog: Path | None
) -> Input:
    """Read ``--data`` from a file on disk.

    See :func:`load` for the parameters; ``path`` is a file already known to
    exist.

    Returns
    -------
    Input
        The file's contents, plus any labels it carried and exogenous data
        from ``target`` or ``exog``.
    """
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
    """Fetch ``--data`` as a dataset id and assign its parts.

    Forecasting datasets return the series as ``obj`` with any exogenous
    columns as ``exog``; classification and regression datasets return the
    panel as ``obj`` with its labels.

    See :func:`load` for the parameters.

    Returns
    -------
    Input
        The dataset's contents.
    """
    source, canonical = _datasets.resolve(data)
    loaded = _datasets.load(source, canonical)
    exog_obj = (
        _io.read_any(exog, index_col=opts.index_col, freq=opts.freq).obj
        if exog is not None
        else loaded.get("X")
    )
    if loaded["task"] == "forecaster":
        y = loaded["y"]
        return Input(obj=y, labels=None, exog=exog_obj, kind=_kind_of(y))
    return Input(
        obj=loaded["X"], labels=loaded["y"], exog=exog_obj, kind=_kind_of(loaded["X"])
    )


_SCITYPE_KINDS = {"Series": "series", "Panel": "panel", "Hierarchical": "hierarchical"}


def _kind_of(obj) -> str:
    """Classify a pandas object's scitype, asking sktime rather than guessing.

    Index depth alone is not enough: sktime's ``nested_univ`` mtype holds a
    whole Series in each cell of a flat-indexed frame, so a Panel can arrive
    with a single index level. Every builtin classification dataset is loaded
    that way, and treating those as a single series made them unusable.

    Parameters
    ----------
    obj : pd.Series or pd.DataFrame
        The object to classify.

    Returns
    -------
    {"series", "panel", "hierarchical"}
        The scitype sktime recognises. Falls back to index depth if sktime
        cannot classify the object at all, so an unrecognised container still
        reaches the estimator and fails with sktime's own message.
    """
    import pandas as pd
    from sktime.datatypes import check_is_scitype

    valid, _msg, meta = check_is_scitype(
        obj, list(_SCITYPE_KINDS), return_metadata=["scitype"]
    )
    if valid:
        kind = _SCITYPE_KINDS.get(meta.get("scitype"))
        if kind:
            return kind

    index = getattr(obj, "index", None)
    if isinstance(index, pd.MultiIndex):
        return "panel" if index.nlevels == 2 else "hierarchical"
    return "series"


def _has_non_numeric(obj) -> list[str]:
    """Name the non-numeric columns of an object, if any.

    Parameters
    ----------
    obj : pd.Series or pd.DataFrame
        The object to check.

    Returns
    -------
    list of str
        Names of columns no estimator will accept as a target. Empty when the
        data is entirely numeric.
    """
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
    """Return the resolved data as forecasting ``y``, or explain why it cannot be.

    The common mistake is pointing ``--data`` at a long-format panel without
    ``--long``, which leaves the instance id sitting in the frame as a string
    column. sktime raises a type error deep inside ``fit`` for that; this
    catches it first and names the flags that fix it.

    Parameters
    ----------
    inp : Input
        Resolved data. Series, Panel, and Hierarchical are all valid: sktime
        forecasters accept panel ``y`` for global forecasting.
    source : str
        What ``--data`` named, reported as the error's detail.

    Returns
    -------
    pd.Series or pd.DataFrame
        The data, unchanged, when it can serve as ``y``.

    Raises
    ------
    CliError
        ``data_error`` naming the offending columns, hinting at ``--long`` and
        ``--target``.
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
