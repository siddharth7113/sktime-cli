"""``run transform`` and ``run detect``: the two scitype families new in 0.0.2."""

import json

# --------------------------------------------------------------------------
# transform


def test_fit_transform_a_series(invoke, airline_csv, tmp_path):
    out = tmp_path / "detrended.csv"
    result = invoke(
        "run", "transform", "Detrender()", "--data", airline_csv, "-o", out, "--json"
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["n"] == 144
    assert out.exists()


def test_transform_persists_and_reuses_a_fitted_transformer(
    invoke, airline_csv, tmp_path
):
    model = tmp_path / "detrender.zip"
    out = tmp_path / "t.csv"
    fitted = invoke(
        "run",
        "transform",
        "Detrender()",
        "--data",
        airline_csv,
        "--model-out",
        model,
        "-o",
        out,
        "--json",
    )
    assert fitted.exit_code == 0, fitted.output
    assert json.loads(fitted.stdout)["model"] == str(model)
    assert model.exists()

    reused = invoke(
        "run", "transform", "--model", model, "--data", airline_csv, "--json"
    )
    assert reused.exit_code == 0, reused.output
    assert len(json.loads(reused.stdout)["data"]) == 144


def test_transform_round_trips_through_inverse(invoke, airline_csv, tmp_path):
    model = tmp_path / "inv.zip"
    invoke(
        "run",
        "transform",
        "Detrender()",
        "--data",
        airline_csv,
        "--model-out",
        model,
        "--json",
    )
    result = invoke(
        "run",
        "transform",
        "--model",
        model,
        "--data",
        airline_csv,
        "--inverse",
        "--json",
    )
    assert result.exit_code == 0, result.output


def test_inverse_is_gated_on_the_capability_tag(invoke, airline_csv):
    result = invoke(
        "run",
        "transform",
        "SummaryTransformer()",
        "--data",
        airline_csv,
        "--inverse",
        "--json",
    )
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert "inverse_transform" in error["message"]
    assert "registry search" in error["hint"]


def test_transform_rejects_a_non_transformer(invoke, airline_csv):
    result = invoke(
        "run", "transform", "NaiveForecaster()", "--data", airline_csv, "--json"
    )
    assert result.exit_code == 2
    assert "forecaster" in json.loads(result.stderr)["error"]["message"]


def test_transform_needs_exactly_one_source(invoke, airline_csv, tmp_path):
    both = invoke(
        "run",
        "transform",
        "Detrender()",
        "--data",
        airline_csv,
        "--model",
        tmp_path / "x.zip",
        "--json",
    )
    assert both.exit_code == 2
    neither = invoke("run", "transform", "--data", airline_csv, "--json")
    assert neither.exit_code == 2


def test_reconcilers_are_transformers(invoke, hierarchical_csv):
    """Reconcilers subclass BaseTransformer, so run transform covers them."""
    result = invoke(
        "run",
        "transform",
        "BottomUpReconciler()",
        "--data",
        hierarchical_csv,
        "--long",
        "--id-col",
        "region,store",
        "--time-col",
        "time",
        "--json",
    )
    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------
# detect


def test_detect_change_points(invoke, airline_csv):
    result = invoke(
        "run",
        "detect",
        "DummyRegularChangePoints(step_size=24)",
        "--data",
        airline_csv,
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)["data"]) > 0


def test_detect_reports_the_resolved_kind(invoke, airline_csv, tmp_path):
    out = tmp_path / "cp.csv"
    result = invoke(
        "run",
        "detect",
        "DummyRegularChangePoints(step_size=24)",
        "--data",
        airline_csv,
        "-o",
        out,
        "--json",
    )
    assert json.loads(result.stdout)["kind"] == "points"


def test_detect_segments(invoke, airline_csv, tmp_path):
    out = tmp_path / "seg.csv"
    result = invoke(
        "run",
        "detect",
        "GreedyGaussianSegmentation(k_max=3)",
        "--data",
        airline_csv,
        "--kind",
        "segments",
        "-o",
        out,
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["kind"] == "segments"


def test_detect_rejects_an_unknown_kind(invoke, airline_csv):
    result = invoke(
        "run",
        "detect",
        "DummyRegularChangePoints()",
        "--data",
        airline_csv,
        "--kind",
        "bogus",
        "--json",
    )
    assert result.exit_code == 2
    assert "points|segments|scores" in json.loads(result.stderr)["error"]["message"]


def test_detect_rejects_a_non_detector(invoke, airline_csv):
    result = invoke(
        "run", "detect", "NaiveForecaster()", "--data", airline_csv, "--json"
    )
    assert result.exit_code == 2
    assert "detector" in json.loads(result.stderr)["error"]["message"]


def test_detector_persists_and_reloads(invoke, airline_csv, tmp_path):
    model = tmp_path / "cp.zip"
    out = tmp_path / "cp.csv"
    fitted = invoke(
        "run",
        "detect",
        "DummyRegularChangePoints(step_size=24)",
        "--data",
        airline_csv,
        "--model-out",
        model,
        "-o",
        out,
        "--json",
    )
    assert json.loads(fitted.stdout)["model"] == str(model)
    reused = invoke("run", "detect", "--model", model, "--data", airline_csv, "--json")
    assert reused.exit_code == 0, reused.output


# --------------------------------------------------------------------------
# scitype gating


def test_run_rejects_an_out_of_scope_scitype(invoke, airline_csv, tmp_path):
    """Unsupported scitypes get the hint from _scitypes.UNSUPPORTED."""
    result = invoke(
        "run",
        "fit",
        "ExpandingWindowSplitter(fh=1)",
        "--data",
        airline_csv,
        "--model-out",
        tmp_path / "s.zip",
        "--json",
    )
    assert result.exit_code == 2
    error = json.loads(result.stderr)["error"]
    assert "splitter" in error["message"]
    assert "data split" in error["hint"]


def test_model_path_goes_to_stderr_when_streaming(invoke, airline_csv, tmp_path):
    """Without --output stdout is the data, so the model path must not pollute it."""
    model = tmp_path / "streamed.zip"
    result = invoke(
        "run",
        "transform",
        "Detrender()",
        "--data",
        airline_csv,
        "--model-out",
        model,
        "--json",
    )
    assert result.exit_code == 0, result.output
    json.loads(result.stdout)  # stdout stays a single parseable document
    assert str(model) in result.stderr
    assert model.exists()
