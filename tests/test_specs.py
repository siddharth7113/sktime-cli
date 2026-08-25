import pytest

from sktime_cli._errors import CliError
from sktime_cli._specs import apply_sets, build_estimator, parse_value, resolve_metric


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12", 12),
        ("0.5", 0.5),
        ("true", True),
        ("True", True),
        ("null", None),
        ("None", None),
        ("[1, 2]", [1, 2]),
        ("last", "last"),
        ("'last'", "last"),
    ],
)
def test_parse_value(text, expected):
    assert parse_value(text) == expected


def test_bare_class_name_instantiates_defaults():
    est = build_estimator("NaiveForecaster")
    assert type(est).__name__ == "NaiveForecaster"
    assert est.get_params()["sp"] == 1


def test_expression_spec():
    est = build_estimator("NaiveForecaster(sp=12, strategy='mean')")
    assert est.get_params()["sp"] == 12
    assert est.get_params()["strategy"] == "mean"


def test_composition_spec():
    est = build_estimator("ExponentTransformer() * NaiveForecaster(sp=4)")
    assert type(est).__name__ == "TransformedTargetForecaster"


def test_return_block_spec():
    spec = "f = NaiveForecaster(sp=3)\nreturn f"
    est = build_estimator(spec)
    assert est.get_params()["sp"] == 3


def test_set_override():
    est = build_estimator("NaiveForecaster(sp=12)", ["sp=4"])
    assert est.get_params()["sp"] == 4


def test_set_nested_override():
    est = build_estimator("ExponentTransformer() * NaiveForecaster()")
    param = next(p for p in est.get_params(deep=True) if p.endswith("__sp"))
    apply_sets(est, [f"{param}=9"])
    assert est.get_params(deep=True)[param] == 9


def test_set_bad_key_is_usage_error():
    with pytest.raises(CliError) as excinfo:
        build_estimator("NaiveForecaster()", ["nope=1"])
    assert excinfo.value.code == "usage"


def test_missing_dependency_estimator():
    with pytest.raises(CliError) as excinfo:
        build_estimator("AutoARIMA()")
    assert excinfo.value.code == "missing_dependency"
    assert "pmdarima" in (excinfo.value.hint or "")


def test_invalid_syntax_is_spec_error():
    with pytest.raises(CliError) as excinfo:
        build_estimator("NaiveForecaster(sp=")
    assert excinfo.value.code == "spec_error"


def test_resolve_metric_by_name():
    metric = resolve_metric("MeanAbsolutePercentageError")
    assert type(metric).__name__ == "MeanAbsolutePercentageError"


def test_resolve_metric_unknown():
    with pytest.raises(CliError) as excinfo:
        resolve_metric("NotAMetric")
    assert excinfo.value.code == "not_found"


def test_sklearn_metric_is_pointed_at_the_command_that_takes_it():
    """`metrics score --metric accuracy_score` used to send you to search
    forecasting metrics, which will never contain it."""
    with pytest.raises(CliError) as excinfo:
        resolve_metric("accuracy_score")
    error = excinfo.value
    assert error.code == "not_found"
    assert "run evaluate" in error.hint
    assert "metric_forecasting" not in error.hint


def test_an_unknown_metric_name_points_at_the_listing_command():
    with pytest.raises(CliError) as excinfo:
        resolve_metric("MeanAbsolutePercentageErrr")
    assert excinfo.value.hint == "list metrics with: sktime-cli metrics list"
