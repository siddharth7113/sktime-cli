import json

import pytest


@pytest.fixture(scope="module")
def model_zip(invoke, airline_csv, tmp_path_factory):
    path = tmp_path_factory.mktemp("models") / "naive.zip"
    result = invoke(
        "run",
        "fit",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--model-out",
        path,
        "--json",
    )
    assert result.exit_code == 0, result.output
    return path


def test_fit_manifest(invoke, airline_csv, tmp_path):
    out = tmp_path / "m.zip"
    result = invoke(
        "run",
        "fit",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--model-out",
        out,
        "--json",
    )
    payload = json.loads(result.stdout)
    assert payload["model"] == str(out)
    assert payload["estimator"] == "NaiveForecaster(sp=12)"
    assert payload["cutoff"] == "1960-12"
    assert out.exists()


def test_fit_with_set_override(invoke, airline_csv, tmp_path):
    out = tmp_path / "m4.zip"
    result = invoke(
        "run",
        "fit",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--set",
        "sp=4",
        "--model-out",
        out,
        "--json",
    )
    assert json.loads(result.stdout)["estimator"] == "NaiveForecaster(sp=4)"


def test_predict_seasonal_naive(invoke, model_zip):
    result = invoke("run", "predict", "--model", model_zip, "--fh", "1:12", "--json")
    payload = json.loads(result.stdout)
    assert len(payload["data"]) == 12
    assert payload["data"][0] == [417.0]
    assert payload["index"][0] == "1961-01"


def test_predict_without_fh_hints(invoke, model_zip):
    result = invoke("run", "predict", "--model", model_zip, "--json")
    assert result.exit_code == 2


def test_predict_model_not_found(invoke):
    result = invoke("run", "predict", "--model", "nope.zip", "--fh", "1", "--json")
    assert result.exit_code == 4


def test_fit_predict(invoke, airline_csv):
    result = invoke(
        "run",
        "fit-predict",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--fh",
        "1:4",
        "--json",
    )
    payload = json.loads(result.stdout)
    assert len(payload["data"]) == 4


def test_classifier_workflow(invoke, unit_test_ts, tmp_path):
    model = tmp_path / "clf.zip"
    fit_result = invoke(
        "run",
        "fit",
        "DummyClassifier()",
        "--data",
        unit_test_ts,
        "--model-out",
        model,
        "--json",
    )
    assert fit_result.exit_code == 0, fit_result.output
    assert json.loads(fit_result.stdout)["scitype"] == "classifier"

    pred_result = invoke(
        "run", "predict", "--model", model, "--data", unit_test_ts, "--json"
    )
    payload = json.loads(pred_result.stdout)
    assert len(payload["data"]) == 42


def test_missing_dependency_exit_code(invoke, airline_csv):
    result = invoke("run", "fit", "AutoARIMA()", "--data", airline_csv, "--json")
    assert result.exit_code == 3


def test_evaluate_default_cv(invoke, airline_csv):
    result = invoke(
        "run",
        "evaluate",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--fh",
        "1:12",
        "--initial-window",
        "72",
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["folds"]
    agg = payload["aggregate"]["test_MeanAbsolutePercentageError"]
    assert 0 < agg["mean"] < 1


def test_evaluate_cv_spec_and_metric(invoke, airline_csv, tmp_path):
    out = tmp_path / "folds.csv"
    result = invoke(
        "run",
        "evaluate",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--cv",
        "ExpandingWindowSplitter(initial_window=72, step_length=12, "
        "fh=[1,2,3,4,5,6,7,8,9,10,11,12])",
        "--metric",
        "MeanAbsolutePercentageError",
        "--metric",
        "MeanAbsoluteError",
        "--output",
        out,
        "--json",
    )
    payload = json.loads(result.stdout)
    assert len(payload["folds"]) == 6
    assert "test_MeanAbsoluteError" in payload["aggregate"]
    assert out.exists()
