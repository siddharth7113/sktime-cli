"""``sktime-cli run``: one-shot fit / predict / transform / detect / evaluate."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import typer

from sktime_cli import _frames, _input, _io
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._input import Input, ReadOptions
from sktime_cli._models import estimator_scitype, load_model, save_model
from sktime_cli._output import (
    OutputFormat,
    emit_frame,
    emit_record,
    resolve_format,
)
from sktime_cli._scitypes import handler_for
from sktime_cli._specs import build_estimator, resolve_cv, resolve_metric

app = typer.Typer(no_args_is_help=True)

DATA_OPT = typer.Option(
    ...,
    "--data",
    help="Data file path, or a dataset name (e.g. airline, ucr:ArrowHead).",
)
SET_OPT = typer.Option(
    [], "--set", help="Parameter override key=value; __ nests (repeatable)."
)
TARGET_OPT = typer.Option(None, "--target", help="y column in --data.")
EXOG_OPT = typer.Option(None, "--exog", help="Exogenous X file.")
INDEX_COL_OPT = typer.Option(
    "auto", "--index-col", help="Time index column, or 'none'."
)
FREQ_OPT = typer.Option(None, "--freq", help="Pandas frequency for the index, e.g. M.")
LONG_OPT = typer.Option(
    False, "--long", help="Long-format panel; requires --id-col and --time-col."
)
ID_COL_OPT = typer.Option(
    None, "--id-col", help="Instance id column(s), comma-separated (long format)."
)
TIME_COL_OPT = typer.Option(None, "--time-col", help="Time column (long format).")
FH_OPT = typer.Option(None, "--fh", help="Horizon, e.g. 1:12.")
OUTPUT_OPT = typer.Option(
    None, "--output", "-o", help="Write results to a file instead of stdout."
)


def _read_opts(index_col, freq, long, id_col, time_col) -> ReadOptions:
    """Group the file-reading flags into one :class:`ReadOptions` value."""
    return ReadOptions(
        index_col=index_col, freq=freq, long=long, id_col=id_col, time_col=time_col
    )


def _looks_like_panel(obj) -> bool:
    """Report whether an object carries a MultiIndex, and so holds a panel."""
    import pandas as pd

    return isinstance(getattr(obj, "index", None), pd.MultiIndex)


# --------------------------------------------------------------------------
# fit dispatch


def _fit(est, handler: str, inp: Input, source: str, fh_text: str | None):
    """Fit an estimator, dispatching on its handler family.

    Parameters
    ----------
    est : sktime estimator
        The object to fit.
    handler : str
        Handler family from :func:`sktime_cli._scitypes.handler_for`.
    inp : Input
        Resolved data; which slot each part fills is decided here.
    source : str
        What ``--data`` named, for error messages.
    fh_text : str or None
        The ``--fh`` value, for forecasters that need a horizon at fit time.

    Returns
    -------
    tuple
        ``(n_obs, extras)``, where ``extras`` holds fields worth reporting in
        the manifest, such as a forecaster's cutoff.
    """
    if handler == "forecaster":
        return _fit_forecaster(est, inp, source, fh_text)
    if handler == "panel":
        return _fit_panel(est, inp)
    if handler in ("transformer", "detector"):
        X = inp.obj
        est.fit(X, inp.labels) if inp.labels is not None else est.fit(X)
        return len(X), {}
    raise CliError("internal", f"unhandled run handler: {handler}")


def _fit_forecaster(est, inp: Input, source: str, fh_text: str | None):
    """Fit a forecaster on a series, a panel, or a hierarchy.

    Panel and Hierarchical ``y`` are accepted, not just Series: sktime
    forecasters support global forecasting, and rejecting a panel here was a
    0.0.1 bug.

    See :func:`_fit` for the parameters.

    Returns
    -------
    tuple
        ``(n_obs, extras)``, where ``extras`` carries the cutoff and, for
        non-series input, the input kind.

    Raises
    ------
    CliError
        ``usage`` when the forecaster needs a horizon at fit time and none was
        given; ``data_error`` when the data cannot serve as ``y``.
    """
    y = _input.as_endogenous(inp, source)
    fh = _io.parse_fh(fh_text) if fh_text else None
    try:
        est.fit(y=y, X=inp.exog, fh=fh)
    except ValueError as err:
        if "fh" in str(err).lower():
            raise CliError(
                "usage",
                f"this forecaster requires the horizon at fit time: {err}",
                hint="pass --fh, e.g. --fh 1:12",
            ) from err
        raise
    extras = {}
    if est.cutoff is not None:
        extras["cutoff"] = str(est.cutoff[0])
    if inp.kind != "series":
        extras["input_kind"] = inp.kind
    return len(y), extras


def _check_panel_input(inp: Input) -> None:
    """Reject a single series where a panel is required.

    Parameters
    ----------
    inp : Input
        Resolved data.

    Raises
    ------
    CliError
        ``data_error`` hinting at the three ways to supply a panel: a ``.ts``
        file, a classification dataset, or a long-format file.
    """
    if inp.kind not in ("panel", "hierarchical") and not _looks_like_panel(inp.obj):
        raise CliError(
            "data_error",
            "this estimator needs Panel data, got a single series",
            hint=(
                "use a .ts file or a classification dataset, or read a "
                "long-format file with --long --id-col ID --time-col TIME"
            ),
        )


def _check_panel_labels(est, inp: Input) -> None:
    """Reject unlabelled data for an estimator that needs labels.

    Clusterers fit without labels; classifiers and regressors do not, and
    handing them ``None`` fails deep inside sktime with an unpacking error.

    Raises
    ------
    CliError
        ``data_error`` explaining where labels have to come from.
    """
    if inp.labels is None and estimator_scitype(est) != "clusterer":
        raise CliError(
            "data_error",
            "training data has no labels",
            hint=(
                "labels have to come with the data: use a .ts file that carries "
                "them, or a named classification dataset"
            ),
        )


def _fit_panel(est, inp: Input):
    """Fit a classifier, regressor, or clusterer on panel data.

    See :func:`_fit` for the parameters.

    Returns
    -------
    tuple
        ``(n_obs, extras)``.

    Raises
    ------
    CliError
        ``data_error`` for series input, or for unlabelled data given to an
        estimator that needs labels. Clusterers fit without labels.
    """
    _check_panel_input(inp)
    _check_panel_labels(est, inp)
    X, y = inp.obj, inp.labels
    est.fit(X, y) if y is not None else est.fit(X)
    return len(X), {}


# --------------------------------------------------------------------------
# predict dispatch


def _require_proba(est, mode: str) -> None:
    """Check a forecaster can produce probabilistic output before asking it to.

    Without this the failure surfaces as an sktime traceback partway through
    prediction; the tag says up front whether it is even possible.

    Parameters
    ----------
    est : sktime forecaster
        The fitted forecaster.
    mode : str
        Which flag was passed, named in the error.

    Raises
    ------
    CliError
        ``usage`` naming the ``capability:pred_int`` tag, with the registry
        search that finds forecasters carrying it.
    """
    if not est.get_tag("capability:pred_int", False, raise_error=False):
        raise CliError(
            "usage",
            f"{type(est).__name__} does not support probabilistic forecasts",
            hint=(
                "find one that does with: sktime-cli registry search forecaster "
                "-t capability:pred_int=True"
            ),
            detail=f"--{mode} needs the capability:pred_int tag",
        )


def _predict_forecaster(est, fh_text, X, mode: str, levels, wide: bool):
    """Produce a point or probabilistic forecast.

    Parameters
    ----------
    est : sktime forecaster
        The fitted forecaster.
    fh_text : str or None
        The ``--fh`` value. May be ``None`` when the horizon was fixed at fit
        time.
    X : pd.DataFrame or None
        Exogenous data for the forecast period.
    mode : {"point", "interval", "quantiles", "var"}
        Which kind of forecast to produce.
    levels : list of float or None
        Coverages or alphas. Defaults per mode when ``None``.
    wide : bool
        Keep sktime's native column layout instead of melting to long form.

    Returns
    -------
    pd.Series or pd.DataFrame
        The forecast. Probabilistic modes come back in the long form described
        in :mod:`sktime_cli._frames` unless ``wide`` is set.

    Raises
    ------
    CliError
        ``usage`` when no horizon is available, or the forecaster cannot
        produce probabilistic output.
    """
    fh = _io.parse_fh(fh_text) if fh_text else None

    def shape(raw, names):
        return _frames.widen(raw) if wide else _frames.melt(raw, names)

    try:
        if mode == "point":
            return est.predict(fh=fh, X=X)
        _require_proba(est, mode)
        if mode == "interval":
            raw = est.predict_interval(fh=fh, X=X, coverage=levels or [0.9])
            return shape(raw, _frames.INTERVAL_LEVELS)
        if mode == "quantiles":
            raw = est.predict_quantiles(fh=fh, X=X, alpha=levels or [0.05, 0.95])
            return shape(raw, _frames.QUANTILE_LEVELS)
        if mode == "var":
            # predict_var labels its column 0 rather than by variable; relabel
            # so --var reports the same name --interval and --quantiles do
            raw = est.predict_var(fh=fh, X=X)
            return shape(_frames.name_columns_like(raw, est), _frames.VAR_LEVELS)
    except ValueError as err:
        if "fh" in str(err).lower():
            raise CliError(
                "usage", f"no forecasting horizon: {err}", hint="pass --fh, e.g. 1:12"
            ) from err
        raise
    raise CliError("internal", f"unhandled predict mode: {mode}")


def _predict_panel(est, X, proba: bool):
    """Predict labels, or class probabilities, for panel data.

    Parameters
    ----------
    est : sktime estimator
        A fitted classifier, regressor, or clusterer.
    X : pd.DataFrame
        Panel data to predict on.
    proba : bool
        Return per-class probabilities rather than labels.

    Returns
    -------
    pd.Series or pd.DataFrame
        Labels as a Series, or probabilities as a frame with one column per
        class, named from the estimator's ``classes_``.
    """
    import pandas as pd

    if proba:
        result = est.predict_proba(X)
        classes = [str(c) for c in getattr(est, "classes_", range(result.shape[1]))]
        return pd.DataFrame(result, columns=classes)
    return pd.Series(est.predict(X), name="prediction")


def _detector_kind(est) -> str:
    """Return the result kind a detector's ``task`` tag implies."""
    task = str(est.get_tag("task", "segmentation", raise_error=False))
    return "segments" if "segment" in task else "points"


def _detector_result(est, X, kind: str):
    """Run the detector method that ``--kind`` asked for.

    Parameters
    ----------
    est : sktime detector
        The fitted detector.
    X : pd.DataFrame
        Data to run over.
    kind : {"auto", "points", "segments", "scores"}
        Which result to produce. ``auto`` reads the detector's ``task`` tag,
        giving segments for segmenters and points for anomaly and change point
        detectors.

    Returns
    -------
    tuple
        ``(frame, resolved_kind)``. Segments are flattened to ``start`` and
        ``end`` columns so they survive a file round trip.

    Raises
    ------
    CliError
        ``usage`` for an unknown kind, or for one this detector cannot produce.
        Detectors signal that inconsistently, by raising ``NotImplementedError``
        from the base class or ``AttributeError`` while converting a result they
        never built, so both are treated as "cannot".
    """
    if kind not in ("auto", "points", "segments", "scores"):
        raise CliError(
            "usage", f"invalid --kind {kind!r}: use auto|points|segments|scores"
        )
    native = _detector_kind(est)
    if kind == "auto":
        kind = native
    try:
        if kind == "points":
            return _frames.to_frame(est.predict_points(X), name="point"), kind
        if kind == "segments":
            return _frames.segments_to_frame(est.predict_segments(X)), kind
        return _frames.to_frame(est.predict_scores(X), name="score"), kind
    except (NotImplementedError, AttributeError) as err:
        hint = (
            f"this detector reports {native}: use --kind {native}"
            if native != kind
            else "try --kind segments or --kind points"
        )
        raise CliError(
            "usage",
            f"{type(est).__name__} cannot report {kind}",
            hint=hint,
            detail=f"{type(err).__name__}: {err}",
        ) from err


def _emit_result(
    result, output: Path | None, fmt: OutputFormat, extra: dict | None = None
) -> None:
    """Write a frame result to --output, or stream it to stdout.

    With ``--output`` stdout carries a manifest, so side facts like a persisted
    model path belong in it. Without it stdout carries the data itself, so
    those facts go to stderr rather than corrupting the result stream.
    """
    if output is not None:
        files = _io.write_any(result, output)
        emit_record(
            {"files": files, "n": int(len(result)), **(extra or {})},
            fmt,
            quiet_value=files[0],
        )
        return
    emit_frame(result, fmt)
    for key, value in (extra or {}).items():
        print(f"{key}: {value}", file=sys.stderr)


def _proba_mode(interval, quantiles, var, residuals) -> str:
    """Collapse the four probabilistic flags into one mode.

    Returns
    -------
    str
        The chosen mode, or ``"point"`` when none was given.

    Raises
    ------
    CliError
        ``usage`` when more than one was given, naming which.
    """
    chosen = [
        name
        for name, on in (
            ("interval", interval is not None),
            ("quantiles", quantiles is not None),
            ("var", var),
            ("residuals", residuals),
        )
        if on
    ]
    if len(chosen) > 1:
        raise CliError("usage", f"--{' and --'.join(chosen)} are mutually exclusive")
    return chosen[0] if chosen else "point"


def _parse_levels(text: str | None) -> list[float] | None:
    """Parse the comma-separated coverages or alphas of a probabilistic flag.

    Parameters
    ----------
    text : str or None
        E.g. ``"0.8,0.95"``.

    Returns
    -------
    list of float or None
        The levels, or ``None`` when the flag was absent, which lets the
        caller apply a per-mode default.

    Raises
    ------
    CliError
        ``usage`` for anything non-numeric, showing the expected form.
    """
    if not text:
        return None
    try:
        return [float(part) for part in text.split(",") if part.strip()]
    except ValueError as err:
        raise CliError(
            "usage", f"invalid level list {text!r}: use e.g. 0.8,0.95"
        ) from err


# --------------------------------------------------------------------------
# commands


@app.command("fit")
@handle_errors
def fit(
    spec: str = typer.Argument(
        ..., help='Estimator spec, e.g. "NaiveForecaster(sp=12)".'
    ),
    data: str = DATA_OPT,
    target: str | None = TARGET_OPT,
    exog: Path | None = EXOG_OPT,
    index_col: str = INDEX_COL_OPT,
    freq: str | None = FREQ_OPT,
    long: bool = LONG_OPT,
    id_col: str | None = ID_COL_OPT,
    time_col: str | None = TIME_COL_OPT,
    fh: str | None = FH_OPT,
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
    handler = handler_for(scitype)
    inp = _input.load(
        data, _read_opts(index_col, freq, long, id_col, time_col), target, exog
    )
    n_obs, extras = _fit(est, handler, inp, data, fh)
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
    fh: str | None = FH_OPT,
    data: str | None = typer.Option(
        None, "--data", help="X data: exog for forecasters, panel for classifiers."
    ),
    index_col: str = INDEX_COL_OPT,
    freq: str | None = FREQ_OPT,
    long: bool = LONG_OPT,
    id_col: str | None = ID_COL_OPT,
    time_col: str | None = TIME_COL_OPT,
    proba: bool = typer.Option(False, "--proba", help="Class probabilities."),
    interval: str | None = typer.Option(
        None, "--interval", help="Prediction intervals at coverage(s), e.g. 0.8,0.95."
    ),
    quantiles: str | None = typer.Option(
        None, "--quantiles", help="Quantile forecasts at alpha(s), e.g. 0.1,0.9."
    ),
    var: bool = typer.Option(False, "--var", help="Forecast variance."),
    residuals: bool = typer.Option(
        False, "--residuals", help="In-sample residuals; --data carries the y series."
    ),
    wide: bool = typer.Option(
        False, "--wide", help="Keep sktime's native columns, joined with __."
    ),
    output: Path | None = OUTPUT_OPT,
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Predict from a saved model: point, probabilistic, or panel results."""
    fmt = resolve_format(format_, json_)
    est = load_model(model)
    handler = handler_for(estimator_scitype(est))
    opts = _read_opts(index_col, freq, long, id_col, time_col)
    loaded = _input.load(data, opts) if data else None

    if handler == "forecaster":
        if proba:
            raise CliError(
                "usage",
                "--proba applies to classifiers, not forecasters",
                hint="for forecast uncertainty use --interval, --quantiles or --var",
            )
        mode = _proba_mode(interval, quantiles, var, residuals)
        if mode == "residuals":
            if loaded is None:
                raise CliError("usage", "--residuals needs --data with the y series")
            result = _frames.to_frame(est.predict_residuals(loaded.obj), "residual")
        else:
            result = _predict_forecaster(
                est,
                fh,
                loaded.obj if loaded is not None else None,
                mode,
                _parse_levels(interval or quantiles),
                wide,
            )
        _emit_result(result, output, fmt)
        return

    if loaded is None:
        raise CliError("usage", "predict needs --data with the input data")
    forecast_only = _proba_mode(interval, quantiles, var, residuals)
    if forecast_only != "point":
        raise CliError(
            "usage",
            f"--{forecast_only} applies to forecasters, not {handler}s",
            hint="for class probabilities use --proba",
        )
    if handler == "panel":
        result = _predict_panel(est, loaded.obj, proba)
    elif handler == "transformer":
        result = _frames.to_frame(est.transform(loaded.obj))
    else:  # detector
        result, _kind = _detector_result(est, loaded.obj, "auto")
    _emit_result(result, output, fmt)


@app.command("fit-predict")
@handle_errors
def fit_predict(
    spec: str = typer.Argument(
        ..., help='Estimator spec, e.g. "NaiveForecaster(sp=12)".'
    ),
    data: str = DATA_OPT,
    target: str | None = TARGET_OPT,
    exog: Path | None = EXOG_OPT,
    index_col: str = INDEX_COL_OPT,
    freq: str | None = FREQ_OPT,
    long: bool = LONG_OPT,
    id_col: str | None = ID_COL_OPT,
    time_col: str | None = TIME_COL_OPT,
    fh: str | None = FH_OPT,
    set_: list[str] = SET_OPT,
    model_out: Path | None = typer.Option(
        None, "--model-out", help="Also persist the fitted model."
    ),
    output: Path | None = OUTPUT_OPT,
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Fit and predict in one process (forecast fh, or in-sample for panels)."""
    fmt = resolve_format(format_, json_)
    est = build_estimator(spec, set_)
    handler = handler_for(estimator_scitype(est))
    inp = _input.load(
        data, _read_opts(index_col, freq, long, id_col, time_col), target, exog
    )

    if handler == "forecaster":
        if not fh:
            raise CliError("usage", "fit-predict needs --fh for forecasters")
        _fit(est, handler, inp, data, fh)
        pred = est.predict()
    elif handler == "panel":
        # fit_predict, not fit+predict: sktime cross-validates the out-of-sample
        # part, so in-sample predictions are not optimistic.
        _check_panel_input(inp)
        _check_panel_labels(est, inp)
        import pandas as pd

        pred = pd.Series(est.fit_predict(inp.obj, inp.labels), name="prediction")
    elif handler == "transformer":
        if fh:
            raise CliError(
                "usage",
                "transformers have no forecasting horizon, so --fh does not apply",
                hint="drop --fh, or use: sktime-cli run transform",
            )
        pred = _frames.to_frame(est.fit_transform(inp.obj, inp.labels))
    else:  # detector
        est.fit(inp.obj)
        pred, _kind = _detector_result(est, inp.obj, "auto")

    if model_out is not None:
        path = save_model(est, model_out)
        print(f"model saved: {path}", file=sys.stderr)
    _emit_result(pred, output, fmt)


@app.command("transform")
@handle_errors
def transform(
    spec: str | None = typer.Argument(
        None, help='Transformer spec, e.g. "Detrender()". Omit when using --model.'
    ),
    data: str = DATA_OPT,
    model: Path | None = typer.Option(
        None, "--model", help="Fitted transformer .zip, instead of a spec."
    ),
    target: str | None = TARGET_OPT,
    index_col: str = INDEX_COL_OPT,
    freq: str | None = FREQ_OPT,
    long: bool = LONG_OPT,
    id_col: str | None = ID_COL_OPT,
    time_col: str | None = TIME_COL_OPT,
    inverse: bool = typer.Option(
        False, "--inverse", help="Apply inverse_transform instead of transform."
    ),
    set_: list[str] = SET_OPT,
    model_out: Path | None = typer.Option(
        None, "--model-out", help="Persist the fitted transformer."
    ),
    output: Path | None = OUTPUT_OPT,
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Transform data with a transformer spec or a saved fitted transformer."""
    fmt = resolve_format(format_, json_)
    if spec is None and model is None:
        raise CliError(
            "usage",
            "pass a transformer spec, or --model with a fitted one",
            hint='e.g. run transform "Detrender()" --data FILE',
        )
    if spec is not None and model is not None:
        raise CliError("usage", "pass a transformer spec or --model, not both")

    est = load_model(model) if model is not None else build_estimator(spec, set_)
    scitype = estimator_scitype(est)
    if handler_for(scitype) != "transformer":
        raise CliError(
            "usage",
            f"run transform needs a transformer, got a {scitype}",
            hint="fit and predict other estimators with: sktime-cli run fit-predict",
        )

    inp = _input.load(data, _read_opts(index_col, freq, long, id_col, time_col), target)
    if inverse and not est.get_tag(
        "capability:inverse_transform", False, raise_error=False
    ):
        raise CliError(
            "usage",
            f"{type(est).__name__} does not support inverse_transform",
            hint=(
                "find one that does with: sktime-cli registry search transformer "
                "-t capability:inverse_transform=True"
            ),
        )

    if model is None:
        est.fit(inp.obj, inp.labels) if inp.labels is not None else est.fit(inp.obj)
    result = est.inverse_transform(inp.obj) if inverse else est.transform(inp.obj)

    extra = {}
    if model_out is not None:
        extra["model"] = str(save_model(est, model_out))
    _emit_result(_frames.to_frame(result), output, fmt, extra)


@app.command("detect")
@handle_errors
def detect(
    spec: str | None = typer.Argument(
        None, help='Detector spec, e.g. "ClaSPSegmentation()". Omit with --model.'
    ),
    data: str = DATA_OPT,
    model: Path | None = typer.Option(
        None, "--model", help="Fitted detector .zip, instead of a spec."
    ),
    kind: str = typer.Option(
        "auto", "--kind", help="Result kind: auto|points|segments|scores."
    ),
    target: str | None = TARGET_OPT,
    index_col: str = INDEX_COL_OPT,
    freq: str | None = FREQ_OPT,
    long: bool = LONG_OPT,
    id_col: str | None = ID_COL_OPT,
    time_col: str | None = TIME_COL_OPT,
    set_: list[str] = SET_OPT,
    model_out: Path | None = typer.Option(
        None, "--model-out", help="Persist the fitted detector."
    ),
    output: Path | None = OUTPUT_OPT,
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Detect anomalies, change points, or segments in a series."""
    fmt = resolve_format(format_, json_)
    if spec is None and model is None:
        raise CliError(
            "usage",
            "pass a detector spec, or --model with a fitted one",
            hint='e.g. run detect "HampelDetector()" --data FILE',
        )
    if spec is not None and model is not None:
        raise CliError("usage", "pass a detector spec or --model, not both")

    est = load_model(model) if model is not None else build_estimator(spec, set_)
    scitype = estimator_scitype(est)
    if handler_for(scitype) != "detector":
        raise CliError("usage", f"run detect needs a detector, got a {scitype}")

    inp = _input.load(data, _read_opts(index_col, freq, long, id_col, time_col), target)
    if model is None:
        est.fit(inp.obj)
    result, resolved = _detector_result(est, inp.obj, kind)

    extra = {"kind": resolved}
    if model_out is not None:
        extra["model"] = str(save_model(est, model_out))
    _emit_result(result, output, fmt, extra)


@app.command("evaluate")
@handle_errors
def evaluate_cmd(
    spec: str = typer.Argument(
        ..., help='Estimator spec, e.g. "NaiveForecaster(sp=12)".'
    ),
    data: str = DATA_OPT,
    target: str | None = TARGET_OPT,
    exog: Path | None = EXOG_OPT,
    index_col: str = INDEX_COL_OPT,
    freq: str | None = FREQ_OPT,
    long: bool = LONG_OPT,
    id_col: str | None = ID_COL_OPT,
    time_col: str | None = TIME_COL_OPT,
    cv: str | None = typer.Option(
        None,
        "--cv",
        help='Splitter spec, e.g. "ExpandingWindowSplitter(initial_window=72)".',
    ),
    metric: list[str] = typer.Option(
        [], "--metric", help="Metric name or spec (repeatable)."
    ),
    strategy: str = typer.Option(
        "refit", "--strategy", help="refit|update|no-update_params (forecasters)."
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
    """Backtest a forecaster, classifier, or regressor with cross-validation."""
    fmt = resolve_format(format_, json_)
    est = build_estimator(spec, set_)
    scitype = estimator_scitype(est)
    handler = handler_for(scitype)
    if handler not in ("forecaster", "panel"):
        raise CliError(
            "usage",
            "run evaluate supports forecasters, classifiers, and regressors, "
            f"got a {scitype}",
        )
    inp = _input.load(
        data, _read_opts(index_col, freq, long, id_col, time_col), target, exog
    )
    if handler == "forecaster":
        results = _evaluate_forecaster(
            est, inp, data, cv, metric, strategy, fh, initial_window
        )
    else:
        results = _evaluate_panel(est, inp, scitype, cv, metric)
    _emit_evaluation(results, output, fmt)


def _evaluate_forecaster(est, inp, source, cv, metric, strategy, fh, initial_window):
    """Backtest a forecaster over a rolling split.

    Parameters
    ----------
    est : sktime forecaster
        The forecaster to score.
    inp : Input
        Resolved data.
    source : str
        What ``--data`` named, for error messages.
    cv : str or None
        Splitter spec. When absent, an expanding window is built from ``fh``.
    metric : list of str
        Metric names or specs. Defaults to mean absolute percentage error.
    strategy : {"refit", "update", "no-update_params"}
        What happens to the model between folds.
    fh : str or None
        Horizon for the default splitter.
    initial_window : int or None
        Training size for the first fold of the default splitter.

    Returns
    -------
    pd.DataFrame
        One row per fold, with a ``test_<Metric>`` column per metric.

    Raises
    ------
    CliError
        ``usage`` for an unknown strategy, or when neither ``cv`` nor ``fh``
        was given.
    """
    from sktime.forecasting.model_evaluation import evaluate

    if strategy not in ("refit", "update", "no-update_params"):
        raise CliError("usage", f"invalid --strategy {strategy!r}")
    if not cv and not fh:
        raise CliError("usage", "pass --cv, or --fh to use a default expanding window")

    y = _input.as_endogenous(inp, source)
    fh_obj = _io.parse_fh(fh) if fh else None
    splitter = resolve_cv(cv, fh_obj, initial_window, len(y))
    metrics = [resolve_metric(m) for m in metric] or [
        resolve_metric("MeanAbsolutePercentageError")
    ]
    return evaluate(
        forecaster=est,
        cv=splitter,
        y=y,
        X=inp.exog,
        strategy=strategy,
        scoring=metrics,
        error_score="raise",
    )


def _panel_evaluate(scitype: str):
    """Find sktime's cross-validation utility for a panel scitype.

    sktime follows a convention rather than publishing a registry of these:
    ``sktime.<task>.model_evaluation.evaluate`` takes the estimator as a
    keyword named after the scitype. Resolving it by convention means a task
    module added upstream works here with no change; a scitype with no such
    module raises, which is how clusterers and detectors are rejected.
    """
    task = {"classifier": "classification", "regressor": "regression"}.get(scitype)
    if task is None:
        raise CliError(
            "usage",
            f"sktime has no cross-validation utility for {scitype}s",
            hint="evaluate supports forecasters, classifiers, and regressors",
        )
    try:
        module = importlib.import_module(f"sktime.{task}.model_evaluation")
        return module.evaluate, scitype
    except (ImportError, AttributeError) as err:
        raise CliError(
            "usage",
            f"this sktime version cannot evaluate {scitype}s",
            detail=str(err),
        ) from err


def _evaluate_panel(est, inp, scitype: str, cv, metric):
    """Cross-validate a classifier or regressor across instances.

    Parameters
    ----------
    est : sktime estimator
        The classifier or regressor to score.
    inp : Input
        Resolved data, which must carry labels.
    scitype : str
        The estimator's scitype, used to find sktime's evaluate utility.
    cv : str or None
        Splitter spec. Defaults to 3-fold cross-validation.
    metric : list of str
        Metric names. Defaults to sktime's own choice for the task.

    Returns
    -------
    pd.DataFrame
        One row per fold.

    Raises
    ------
    CliError
        ``data_error`` for unlabelled data; ``usage`` for a scitype sktime
        cannot cross-validate.

    Notes
    -----
    ``error_score="raise"`` is passed, so a fold that fails becomes an error
    rather than a silent ``NaN`` column.
    """
    evaluate, arg_name = _panel_evaluate(scitype)

    if inp.labels is None:
        raise CliError(
            "data_error",
            "evaluate needs labelled Panel data",
            hint=(
                "labels have to come with the data: use a .ts file that carries "
                "them, or a named classification dataset"
            ),
        )
    kwargs = {
        arg_name: est,
        "cv": _resolve_panel_cv(cv),
        "X": inp.obj,
        "y": inp.labels,
        # surface a failing fold as a CLI error instead of a silent NaN score
        "error_score": "raise",
    }
    if metric:
        kwargs["scoring"] = [_resolve_panel_metric(m) for m in metric]
    return evaluate(**kwargs)


def _resolve_panel_metric(name: str):
    """Resolve a metric for panel evaluation.

    Panel results are scored per instance, so these are sklearn's metrics.
    sktime's own metric objects are for forecasting and cannot score labels;
    passing one used to crash inside sktime, so it is refused here.

    Parameters
    ----------
    name : str
        A metric name, e.g. ``"accuracy_score"``.

    Returns
    -------
    callable
        The metric function.

    Raises
    ------
    CliError
        ``not_found`` naming sklearn.metrics as the place these come from.
    """
    import sklearn.metrics

    func = getattr(sklearn.metrics, name, None)
    if callable(func):
        return func
    from sktime_cli import _cache

    record = _cache.lookup(name)
    hint = "classifier and regressor metrics come from sklearn.metrics, "
    if record is not None:
        hint += f"but {name} is an sktime forecasting metric"
    else:
        hint += "e.g. accuracy_score, f1_score, r2_score"
    raise CliError("not_found", f"unknown metric for this estimator: {name}", hint=hint)


def _resolve_panel_cv(cv: str | None):
    """Resolve ``--cv`` for panel evaluation.

    Panel folds are drawn across instances rather than across time, so the
    splitters that fit are sklearn's. Those are not in sktime's registry, so
    they are injected into the spec namespace here.

    Parameters
    ----------
    cv : str or None
        A splitter spec such as ``"StratifiedKFold(n_splits=5)"``.

    Returns
    -------
    Any
        A splitter, defaulting to shuffled 3-fold cross-validation with a
        fixed seed so repeated runs are comparable.
    """
    import sklearn.model_selection as skcv

    if cv:
        splitters = {
            name: getattr(skcv, name)
            for name in dir(skcv)
            if not name.startswith("_")
            and name.endswith(("Fold", "Split", "ShuffleSplit"))
        }
        return build_estimator(cv, extra_names=splitters)
    return skcv.KFold(n_splits=3, shuffle=True, random_state=42)


def _emit_evaluation(results, output: Path | None, fmt: OutputFormat) -> None:
    """Write evaluation results, per fold and aggregated.

    The aggregate is what makes runs comparable: one mean and standard
    deviation per metric, so two candidate estimators can be ranked without
    reading every fold.

    Parameters
    ----------
    results : pd.DataFrame
        One row per fold, as sktime's evaluate returns.
    output : Path or None
        Where to also write the per-fold rows as CSV.
    fmt : OutputFormat
        A concrete format from :func:`resolve_format`.
    """
    aggregate = {
        col: {"mean": float(results[col].mean()), "std": float(results[col].std())}
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
