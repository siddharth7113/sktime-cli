"""Shared fixtures: isolated cache home, CliRunner, offline data files."""

import os

import pytest
from typer.testing import CliRunner

from sktime_cli.app import app


@pytest.fixture(scope="session", autouse=True)
def cli_home(tmp_path_factory):
    """Point SKTIME_CLI_HOME at a temp dir for the whole session."""
    home = tmp_path_factory.mktemp("skthome")
    old = os.environ.get("SKTIME_CLI_HOME")
    os.environ["SKTIME_CLI_HOME"] = str(home)
    yield home
    if old is None:
        os.environ.pop("SKTIME_CLI_HOME", None)
    else:
        os.environ["SKTIME_CLI_HOME"] = old


@pytest.fixture(scope="session")
def runner():
    return CliRunner()


@pytest.fixture(scope="session")
def invoke(runner):
    """Invoke the app; returns the click Result."""

    def _invoke(*args):
        return runner.invoke(app, [str(a) for a in args])

    return _invoke


@pytest.fixture(scope="session")
def airline_csv(tmp_path_factory):
    """Airline series written to CSV (offline builtin dataset)."""
    from sktime.datasets import load_airline

    from sktime_cli._io import write_any

    path = tmp_path_factory.mktemp("data") / "airline.csv"
    write_any(load_airline(), path)
    return path


@pytest.fixture(scope="session")
def unit_test_ts(tmp_path_factory):
    """UnitTest classification panel written to a .ts file (offline builtin)."""
    from sktime.datasets import load_unit_test

    from sktime_cli._io import write_any

    path = tmp_path_factory.mktemp("data") / "unit_test.ts"
    X, y = load_unit_test()
    write_any(X, path, "ts", y=y)
    return path


@pytest.fixture(scope="session")
def long_panel_csv(tmp_path_factory):
    """Two instances in long format: id, time, value (offline, generated)."""
    import numpy as np
    import pandas as pd

    rows = [
        {"inst": inst, "time": t, "value": float(np.sin(t / 3) + offset)}
        for inst, offset in (("a", 0.0), ("b", 5.0))
        for t in range(24)
    ]
    path = tmp_path_factory.mktemp("data") / "panel_long.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="session")
def hierarchical_csv(tmp_path_factory):
    """Two id levels in long format, for hierarchical input."""
    import pandas as pd

    rows = [
        {"region": region, "store": store, "time": t, "value": float(t + seed)}
        for region, store, seed in (
            ("north", "s1", 0),
            ("north", "s2", 10),
            ("south", "s1", 20),
        )
        for t in range(20)
    ]
    path = tmp_path_factory.mktemp("data") / "hier_long.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def fitted_naive(invoke, airline_csv, tmp_path_factory):
    """A fitted NaiveForecaster artifact, reusable across predict tests."""
    path = tmp_path_factory.mktemp("models") / "naive_shared.zip"
    result = invoke(
        "run",
        "fit",
        "NaiveForecaster(sp=12)",
        "--data",
        airline_csv,
        "--model-out",
        path,
        "--json",
    )
    assert result.exit_code == 0, result.output
    return path
