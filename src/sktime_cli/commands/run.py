"""``sktime-cli run``: one-shot fit / predict / fit-predict / evaluate."""

from __future__ import annotations

from pathlib import Path

import typer

from sktime_cli import _datasets, _io
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._models import estimator_scitype, load_model, save_model
from sktime_cli._output import (
    OutputFormat,
    emit_frame,
    emit_record,
    resolve_format,
)
from sktime_cli._specs import build_estimator, resolve_cv, resolve_metric

app = typer.Typer(no_args_is_help=True)

_PANEL_SCITYPES = ("classifier", "regressor", "clusterer")

DATA_OPT = typer.Option(
    ...,
    "--data",
    help="Data file path, or a dataset name (e.g. airline, ucr:ArrowHead).",
)
SET_OPT = typer.Option(
    [], "--set", help="Parameter override key=value; __ nests (repeatable)."
)


def _looks_like_path(data: str) -> bool:
    """Report whether --data reads as a filename, so a miss is a missing file."""
    if "/" in data or "\\" in data:
        return True
    if ":" in data:  # namespaced dataset id, e.g. ucr:ArrowHead
        return False
    return Path(data).suffix != ""


def _missing_data_file(data: str) -> CliError:
    """Report a --data path that doesn't exist, suggesting a fetch when we can."""
    stem = Path(data).stem
    try:
        _datasets.resolve(stem)
    except CliError:
        hint = "pass an existing file, or a dataset name: sktime-cli datasets list"
    else:
        hint = f"fetch it first: sktime-cli datasets load {stem} --output {data}"
    return CliError("not_found", f"file not found: {data}", hint=hint)


def _load_input(
    data: str,
    target: str | None = None,
    exog: Path | None = None,
    index_col: str = "auto",
    freq: str | None = None,
) -> dict:
    """Resolve --data (path or dataset name) into y/X for the workflow."""
    path = Path(data)
    if path.exists():
        read = _io.read_any(path, index_col=index_col, freq=freq)
        if read.kind in ("panel", "hierarchical") and read.y is not None:
            return {"kind": "panel", "X": read.obj, "y": read.y}
        if read.kind in ("panel", "hierarchical"):
            return {"kind": "panel", "X": read.obj, "y": None}
        obj = read.obj
        X = None
        if target is not None:
            import pandas as pd

            if not isinstance(obj, pd.DataFrame) or target not in obj.columns:
                raise CliError("not_found", f"target column {target!r} not in {data}")
            y = obj[target]
            rest = obj.drop(columns=[target])
            X = rest if rest.shape[1] else None
        else:
            y = obj
        if exog is not None:
            X = _io.read_any(exog, index_col=index_col, freq=freq).obj
        return {"kind": "series", "y": y, "X": X}

    if _looks_like_path(data):
        raise _missing_data_file(data)

    source, canonical = _datasets.resolve(data)
    loaded = _datasets.load(source, canonical)
    if loaded["task"] == "forecasting":
        return {"kind": "series", "y": loaded["y"], "X": loaded.get("X")}
    return {"kind": "panel", "X": loaded["X"], "y": loaded["y"]}


def _fit(est, scitype: str, inp: dict, fh_text: str | None):
    """Dispatch fit by scitype; returns (n_obs, extras dict)."""
    if scitype == "forecaster":
        if inp["kind"] != "series":
            raise CliError("data_error", "forecasters need Series data, got a panel")
        y = inp["y"]
        fh = _io.parse_fh(fh_text) if fh_text else None
        try:
            est.fit(y=y, X=inp.get("X"), fh=fh)
        except ValueError as err:
            if "fh" in str(err).lower():
                raise CliError(
                    "usage",
                    f"this forecaster requires the horizon at fit time: {err}",
                    hint="pass --fh, e.g. --fh 1:12",
                ) from err
            raise
        return len(y), {"cutoff": str(est.cutoff[0])}
    if scitype in _PANEL_SCITYPES:
        if inp["kind"] != "panel":
            raise CliError(
                "data_error",
                f"{scitype}s need Panel data (.ts file or classification dataset)",
            )
        X, y = inp["X"], inp["y"]
        if y is None and scitype != "clusterer":
            raise CliError("data_error", f"{scitype} training data has no labels")
        est.fit(X, y) if y is not None else est.fit(X)
        return len(X), {}
    raise CliError(
        "usage",
        f"run supports forecaster/classifier/regressor/clusterer, got {scitype}",
    )


def _load_x(data: str):
    """Resolve --data for predict into one object: exog X, or a panel to score."""
    inp = _load_input(data)
    return inp["y"] if inp["kind"] == "series" else inp["X"]


def _predict(est, scitype: str, fh_text: str | None, data: str | None, proba: bool):
    """Dispatch predict by scitype; returns a pandas object."""
    import pandas as pd

    if scitype == "forecaster":
        fh = _io.parse_fh(fh_text) if fh_text else None
        X = None
        if data:
            X = _load_x(data)
        try:
            return est.predict(fh=fh, X=X)
        except ValueError as err:
            if "fh" in str(err).lower():
                raise CliError(
                    "usage",
                    f"no forecasting horizon: {err}",
                    hint="pass --fh, e.g. --fh 1:12",
                ) from err
            raise
    if data is None:
        raise CliError("usage", f"{scitype} predict needs --data with panel X")
    X = _load_x(data)
    if proba:
        result = est.predict_proba(X)
        classes = [str(c) for c in getattr(est, "classes_", range(result.shape[1]))]
        return pd.DataFrame(result, columns=classes)
    result = est.predict(X)
    return pd.Series(result, name="prediction")


def _emit_prediction(pred, output: Path | None, fmt: OutputFormat) -> None:
    if output is not None:
        files = _io.write_any(pred, output)
        emit_record({"files": files, "n": int(len(pred))}, fmt, quiet_value=files[0])
    else:
        emit_frame(pred, fmt)


@app.command("fit")
@handle_errors
def fit(
    spec: str = typer.Argument(
        ..., help='Estimator spec, e.g. "NaiveForecaster(sp=12)".'
    ),
    data: str = DATA_OPT,
    target: str | None = typer.Option(None, "--target", help="y column in --data."),
    exog: Path | None = typer.Option(None, "--exog", help="Exogenous X file."),
    index_col: str = typer.Option(
        "auto", "--index-col", help="Time index column: a name, auto, or none."
    ),
    freq: str | None = typer.Option(
        None, "--freq", help="Pandas frequency for the index, e.g. M, D."
    ),
    fh: str | None = typer.Option(None, "--fh", help="Horizon, e.g. 1:12."),
    set_: list[str] = SET_OPT,
    model_out: Path | None = typer.Option(
        None, "--model-out", help="Model .zip path (default: under the cache dir)."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Fit an estimator on data and save the fitted model to a .zip file."""
    fmt = resolve_format(format_, json_)
    est = build_estimator(spec, set_)
    scitype = estimator_scitype(est)
    inp = _load_input(data, target=target, exog=exog, index_col=index_col, freq=freq)
    n_obs, extras = _fit(est, scitype, inp, fh)
    path = save_model(est, model_out)
    record = {
        "model": str(path),
        "estimator": str(est),
        "scitype": scitype,
        "n_obs": n_obs,
        **extras,
    }
    emit_record(record, fmt, quiet_value=str(path))


@app.command("predict")
@handle_errors
def predict(
    model: Path = typer.Option(..., "--model", help="Model .zip from `run fit`."),
    fh: str | None = typer.Option(None, "--fh", help="Horizon, e.g. 1:12."),
    data: str | None = typer.Option(
        None,
        "--data",
        help=(
            "X data, as a file path or a dataset name: exog for forecasters, "
            "panel for classifiers."
        ),
    ),
    proba: bool = typer.Option(False, "--proba", help="Class probabilities."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write predictions to a file instead of stdout."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Predict from a saved model; writes predictions to stdout or --output."""
    fmt = resolve_format(format_, json_)
    est = load_model(model)
    scitype = estimator_scitype(est)
    pred = _predict(est, scitype, fh, data, proba)
    _emit_prediction(pred, output, fmt)


@app.command("fit-predict")
@handle_errors
def fit_predict(
    spec: str = typer.Argument(
        ..., help='Estimator spec, e.g. "NaiveForecaster(sp=12)".'
    ),
    data: str = DATA_OPT,
    target: str | None = typer.Option(None, "--target", help="y column in --data."),
    exog: Path | None = typer.Option(None, "--exog", help="Exogenous X file."),
    index_col: str = typer.Option(
        "auto", "--index-col", help="Time index column: a name, auto, or none."
    ),
    freq: str | None = typer.Option(
        None, "--freq", help="Pandas frequency for the index, e.g. M, D."
    ),
    fh: str | None = typer.Option(None, "--fh", help="Horizon, e.g. 1:12."),
    set_: list[str] = SET_OPT,
    model_out: Path | None = typer.Option(
        None, "--model-out", help="Also persist the fitted model."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write predictions here instead of stdout."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Fit and predict in one process (forecast fh, or in-sample for panels)."""
    import sys

    fmt = resolve_format(format_, json_)
    est = build_estimator(spec, set_)
    scitype = estimator_scitype(est)
    inp = _load_input(data, target=target, exog=exog, index_col=index_col, freq=freq)

    if scitype == "forecaster":
        if not fh:
            raise CliError("usage", "fit-predict needs --fh for forecasters")
        _fit(est, scitype, inp, fh)
        pred = est.predict()
    else:
        if inp["kind"] != "panel":
            raise CliError("data_error", f"{scitype}s need Panel data")
        pred_raw = est.fit_predict(inp["X"], inp["y"])
        import pandas as pd

        pred = pd.Series(pred_raw, name="prediction")

    if model_out is not None:
        path = save_model(est, model_out)
        print(f"model saved: {path}", file=sys.stderr)
    _emit_prediction(pred, output, fmt)


@app.command("evaluate")
@handle_errors
def evaluate_cmd(
    spec: str = typer.Argument(
        ..., help='Forecaster spec, e.g. "NaiveForecaster(sp=12)".'
    ),
    data: str = DATA_OPT,
    target: str | None = typer.Option(None, "--target", help="y column in --data."),
    exog: Path | None = typer.Option(None, "--exog", help="Exogenous X file."),
    index_col: str = typer.Option(
        "auto", "--index-col", help="Time index column: a name, auto, or none."
    ),
    freq: str | None = typer.Option(
        None, "--freq", help="Pandas frequency for the index, e.g. M, D."
    ),
    cv: str | None = typer.Option(
        None,
        "--cv",
        help='Splitter spec, e.g. "ExpandingWindowSplitter(initial_window=72)".',
    ),
    metric: list[str] = typer.Option(
        [], "--metric", help="Metric name or spec (repeatable)."
    ),
    strategy: str = typer.Option(
        "refit", "--strategy", help="refit|update|no-update_params."
    ),
    fh: str | None = typer.Option(
        None, "--fh", help="Horizon for the default splitter when --cv is absent."
    ),
    initial_window: int | None = typer.Option(
        None, "--initial-window", help="Initial window for the default splitter."
    ),
    set_: list[str] = SET_OPT,
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write per-fold results to a CSV file."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Backtest a forecaster with cross-validation (sktime evaluate)."""
    from sktime.forecasting.model_evaluation import evaluate

    fmt = resolve_format(format_, json_)
    est = build_estimator(spec, set_)
    scitype = estimator_scitype(est)
    if scitype != "forecaster":
        raise CliError("usage", "run evaluate supports forecasters in v0.0.1")
    if strategy not in ("refit", "update", "no-update_params"):
        raise CliError("usage", f"invalid --strategy {strategy!r}")
    if not cv and not fh:
        raise CliError("usage", "pass --cv, or --fh to use a default expanding window")

    inp = _load_input(data, target=target, exog=exog, index_col=index_col, freq=freq)
    if inp["kind"] != "series":
        raise CliError("data_error", "evaluate needs Series data")
    y = inp["y"]

    fh_obj = _io.parse_fh(fh) if fh else None
    splitter = resolve_cv(cv, fh_obj, initial_window, len(y))
    metrics = [resolve_metric(m) for m in metric] or [
        resolve_metric("MeanAbsolutePercentageError")
    ]

    results = evaluate(
        forecaster=est,
        cv=splitter,
        y=y,
        X=inp.get("X"),
        strategy=strategy,
        scoring=metrics,
    )
    aggregate = {
        col: {
            "mean": float(results[col].mean()),
            "std": float(results[col].std()),
        }
        for col in results.columns
        if col.startswith("test_")
    }
    if output is not None:
        results.to_csv(output)

    if fmt in (OutputFormat.json, OutputFormat.quiet):
        folds = [
            {
                k: (v if isinstance(v, (int, float, str, bool)) else str(v))
                for k, v in row.items()
            }
            for row in results.to_dict(orient="records")
        ]
        payload: dict = {"folds": folds, "aggregate": aggregate}
        if output is not None:
            payload["output"] = str(output)
        emit_record(
            payload,
            fmt,
            quiet_value="\n".join(f"{k}\t{v['mean']}" for k, v in aggregate.items()),
        )
    else:
        emit_frame(results, fmt)
        flat = {
            f"{name}.{stat}": value
            for name, stats in aggregate.items()
            for stat, value in stats.items()
        }
        emit_record(flat, fmt)
