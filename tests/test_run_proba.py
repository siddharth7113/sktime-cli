"""Probabilistic forecasting: the long-form schema and the capability gate."""

import json

import pytest


def _rows(result):
    payload = json.loads(result.stdout)
    return payload["columns"], payload["data"]


def test_interval_emits_long_form(invoke, fitted_naive):
    result = invoke(
        "run",
        "predict",
        "--model",
        fitted_naive,
        "--fh",
        "1:3",
        "--interval",
        "0.8,0.95",
        "--json",
    )
    assert result.exit_code == 0, result.output
    columns, data = _rows(result)
    assert columns == ["variable", "coverage", "bound", "value"]
    # 3 horizon steps x 2 coverages x 2 bounds
    assert len(data) == 12
    assert {row[2] for row in data} == {"lower", "upper"}
    assert {row[1] for row in data} == {0.8, 0.95}


def test_interval_column_count_is_independent_of_coverage_count(invoke, fitted_naive):
    one, two = (
        _rows(
            invoke(
                "run",
                "predict",
                "--model",
                fitted_naive,
                "--fh",
                "1:3",
                "--interval",
                levels,
                "--json",
            )
        )
        for levels in ("0.9", "0.5,0.8,0.95")
    )
    assert one[0] == two[0]
    assert len(two[1]) == 3 * len(one[1])


def test_quantiles_emit_long_form(invoke, fitted_naive):
    result = invoke(
        "run",
        "predict",
        "--model",
        fitted_naive,
        "--fh",
        "1:2",
        "--quantiles",
        "0.1,0.9",
        "--json",
    )
    columns, data = _rows(result)
    assert columns == ["variable", "quantile", "value"]
    assert len(data) == 4


def test_var_emits_long_form(invoke, fitted_naive):
    columns, _ = _rows(
        invoke(
            "run", "predict", "--model", fitted_naive, "--fh", "1", "--var", "--json"
        )
    )
    assert columns == ["variable", "value"]


def test_wide_keeps_sktime_native_columns(invoke, fitted_naive):
    columns, _ = _rows(
        invoke(
            "run",
            "predict",
            "--model",
            fitted_naive,
            "--fh",
            "1:2",
            "--interval",
            "0.8",
            "--wide",
            "--json",
        )
    )
    assert all("__" in str(col) for col in columns)
    assert any(str(col).endswith("__lower") for col in columns)


def test_residuals_need_the_training_series(invoke, fitted_naive):
    result = invoke("run", "predict", "--model", fitted_naive, "--residuals", "--json")
    assert result.exit_code == 2
    assert "--data" in json.loads(result.stderr)["error"]["message"]


def test_residuals_from_data(invoke, fitted_naive, airline_csv):
    result = invoke(
        "run",
        "predict",
        "--model",
        fitted_naive,
        "--data",
        airline_csv,
        "--residuals",
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)["data"]) == 144


@pytest.mark.parametrize("flags", [("--interval", "0.9"), ("--quantiles", "0.1")])
def test_capability_gate_names_the_tag(invoke, airline_csv, tmp_path, flags):
    """A forecaster without capability:pred_int fails at the CLI, not inside sktime."""
    model = tmp_path / "croston.zip"
    fit = invoke(
        "run", "fit", "Croston()", "--data", airline_csv, "--model-out", model, "--json"
    )
    assert fit.exit_code == 0, fit.output
    result = invoke("run", "predict", "--model", model, "--fh", "1", *flags, "--json")
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert "capability:pred_int" in error["detail"]
    assert "registry search" in error["hint"]


def test_probabilistic_flags_are_mutually_exclusive(invoke, fitted_naive):
    result = invoke(
        "run",
        "predict",
        "--model",
        fitted_naive,
        "--fh",
        "1",
        "--interval",
        "0.9",
        "--var",
        "--json",
    )
    assert result.exit_code == 2
    assert "mutually exclusive" in json.loads(result.stderr)["error"]["message"]


def test_invalid_level_list_is_a_usage_error(invoke, fitted_naive):
    result = invoke(
        "run",
        "predict",
        "--model",
        fitted_naive,
        "--fh",
        "1",
        "--interval",
        "wide",
        "--json",
    )
    assert result.exit_code == 2
    assert "0.8,0.95" in json.loads(result.stderr)["error"]["message"]
