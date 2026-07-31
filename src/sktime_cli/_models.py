"""Save/load helpers for model artifacts (sktime .zip serialization)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sktime_cli._cache import subdir
from sktime_cli._errors import CliError


def save_model(estimator, path: Path | None) -> Path:
    """Save a fitted estimator; returns the .zip path actually written."""
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = subdir("models") / f"{type(estimator).__name__}-{stamp}.zip"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = str(path)[: -len(".zip")] if str(path).endswith(".zip") else str(path)
    estimator.save(base)
    return Path(base + ".zip")


def load_model(path: str | Path):
    """Load an estimator from a .zip artifact written by ``save_model``."""
    from sktime.base import load

    path = Path(path)
    if path.suffix != ".zip":
        path = path.with_suffix(path.suffix + ".zip")
    if not path.exists():
        raise CliError("not_found", f"model file not found: {path}")
    try:
        return load(path)
    except Exception as err:
        raise CliError(
            "data_error",
            f"could not load model from {path}: {type(err).__name__}: {err}",
            hint="the artifact must come from est.save() / sktime-cli run fit",
        ) from err


def estimator_scitype(estimator) -> str:
    """Return the single scitype string of an estimator."""
    from sktime.registry import scitype

    return scitype(estimator)
