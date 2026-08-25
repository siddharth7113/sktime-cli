import json

import sktime_cli


def test_version_json(invoke):
    result = invoke("version", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {"sktime_cli", "sktime", "python"}
    assert payload["sktime_cli"] == sktime_cli.__version__


def test_version_eager_flag(invoke):
    result = invoke("--version")
    assert result.exit_code == 0
    assert sktime_cli.__version__ in result.stdout


def test_version_quiet(invoke):
    result = invoke("version", "--format", "quiet")
    assert result.stdout.strip() == sktime_cli.__version__


def test_unknown_command_is_usage_error(invoke):
    result = invoke("frobnicate")
    assert result.exit_code == 2


def test_json_format_conflict(invoke):
    result = invoke("version", "--json", "--format", "agent")
    assert result.exit_code == 2


def test_package_version_matches_pyproject():
    """The release workflow tags from pyproject; the two must not drift."""
    from pathlib import Path

    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert sktime_cli.__version__ == declared, (
        "the installed version differs from pyproject.toml; run `uv sync`"
    )
