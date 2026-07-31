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


def test_inspect(invoke, model_zip):
    payload = json.loads(invoke("model", "inspect", model_zip, "--json").stdout)
    assert payload["class"] == "NaiveForecaster"
    assert payload["is_fitted"] is True
    assert payload["params"]["sp"] == 12
    assert payload["cutoff"] == "1960-12"


def test_inspect_spec_roundtrip(invoke, model_zip, airline_csv, tmp_path):
    spec = invoke("model", "inspect", model_zip, "--spec").stdout.strip()
    assert spec == "NaiveForecaster(sp=12)"
    refit = invoke(
        "run",
        "fit",
        spec,
        "--data",
        airline_csv,
        "--model-out",
        tmp_path / "refit.zip",
        "--json",
    )
    assert json.loads(refit.stdout)["estimator"] == spec


def test_inspect_fitted_params(invoke, model_zip):
    payload = json.loads(
        invoke("model", "inspect", model_zip, "--fitted", "--json").stdout
    )
    assert "fitted_params" in payload
