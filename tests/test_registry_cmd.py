import json


def test_search_with_tag_filter(invoke):
    result = invoke(
        "registry",
        "search",
        "forecaster",
        "-t",
        "capability:missing_values=true",
        "--json",
    )
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert rows
    assert all("forecaster" in row["scitypes"] for row in rows)


def test_search_installable_only_is_subset(invoke):
    all_rows = json.loads(invoke("registry", "search", "forecaster", "--json").stdout)
    inst_rows = json.loads(
        invoke(
            "registry", "search", "forecaster", "--installable-only", "--json"
        ).stdout
    )
    assert 0 < len(inst_rows) < len(all_rows)
    assert all(row["installable"] for row in inst_rows)


def test_search_agent_format_is_tsv(invoke):
    result = invoke(
        "registry", "search", "forecaster", "--limit", "3", "--format", "agent"
    )
    lines = result.stdout.strip().splitlines()
    assert lines[0].split("\t")[0] == "name"
    assert len(lines) == 4
    assert "\x1b" not in result.stdout  # no ANSI codes


def test_search_unknown_scitype(invoke):
    result = invoke("registry", "search", "nonsense", "--json")
    assert result.exit_code == 4


def test_describe(invoke):
    result = invoke("registry", "describe", "NaiveForecaster", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["params"]["sp"]["default"] == "1"
    assert payload["installable"] is True
    assert payload["summary"]


def test_describe_not_found(invoke):
    result = invoke("registry", "describe", "NoSuchEstimator", "--json")
    assert result.exit_code == 4


def test_tags(invoke):
    rows = json.loads(invoke("registry", "tags", "forecaster", "--json").stdout)
    assert len(rows) > 20
    assert {"name", "scitype", "type", "description"} <= set(rows[0])


def test_types(invoke):
    rows = json.loads(invoke("registry", "types", "--json").stdout)
    assert len(rows) == 25
    forecaster = next(r for r in rows if r["scitype"] == "forecaster")
    assert forecaster["count"] > 100
