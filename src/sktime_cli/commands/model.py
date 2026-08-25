"""``sktime-cli model``: inspect saved model artifacts."""

from __future__ import annotations

from pathlib import Path

import typer

from sktime_cli._cache import _jsonify_tag
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._models import estimator_scitype, load_model
from sktime_cli._output import OutputFormat, emit_record, resolve_format

app = typer.Typer(no_args_is_help=True)


@app.command("inspect")
@handle_errors
def inspect(
    path: Path = typer.Argument(..., help="Model .zip written by `run fit`."),
    fitted: bool = typer.Option(
        False, "--fitted", help="Include get_fitted_params() (can be large)."
    ),
    spec_only: bool = typer.Option(
        False, "--spec", help="Print only the spec string (reusable with run fit)."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Show class, spec, params, and tags of a saved model."""
    fmt = resolve_format(format_, json_)
    est = load_model(path)
    spec = str(est)
    if spec_only:
        # --spec exists to be captured, so it stays bare in every format that a
        # shell reads. Only --json owes a document, and its contract requires
        # one, so there it is an object rather than a naked string.
        if fmt == OutputFormat.json:
            emit_record({"spec": spec}, fmt, quiet_value=spec)
        else:
            print(spec)
        return

    record = {
        "class": type(est).__name__,
        "spec": spec,
        "scitype": estimator_scitype(est),
        "is_fitted": bool(getattr(est, "is_fitted", False)),
        "params": {k: _jsonify_tag(v) for k, v in est.get_params(deep=True).items()},
        "tags": {k: _jsonify_tag(v) for k, v in est.get_tags().items()},
    }
    if record["is_fitted"] and record["scitype"] == "forecaster":
        record["cutoff"] = str(est.cutoff[0])
    if fitted:
        try:
            record["fitted_params"] = {
                k: _jsonify_tag(v) for k, v in est.get_fitted_params().items()
            }
        except Exception as err:  # noqa: BLE001 - optional extra, never fatal
            record["fitted_params_error"] = str(err)
    emit_record(record, fmt, quiet_value=spec)
