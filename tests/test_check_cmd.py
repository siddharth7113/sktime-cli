"""``sktime-cli check``: the API-contract command."""

import json


def test_check_reports_passing_tests(invoke):
    result = invoke(
        "check", "NaiveForecaster(sp=12)", "--tests", "test_constructor", "--json"
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scitype"] == "forecaster"
    assert payload["failed"] == 0
    assert payload["passed"] == payload["total"] > 0
    assert all(check["status"] == "pass" for check in payload["checks"])


def test_check_counts_add_up(invoke):
    payload = json.loads(
        invoke(
            "check",
            "NaiveForecaster()",
            "--tests",
            "test_constructor,test_get_params",
            "--json",
        ).stdout
    )
    assert payload["passed"] + payload["failed"] == payload["total"]


def test_check_excludes_tests(invoke):
    both = json.loads(
        invoke(
            "check",
            "NaiveForecaster()",
            "--tests",
            "test_constructor,test_get_params",
            "--json",
        ).stdout
    )["total"]
    one = json.loads(
        invoke(
            "check",
            "NaiveForecaster()",
            "--tests",
            "test_constructor,test_get_params",
            "--exclude",
            "test_get_params",
            "--json",
        ).stdout
    )["total"]
    assert one < both


def test_check_applies_set_overrides(invoke):
    payload = json.loads(
        invoke(
            "check",
            "NaiveForecaster()",
            "--set",
            "sp=4",
            "--tests",
            "test_constructor",
            "--json",
        ).stdout
    )
    assert payload["object"] == "NaiveForecaster(sp=4)"


def test_check_rejects_an_unknown_object(invoke):
    result = invoke("check", "NotAnEstimator()", "--json")
    assert result.exit_code == 5
    assert json.loads(result.stderr)["error"]["code"] == "spec_error"


def test_check_agent_format_lists_each_test(invoke):
    result = invoke(
        "check", "NaiveForecaster()", "--tests", "test_constructor", "--format", "agent"
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0].startswith("test\tstatus")
