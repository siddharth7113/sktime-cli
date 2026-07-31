import json


def test_list_builtin(invoke):
    result = invoke("datasets", "list", "--source", "builtin", "--json")
    rows = json.loads(result.stdout)
    assert any(row["name"] == "airline" for row in rows)


def test_list_all_sources(invoke):
    rows = json.loads(invoke("datasets", "list", "--json").stdout)
    sources = {row["source"] for row in rows}
    assert {"builtin", "ucr", "tsf", "fpp3"} <= sources


def test_describe_builtin(invoke):
    payload = json.loads(invoke("datasets", "describe", "airline", "--json").stdout)
    assert payload["task"] == "forecasting"
    assert payload["shape"] == [144]


def test_describe_remote_no_download(invoke):
    payload = json.loads(
        invoke("datasets", "describe", "ucr:ArrowHead", "--json").stdout
    )
    assert payload["task"] == "classification"
    assert "load" in payload["note"]


def test_load_airline(invoke, tmp_path):
    out = tmp_path / "airline.csv"
    result = invoke("datasets", "load", "airline", "--output", out, "--json")
    assert result.exit_code == 0
    manifest = json.loads(result.stdout)
    assert manifest["files"] == [str(out)]
    assert out.exists()


def test_load_classification_ts(invoke, tmp_path):
    out = tmp_path / "unit_test.ts"
    result = invoke("datasets", "load", "unit_test", "--output", out, "--json")
    manifest = json.loads(result.stdout)
    assert manifest["classes"] == ["1", "2"]
    assert out.exists()


def test_unknown_dataset_suggests(invoke):
    result = invoke("datasets", "load", "airlin", "--json")
    assert result.exit_code == 4
