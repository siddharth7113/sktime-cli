"""Input resolution: long-format panels, hierarchies, and role assignment."""

import json

import pytest

from sktime_cli import _input
from sktime_cli._errors import CliError
from sktime_cli._input import ReadOptions


def test_long_csv_reads_as_panel(long_panel_csv):
    inp = _input.load(
        str(long_panel_csv), ReadOptions(long=True, id_col="inst", time_col="time")
    )
    assert inp.kind == "panel"
    assert inp.obj.index.nlevels == 2
    assert list(inp.obj.columns) == ["value"]


def test_multiple_id_cols_read_as_hierarchical(hierarchical_csv):
    inp = _input.load(
        str(hierarchical_csv),
        ReadOptions(long=True, id_col="region,store", time_col="time"),
    )
    assert inp.kind == "hierarchical"
    assert inp.obj.index.nlevels == 3


def test_long_defaults_use_the_first_columns(long_panel_csv):
    """Without --id-col/--time-col the first two columns are id and time."""
    inp = _input.load(str(long_panel_csv), ReadOptions(long=True))
    assert inp.kind == "panel"
    assert inp.obj.index.names == ["inst", "time"]


def test_missing_long_column_names_the_available_ones(long_panel_csv):
    with pytest.raises(CliError) as excinfo:
        _input.load(str(long_panel_csv), ReadOptions(long=True, id_col="nope"))
    assert excinfo.value.code == "not_found"
    assert "inst" in excinfo.value.hint


def test_non_numeric_endogenous_is_a_cli_error(long_panel_csv):
    """The B1 regression: a long file read without --long must not reach sktime."""
    inp = _input.load(str(long_panel_csv))
    with pytest.raises(CliError) as excinfo:
        _input.as_endogenous(inp, str(long_panel_csv))
    assert excinfo.value.code == "data_error"
    assert "--long" in excinfo.value.hint
    assert "inst" in excinfo.value.message


def test_target_splits_endogenous_from_exogenous(tmp_path):
    import pandas as pd

    path = tmp_path / "wide.csv"
    pd.DataFrame({"time": range(10), "y": range(10), "x1": range(10, 20)}).to_csv(
        path, index=False
    )
    inp = _input.load(str(path), target="y")
    assert inp.obj.name == "y"
    assert list(inp.exog.columns) == ["x1"]


def test_dataset_id_resolves_without_a_file():
    inp = _input.load("airline")
    assert inp.kind == "series"
    assert len(inp.obj) == 144


# --------------------------------------------------------------------------
# end-to-end regressions for the two bugs the input layer fixes


def test_global_forecasting_from_a_long_file(invoke, long_panel_csv, tmp_path):
    """B2: a panel read from a file trains a global forecaster, as datasets do."""
    out = tmp_path / "global.csv"
    result = invoke(
        "run",
        "fit-predict",
        "NaiveForecaster()",
        "--data",
        long_panel_csv,
        "--long",
        "--id-col",
        "inst",
        "--time-col",
        "time",
        "--fh",
        "1:2",
        "-o",
        out,
        "--json",
    )
    assert result.exit_code == 0, result.output
    # one forecast per instance per horizon step
    assert json.loads(result.stdout)["n"] == 4


def test_forgetting_long_gives_an_actionable_error(invoke, long_panel_csv):
    """B1: the id column must not silently become part of y."""
    result = invoke(
        "run",
        "fit-predict",
        "NaiveForecaster()",
        "--data",
        long_panel_csv,
        "--fh",
        "1:2",
        "--json",
    )
    assert result.exit_code == 5
    payload = json.loads(result.stderr)["error"]
    assert payload["code"] == "data_error"
    assert "--long" in payload["hint"]


def test_fit_reports_the_input_kind_for_panels(invoke, long_panel_csv, tmp_path):
    result = invoke(
        "run",
        "fit",
        "NaiveForecaster()",
        "--data",
        long_panel_csv,
        "--long",
        "--id-col",
        "inst",
        "--time-col",
        "time",
        "--model-out",
        tmp_path / "g.zip",
        "--json",
    )
    assert json.loads(result.stdout)["input_kind"] == "panel"
