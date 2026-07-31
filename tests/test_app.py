import json


def test_version_json(invoke):
    result = invoke("version", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {"sktime_cli", "sktime", "python"}
    assert payload["sktime_cli"] == "0.0.1"


def test_version_eager_flag(invoke):
    result = invoke("--version")
    assert result.exit_code == 0
    assert "0.0.1" in result.stdout


def test_version_quiet(invoke):
    result = invoke("version", "--format", "quiet")
    assert result.stdout.strip() == "0.0.1"


def test_unknown_command_is_usage_error(invoke):
    result = invoke("frobnicate")
    assert result.exit_code == 2


def test_json_format_conflict(invoke):
    result = invoke("version", "--json", "--format", "agent")
    assert result.exit_code == 2
