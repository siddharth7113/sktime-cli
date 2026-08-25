"""Save/load helpers for model artifacts (sktime .zip serialization)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sktime_cli._cache import subdir
from sktime_cli._errors import CliError


def save_model(estimator, path: Path | None) -> Path:
    """Serialize a fitted estimator to a ``.zip`` artifact.

    Parameters
    ----------
    estimator : sktime estimator
        The fitted object to save.
    path : Path or None
        Destination. A ``.zip`` suffix is added if absent, since sktime's
        ``save`` appends it. When ``None``, a timestamped name is generated
        under the workspace ``models`` directory.

    Returns
    -------
    Path
        The file actually written, which is what callers report so the user
        can pass it back to ``--model``.
    """
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = subdir("models") / f"{type(estimator).__name__}-{stamp}.zip"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = str(path)[: -len(".zip")] if str(path).endswith(".zip") else str(path)
    estimator.save(base)
    return Path(base + ".zip")


def load_model(path: str | Path):
    """Load an estimator from a ``.zip`` artifact.

    Parameters
    ----------
    path : str or Path
        The artifact to load. A missing ``.zip`` suffix is added.

    Returns
    -------
    sktime estimator
        The estimator, still fitted.

    Raises
    ------
    CliError
        ``not_found`` if the file does not exist; ``data_error`` if it exists
        but is not an sktime artifact, hinting at what does produce one.
    """
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
    """Return an estimator's scitype.

    Parameters
    ----------
    estimator : sktime estimator
        Object to classify. May be fitted or not.

    Returns
    -------
    str
        One scitype string, e.g. ``"forecaster"``. Feed it to
        :func:`sktime_cli._scitypes.handler_for` to find the handler.
    """
    from sktime.registry import scitype

    return scitype(estimator)
