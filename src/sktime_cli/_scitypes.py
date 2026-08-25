"""Single source of truth for which sktime scitypes ``run`` can dispatch on.

Every scitype sktime declares is classified here exactly once: either it maps
to a ``run`` handler, or it is listed with the reason it is out of scope and
the command to use instead. ``tests/test_scitypes.py`` asserts the
classification is total against ``BASE_CLASS_SCITYPE_LIST`` *and* against the
``object_type`` tags actually observed in the registry, so a scitype added
upstream fails the suite instead of silently widening the coverage gap.

Regenerate the coverage table in ``docs/roadmap.md`` with
``python scripts/scitype_coverage.py``.
"""

from __future__ import annotations

from sktime_cli._errors import CliError

# scitype -> handler family used by ``run``.
#
# "forecaster"  : fit(y, X, fh) / predict(fh, X), incl. global forecasting
# "panel"       : fit(X, y) / predict(X) over Panel data
# "transformer" : fit/transform/inverse_transform (reconcilers are transformers)
# "detector"    : fit/predict + predict_points/segments/scores
SUPPORTED: dict[str, str] = {
    "forecaster": "forecaster",
    "classifier": "panel",
    "regressor": "panel",
    "clusterer": "panel",
    "early_classifier": "panel",
    "transformer": "transformer",
    "reconciler": "transformer",
    "detector": "detector",
}

# scitype -> why ``run`` does not dispatch on it, phrased as a CLI hint.
UNSUPPORTED: dict[str, str] = {
    # not estimators: other commands own these
    "dataset": "datasets are loaded with: sktime-cli datasets load",
    "dataset_forecasting": "datasets are loaded with: sktime-cli datasets load",
    "dataset_classification": "datasets are loaded with: sktime-cli datasets load",
    "dataset_regression": "datasets are loaded with: sktime-cli datasets load",
    "catalogue": "catalogues are listed with: sktime-cli catalogues list",
    "splitter": "splitters are used via --cv, or: sktime-cli data split --cv",
    "metric": "metrics are used via --metric, or: sktime-cli metrics score",
    "metric_forecasting": "metrics are used via --metric, or: sktime-cli metrics score",
    "metric_forecasting_proba": (
        "metrics are used via --metric, or: sktime-cli metrics score"
    ),
    "metric_detection": "metrics are used via --metric, or: sktime-cli metrics score",
    # abstract categories, never a concrete object's only type
    "object": "an abstract category, not a runnable estimator",
    "estimator": "an abstract category, not a runnable estimator",
    # components used inside other estimators
    "network": "neural network components are used inside classifiers/regressors",
    "interval_scorer": "cost and saving components are used inside detectors",
    "transformer-pairwise": "pairwise transformers are used inside other estimators",
    "transformer-pairwise-panel": (
        "pairwise panel transformers are used inside other estimators"
    ),
    # deferred to a later version
    "param_est": (
        "parameter estimators are not yet exposed; fit one with a spec inside "
        "another estimator, or read: sktime-cli model inspect --fitted"
    ),
    "aligner": "aligners are not yet exposed by run",
}


def handler_for(scitype: str) -> str:
    """Find which ``run`` handler family deals with an object of this scitype.

    Parameters
    ----------
    scitype : str
        An sktime scitype, as returned by ``sktime.registry.scitype``.

    Returns
    -------
    {"forecaster", "panel", "transformer", "detector"}
        The handler family, from :data:`SUPPORTED`.

    Raises
    ------
    CliError
        ``usage`` either way, but with different hints: a scitype in
        :data:`UNSUPPORTED` gets the command that does handle it, while one
        this version has never heard of gets the issue tracker, because that
        means sktime added a category upstream.
    """
    handler = SUPPORTED.get(scitype)
    if handler is not None:
        return handler
    reason = UNSUPPORTED.get(scitype)
    if reason is not None:
        raise CliError("usage", f"run does not support {scitype} objects", hint=reason)
    raise CliError(
        "usage",
        f"unknown object type: {scitype}",
        hint=(
            "this sktime version declares a scitype sktime-cli does not know; "
            "please report it at https://github.com/siddharth7113/sktime-cli/issues"
        ),
    )
