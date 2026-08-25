"""Errors found in the 0.0.2 user-testing pass, kept fixed."""

import json

import pytest


def test_missing_dependency_names_only_what_is_missing(invoke, airline_csv):
    """AutoETS declares statsmodels and joblib; joblib is installed here."""
    result = invoke("run", "fit", "AutoETS()", "--data", airline_csv, "--json")
    if result.exit_code == 0:
        pytest.skip("statsmodels is installed in this environment")
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "missing_dependency"
    from skbase.utils.dependencies import _check_soft_dependencies

    for package in error["message"].split(":")[-1].split(","):
        package = package.strip()
        assert not _check_soft_dependencies(package, severity="none"), (
            f"{package} is installed but was reported as missing"
        )


def test_detector_without_scores_fails_as_usage(invoke, airline_csv):
    """A missing detector method is a CLI error, not a leaked NotImplementedError."""
    result = invoke(
        "run",
        "detect",
        "HampelDetector()",
        "--data",
        airline_csv,
        "--kind",
        "scores",
        "--json",
    )
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "usage"
    assert "cannot report scores" in error["message"]
    assert "--kind" in error["hint"]


def test_invalid_kind_is_still_rejected(invoke, airline_csv):
    result = invoke(
        "run",
        "detect",
        "HampelDetector()",
        "--data",
        airline_csv,
        "--kind",
        "bogus",
        "--json",
    )
    assert result.exit_code == 2
    assert "points|segments|scores" in json.loads(result.stderr)["error"]["message"]


def test_bad_nested_set_key_is_usage_not_keyerror(invoke, airline_csv, tmp_path):
    """Nested keys raise KeyError from the composite; it must not escape as exit 1."""
    result = invoke(
        "run",
        "fit",
        "Detrender() * NaiveForecaster()",
        "--data",
        airline_csv,
        "--set",
        "forecaster__sp=4",
        "--model-out",
        tmp_path / "m.zip",
        "--json",
    )
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "usage"
    assert "NaiveForecaster__sp" in error["hint"]


def test_tag_that_no_object_of_that_scitype_carries_is_an_error(invoke):
    """An empty result must not be the answer to an impossible filter."""
    result = invoke(
        "registry", "search", "forecaster", "-t", "scitype:y=univariate", "--json"
    )
    assert result.exit_code == 4
    error = json.loads(result.stderr)["error"]
    assert "scitype:y" in error["message"]
    assert "forecaster" in error["message"]


def test_misspelled_tag_suggests_the_real_one(invoke):
    result = invoke(
        "registry",
        "search",
        "forecaster",
        "-t",
        "capability:missing_value=true",
        "--json",
    )
    assert result.exit_code == 4
    assert "capability:missing_values" in json.loads(result.stderr)["error"]["hint"]


def test_valid_tag_filter_still_works(invoke):
    result = invoke(
        "registry",
        "search",
        "forecaster",
        "-t",
        "capability:missing_values=true",
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) > 0


def test_unknown_task_is_rejected_like_unknown_source(invoke):
    result = invoke("datasets", "list", "--task", "bogus", "--json")
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "usage"
    assert "forecaster" in error["hint"]


def test_known_task_still_lists(invoke):
    result = invoke("datasets", "list", "--task", "classifier", "--json")
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) > 0


def test_agent_format_emits_a_header_for_an_empty_result(invoke):
    """A script that skips the header must not eat the first row when empty."""
    result = invoke("registry", "search", "-n", "zzzznosuchthing", "--format", "agent")
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0].strip() != ""


def test_var_reports_the_variable_name(invoke, fitted_naive):
    """--var used to label the column 0 while --interval used the series name."""
    result = invoke(
        "run", "predict", "--model", fitted_naive, "--fh", "1", "--var", "--json"
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["columns"] == ["variable", "value"]
    assert payload["data"][0][0] == "Number of airline passengers"
