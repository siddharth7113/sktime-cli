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
    assert payload["task"] == "forecaster"
    assert payload["shape"] == [144]


def test_describe_remote_no_download(invoke):
    payload = json.loads(
        invoke("datasets", "describe", "ucr:ArrowHead", "--json").stdout
    )
    assert payload["task"] == "classifier"
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


# --------------------------------------------------------------------------
# dataset objects (0.0.2): the catalogue comes from the registry, not a dict


def test_catalogue_is_metadata_driven():
    """Bare dataset ids are exactly the `name` tags sktime's objects declare."""
    from sktime.registry import all_estimators

    from sktime_cli import _datasets

    declared = {
        cls.get_class_tag("name", None)
        for _n, cls in all_estimators(
            filter_tags={
                "object_type": [
                    "dataset",
                    "dataset_forecasting",
                    "dataset_classification",
                    "dataset_regression",
                ]
            },
            return_names=True,
        )
    }
    declared.discard(None)
    assert set(_datasets.object_index()) == declared


def test_describe_reports_tags_without_loading(invoke):
    payload = json.loads(
        invoke("datasets", "describe", "airline", "--no-load", "--json").stdout
    )
    assert payload["source"] == "builtin"
    assert payload["frequency"] == "M"
    assert payload["n_timepoints"] == 144
    assert payload["is_univariate"] is True
    assert "shape" not in payload  # nothing was loaded


def test_describe_adds_loaded_shape_by_default(invoke):
    payload = json.loads(invoke("datasets", "describe", "airline", "--json").stdout)
    assert payload["n_timepoints"] == 144  # from tags
    assert payload["shape"] == [144]  # from the loaded series


def test_describe_reports_soft_dependencies(invoke):
    payload = json.loads(
        invoke("datasets", "describe", "macroeconomic", "--json").stdout
    )
    assert payload["installable"] is False
    assert payload["python_dependencies"] == ["statsmodels"]


def test_loader_only_datasets_still_resolve(invoke, tmp_path):
    """unit_test and covid_3month have no object; the loader path covers them."""
    result = invoke("datasets", "load", "unit_test", "--output-dir", tmp_path, "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["task"] == "classifier"


def test_unknown_name_suggests_the_metadata_spelling(invoke):
    """0.0.2 uses sktime's own spelling; a near miss says what it should be."""
    result = invoke("datasets", "describe", "hierarchical_sales", "--json")
    assert result.exit_code == 4
    error = json.loads(result.stderr)["error"]
    assert error["message"] == "unknown dataset: hierarchical_sales"
    assert "hierarchical_sales_toydata" in error["hint"]


def test_bare_name_falls_through_to_the_remote_namespace(invoke):
    """`gunpoint` is no longer a builtin id, but UCR publishes a GunPoint."""
    from sktime_cli import _datasets

    assert _datasets.resolve("gunpoint") == ("ucr", "GunPoint")
    assert _datasets.resolve("gun_point") == ("object", "gun_point")


def test_panel_dataset_writes_labels_alongside_non_ts_formats(invoke, tmp_path):
    result = invoke(
        "datasets",
        "load",
        "arrow_head",
        "--split",
        "train",
        "--file-format",
        "csv",
        "--output-dir",
        tmp_path,
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["labels"].endswith("_y.csv")
    assert len(payload["files"]) == 2


def test_split_that_does_not_exist_lists_the_parts(invoke, tmp_path):
    result = invoke(
        "datasets",
        "load",
        "airline",
        "--split",
        "train",
        "--output-dir",
        tmp_path,
        "--json",
    )
    assert result.exit_code == 2
    assert "available parts" in json.loads(result.stderr)["error"]["hint"]
