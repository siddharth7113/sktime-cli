import json
import os
from pathlib import Path

from sktime_cli import _cache


def test_cli_home_env(cli_home):
    assert _cache.cli_home() == Path(os.environ["SKTIME_CLI_HOME"]) == cli_home


def test_cache_dir_flag_wins(cli_home, tmp_path):
    _cache.set_cache_dir(tmp_path)
    try:
        assert _cache.cli_home() == tmp_path
    finally:
        _cache.set_cache_dir(None)
    assert _cache.cli_home() == cli_home


def test_registry_cache_file_written(cli_home):
    records = _cache.get_registry()
    assert len(records) > 500
    files = list((cli_home / "registry").glob("registry-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["schema_version"] == _cache.REGISTRY_SCHEMA_VERSION


def test_corrupt_cache_is_rebuilt(cli_home):
    _cache.get_registry()
    cache_file = next((cli_home / "registry").glob("registry-*.json"))
    cache_file.write_text("{corrupt")
    records = _cache.get_registry()
    assert len(records) > 500
    assert json.loads(cache_file.read_text())["schema_version"] == 1


def test_lookup():
    record = _cache.lookup("NaiveForecaster")
    assert record is not None
    assert record["installable"] is True
    assert _cache.lookup("DefinitelyNotAThing") is None
