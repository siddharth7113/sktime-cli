import json
from pathlib import Path


def test_inspect_series(invoke, airline_csv):
    result = invoke("data", "inspect", airline_csv, "--json")
    payload = json.loads(result.stdout)
    assert payload["scitype"] == "Series"
    assert payload["mtype"] == "pd.Series"
    assert payload["metadata"]["is_univariate"] is True
    assert payload["index"]["dtype"] == "period[M]"


def test_inspect_panel_ts(invoke, unit_test_ts):
    payload = json.loads(invoke("data", "inspect", unit_test_ts, "--json").stdout)
    assert payload["scitype"] == "Panel"
    assert payload["labels"]["classes"] == ["1", "2"]


def test_split(invoke, airline_csv, tmp_path):
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    result = invoke(
        "data",
        "split",
        airline_csv,
        "--test-size",
        "12",
        "--train-out",
        train,
        "--test-out",
        test,
        "--json",
    )
    payload = json.loads(result.stdout)
    assert payload["n_train"] == 132
    assert payload["n_test"] == 12
    assert train.exists() and test.exists()


def test_split_needs_a_size(invoke, airline_csv):
    result = invoke("data", "split", airline_csv, "--json")
    assert result.exit_code == 2


def test_convert_to_json(invoke, airline_csv, tmp_path):
    out = tmp_path / "airline.json"
    result = invoke("data", "convert", airline_csv, "--output", out, "--json")
    assert result.exit_code == 0
    payload = json.loads(out.read_text())
    assert len(payload["data"]) == 144


# --------------------------------------------------------------------------
# cross-validation folds (0.0.2)


def test_split_cv_writes_a_fold_per_split(invoke, airline_csv, tmp_path):
    import shutil

    data = tmp_path / "airline.csv"
    shutil.copy(airline_csv, data)
    result = invoke(
        "data",
        "split",
        data,
        "--cv",
        "ExpandingWindowSplitter(initial_window=100, step_length=12, fh=[1,2,3])",
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["n_folds"] == len(payload["folds"]) > 1
    assert len(payload["files"]) == 2 * payload["n_folds"]
    for fold in payload["folds"]:
        assert Path(fold["train"]).exists()
        assert Path(fold["test"]).exists()
        assert fold["n_test"] == 3
    # expanding window: each fold trains on more data than the last
    sizes = [fold["n_train"] for fold in payload["folds"]]
    assert sizes == sorted(sizes) and sizes[0] < sizes[-1]


def test_split_cv_conflicts_with_sizing_options(invoke, airline_csv, tmp_path):
    import shutil

    data = tmp_path / "airline.csv"
    shutil.copy(airline_csv, data)
    result = invoke(
        "data",
        "split",
        data,
        "--cv",
        "ExpandingWindowSplitter(fh=1)",
        "--test-size",
        "12",
        "--json",
    )
    assert result.exit_code == 2
    assert "cannot be combined" in json.loads(result.stderr)["error"]["message"]


def test_split_cv_rejects_a_non_splitter(invoke, airline_csv, tmp_path):
    import shutil

    data = tmp_path / "airline.csv"
    shutil.copy(airline_csv, data)
    result = invoke("data", "split", data, "--cv", "NaiveForecaster()", "--json")
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert "needs a splitter" in error["message"]
    assert "registry search splitter" in error["hint"]


def test_split_with_no_sizing_option_is_a_usage_error(invoke, airline_csv, tmp_path):
    import shutil

    data = tmp_path / "airline.csv"
    shutil.copy(airline_csv, data)
    result = invoke("data", "split", data, "--json")
    assert result.exit_code == 2
    assert "--cv" in json.loads(result.stderr)["error"]["message"]
