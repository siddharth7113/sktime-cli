"""``sktime-cli catalogues``: browsing sktime's benchmark catalogues."""

import json


def test_list_is_registry_backed(invoke):
    rows = json.loads(invoke("catalogues", "list", "--json").stdout)
    assert len(rows) > 0
    names = {row["name"] for row in rows}
    assert "DummyForecastingCatalogue" in names


def test_list_filters_by_name(invoke):
    rows = json.loads(invoke("catalogues", "list", "-n", "M4", "--json").stdout)
    assert rows
    assert all("m4" in row["name"].lower() for row in rows)


def test_get_returns_reusable_specs(invoke):
    payload = json.loads(
        invoke("catalogues", "get", "DummyForecastingCatalogue", "--json").stdout
    )
    assert payload["name"] == "DummyForecastingCatalogue"
    assert "forecaster" in payload["categories"]
    assert any("NaiveForecaster" in entry for entry in payload["entries"])


def test_get_filters_by_category(invoke):
    payload = json.loads(
        invoke(
            "catalogues",
            "get",
            "DummyForecastingCatalogue",
            "--type",
            "metric",
            "--json",
        ).stdout
    )
    assert payload["entries"]
    assert all("Error" in entry for entry in payload["entries"])


def test_get_rejects_an_unknown_category(invoke):
    result = invoke(
        "catalogues", "get", "DummyForecastingCatalogue", "--type", "nope", "--json"
    )
    assert result.exit_code == 2
    assert "available categories" in json.loads(result.stderr)["error"]["hint"]


def test_get_rejects_an_unknown_catalogue(invoke):
    result = invoke("catalogues", "get", "NoSuchCatalogue", "--json")
    assert result.exit_code == 4
    assert "catalogues list" in json.loads(result.stderr)["error"]["hint"]
