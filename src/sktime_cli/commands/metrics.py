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

# every metric scitype sktime declares, so `metrics list` needs no hardcoding
METRIC_SCITYPES = (
    "metric",
    "metric_forecasting",
    "metric_forecasting_proba",
    "metric_detection",
)


@app.command("list")
@handle_errors
def list_(
    scitype: str | None = typer.Argument(
        None, help=f"Restrict to one metric scitype: {'|'.join(METRIC_SCITYPES)}."
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
    if scitype and scitype not in METRIC_SCITYPES:
        raise CliError(
            "usage",
            f"unknown metric scitype {scitype!r}",
            hint=f"use one of: {', '.join(METRIC_SCITYPES)}",
        )
    wanted = (scitype,) if scitype else METRIC_SCITYPES
    rows = [
        {
            "name": record["name"],
            "scitypes": [s for s in record["scitypes"] if s in METRIC_SCITYPES],
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
    """Name a score after the metric, without its parameter list."""
    return item.partition("(")[0] if "(" in item else item


def _align(y_true, y_pred):
    """Line up truth and prediction, erroring when they cannot be compared."""
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
    """Call a metric, supplying y_train to the metrics whose tag requires it."""
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
