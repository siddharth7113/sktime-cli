import json


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
