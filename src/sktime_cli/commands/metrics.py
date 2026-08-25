"""``sktime-cli metrics``: list metric objects and score predictions with them.

sktime's 90-odd metric objects were previously reachable only through
``run evaluate --metric``. These commands close the predict-then-score loop:
score a prediction file against a truth file without writing any Python.
"""

from __future__ import annotations

from pathlib import Path

import typer

from sktime_cli import _cache, _io
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._output import OutputFormat, emit_record, emit_table, resolve_format
from sktime_cli._specs import resolve_metric

app = typer.Typer(no_args_is_help=True)


def metric_scitypes() -> tuple[str, ...]:
    """Return every scitype sktime uses for performance metrics.

    Read from the registry rather than listed here, so a metric category added
    upstream is listed without a change.

    Returns
    -------
    tuple of str
        Scitype names, e.g. ``("metric", "metric_forecasting", ...)``.
    """
    from sktime.registry import BASE_CLASS_SCITYPE_LIST

    return tuple(s for s in BASE_CLASS_SCITYPE_LIST if s.startswith("metric"))


@app.command("list")
@handle_errors
def list_(
    scitype: str | None = typer.Argument(
        None, help="Restrict to one metric scitype, e.g. metric_forecasting."
    ),
    name: str | None = typer.Option(
        None, "--name", "-n", help="Substring match on the metric name."
    ),
    installable_only: bool = typer.Option(
        False, "--installable-only", help="Only metrics whose soft deps are installed."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """List sktime metric objects usable with --metric and `metrics score`."""
    fmt = resolve_format(format_, json_)
    known = metric_scitypes()
    if scitype and scitype not in known:
        raise CliError(
            "usage",
            f"unknown metric scitype {scitype!r}",
            hint=f"use one of: {', '.join(known)}",
        )
    wanted = (scitype,) if scitype else known
    rows = [
        {
            "name": record["name"],
            "scitypes": [s for s in record["scitypes"] if s in known],
            "lower_is_better": record["tags"].get("lower_is_better"),
            "installable": record["installable"],
        }
        for record in _cache.get_registry()
        if any(s in wanted for s in record["scitypes"])
        and (not name or name.lower() in record["name"].lower())
        and (not installable_only or record["installable"])
    ]
    emit_table(rows, fmt, quiet_key="name")


@app.command("score")
@handle_errors
def score(
    true: Path = typer.Option(..., "--true", help="File with the observed values."),
    pred: Path = typer.Option(..., "--pred", help="File with the predicted values."),
    metric: list[str] = typer.Option(
        [], "--metric", help="Metric name or spec (repeatable)."
    ),
    train: Path | None = typer.Option(
        None, "--train", help="Training series, for metrics that need y_train."
    ),
    index_col: str = typer.Option("auto", "--index-col"),
    freq: str | None = typer.Option(None, "--freq"),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Score predictions against observed values with one or more metrics."""
    fmt = resolve_format(format_, json_)
    y_true = _io.read_any(true, index_col=index_col, freq=freq).obj
    y_pred = _io.read_any(pred, index_col=index_col, freq=freq).obj
    y_train = _io.read_any(train, index_col=index_col, freq=freq).obj if train else None

    y_true, y_pred = _align(y_true, y_pred)
    metrics = metric or ["MeanAbsolutePercentageError"]

    scores: dict = {}
    for item in metrics:
        scorer = resolve_metric(item)
        scores[_metric_key(item)] = _call_metric(scorer, y_true, y_pred, y_train, item)

    emit_record(
        scores,
        fmt,
        quiet_value="\n".join(f"{k}\t{v}" for k, v in scores.items()),
    )


def _metric_key(item: str) -> str:
    """Name a score after its metric, dropping any parameter list.

    Parameters
    ----------
    item : str
        The ``--metric`` value, which may be a spec.

    Returns
    -------
    str
        The bare metric name, so a parameterized metric keys the output the
        same way a bare one does.
    """
    return item.partition("(")[0] if "(" in item else item


def _align(y_true, y_pred):
    """Line up observed and predicted values so they can be compared.

    Single-column frames are squeezed to Series, and differing lengths are
    reconciled on the shared part of the index, which is what makes it
    possible to score a forecast against a longer test file.

    Parameters
    ----------
    y_true : pd.Series or pd.DataFrame
        Observed values.
    y_pred : pd.Series or pd.DataFrame
        Predicted values.

    Returns
    -------
    tuple
        ``(y_true, y_pred)`` covering the same rows.

    Raises
    ------
    CliError
        ``data_error`` when the lengths differ and the indexes do not overlap
        at all, which means the two files describe different periods.
    """
    import pandas as pd

    if isinstance(y_true, pd.DataFrame) and y_true.shape[1] == 1:
        y_true = y_true.iloc[:, 0]
    if isinstance(y_pred, pd.DataFrame) and y_pred.shape[1] == 1:
        y_pred = y_pred.iloc[:, 0]
    if len(y_true) == len(y_pred):
        return y_true, y_pred

    common = y_true.index.intersection(y_pred.index)
    if len(common) == 0:
        raise CliError(
            "data_error",
            f"--true has {len(y_true)} rows and --pred has {len(y_pred)}, "
            "and their indexes do not overlap",
            hint="score the same horizon, e.g. the test split from: data split",
        )
    return y_true.loc[common], y_pred.loc[common]


def _call_metric(scorer, y_true, y_pred, y_train, item: str):
    """Score one metric, supplying the extra arguments its tags ask for.

    Scaled metrics such as MASE score against the training series, and the
    tags say so, so a metric that needs it can ask for it rather than failing
    with a ``KeyError`` from inside sktime.

    Parameters
    ----------
    scorer : sktime metric
        The metric object.
    y_true, y_pred : pd.Series
        Aligned observed and predicted values.
    y_train : pd.Series or None
        Training series, from ``--train``.
    item : str
        The original ``--metric`` value, named in error messages.

    Returns
    -------
    float
        The score.

    Raises
    ------
    CliError
        ``usage`` when the metric needs a training series that was not given,
        or needs a benchmark prediction, which this command cannot supply.
    """
    kwargs = {}
    if scorer.get_tag("requires-y-train", False, raise_error=False):
        if y_train is None:
            raise CliError(
                "usage",
                f"metric {item} scores against the training series",
                hint="pass --train with the series the model was fitted on",
            )
        kwargs["y_train"] = y_train
    if scorer.get_tag("requires-y-pred-benchmark", False, raise_error=False):
        raise CliError(
            "usage",
            f"metric {item} needs a benchmark prediction, which score cannot supply",
            hint="use it through: sktime-cli run evaluate --metric",
        )
    return float(scorer(y_true, y_pred, **kwargs))
