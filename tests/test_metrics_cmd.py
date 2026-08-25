"""``sktime-cli metrics``: listing metric objects and scoring predictions."""

import json

import pytest


@pytest.fixture(scope="module")
def scored_pair(invoke, airline_csv, tmp_path_factory):
    """A train/test split plus a prediction over the test horizon."""
    workdir = tmp_path_factory.mktemp("score")
    import shutil

    data = workdir / "airline.csv"
    shutil.copy(airline_csv, data)

    split = invoke("data", "split", data, "--test-size", "12", "--json")
    assert split.exit_code == 0, split.output
    paths = json.loads(split.stdout)

    model = workdir / "m.zip"
    fit = invoke(
        "run",
        "fit",
        "NaiveForecaster(sp=12)",
        "--data",
        paths["train"],
        "--model-out",
        model,
        "--json",
    )
    assert fit.exit_code == 0, fit.output

    pred = workdir / "pred.csv"
    predicted = invoke(
        "run", "predict", "--model", model, "--fh", "1:12", "-o", pred, "--json"
    )
    assert predicted.exit_code == 0, predicted.output
    return {"train": paths["train"], "test": paths["test"], "pred": str(pred)}


def test_metrics_list_is_registry_backed(invoke):
    rows = json.loads(invoke("metrics", "list", "metric_forecasting", "--json").stdout)
    assert len(rows) > 10
    names = {row["name"] for row in rows}
    assert "MeanAbsolutePercentageError" in names
    assert all("metric_forecasting" in row["scitypes"] for row in rows)


def test_metrics_list_reports_direction(invoke):
    rows = json.loads(
        invoke("metrics", "list", "-n", "MeanAbsoluteError", "--json").stdout
    )
    assert rows[0]["lower_is_better"] is True


def test_metrics_list_rejects_a_non_metric_scitype(invoke):
    result = invoke("metrics", "list", "forecaster", "--json")
    assert result.exit_code == 2
    assert "metric_forecasting" in json.loads(result.stderr)["error"]["hint"]


def test_score_a_prediction(invoke, scored_pair):
    result = invoke(
        "metrics",
        "score",
        "--true",
        scored_pair["test"],
        "--pred",
        scored_pair["pred"],
        "--metric",
        "MeanAbsolutePercentageError",
        "--metric",
        "MeanAbsoluteError",
        "--json",
    )
    assert result.exit_code == 0, result.output
    scores = json.loads(result.stdout)
    assert set(scores) == {"MeanAbsolutePercentageError", "MeanAbsoluteError"}
    assert 0 < scores["MeanAbsolutePercentageError"] < 1


def test_score_defaults_to_mape(invoke, scored_pair):
    scores = json.loads(
        invoke(
            "metrics",
            "score",
            "--true",
            scored_pair["test"],
            "--pred",
            scored_pair["pred"],
            "--json",
        ).stdout
    )
    assert list(scores) == ["MeanAbsolutePercentageError"]


def test_metric_requiring_y_train_says_so(invoke, scored_pair):
    result = invoke(
        "metrics",
        "score",
        "--true",
        scored_pair["test"],
        "--pred",
        scored_pair["pred"],
        "--metric",
        "MeanAbsoluteScaledError",
        "--json",
    )
    assert result.exit_code == 2
    assert "--train" in json.loads(result.stderr)["error"]["hint"]


def test_metric_requiring_y_train_works_with_it(invoke, scored_pair):
    result = invoke(
        "metrics",
        "score",
        "--true",
        scored_pair["test"],
        "--pred",
        scored_pair["pred"],
        "--metric",
        "MeanAbsoluteScaledError",
        "--train",
        scored_pair["train"],
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["MeanAbsoluteScaledError"] > 0


def test_score_accepts_a_metric_spec(invoke, scored_pair):
    scores = json.loads(
        invoke(
            "metrics",
            "score",
            "--true",
            scored_pair["test"],
            "--pred",
            scored_pair["pred"],
            "--metric",
            "MeanAbsolutePercentageError(symmetric=True)",
            "--json",
        ).stdout
    )
    assert "MeanAbsolutePercentageError" in scores


def test_non_overlapping_indexes_are_a_data_error(invoke, scored_pair, tmp_path):
    import pandas as pd

    bogus = tmp_path / "other.csv"
    pd.DataFrame({"index": range(3), "value": [1.0, 2.0, 3.0]}).to_csv(
        bogus, index=False
    )
    result = invoke(
        "metrics", "score", "--true", scored_pair["test"], "--pred", bogus, "--json"
    )
    assert result.exit_code == 5
    error = json.loads(result.stderr)["error"]
    assert "different periods" in error["message"]
    assert "data split" in error["hint"]


def test_equal_length_but_different_periods_is_rejected(invoke, scored_pair, tmp_path):
    """Equal lengths are not equal periods; scoring them positionally is nonsense."""
    import pandas as pd

    truth = pd.read_csv(scored_pair["test"])
    shifted = tmp_path / "shifted.csv"
    truth.assign(**{truth.columns[0]: range(9000, 9000 + len(truth))}).to_csv(
        shifted, index=False
    )
    result = invoke(
        "metrics", "score", "--true", shifted, "--pred", scored_pair["pred"], "--json"
    )
    assert result.exit_code == 5
    assert "different periods" in json.loads(result.stderr)["error"]["message"]
