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
