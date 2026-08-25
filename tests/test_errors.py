"""Missing-dependency reporting, including sktime's nameless import errors."""

import os

import pytest

from sktime_cli._errors import (
    CliError,
    from_module_not_found,
    missing_dependency,
    packages_from_error,
)

# the shape skbase's _check_soft_dependencies raises: a message, and name=None
SKBASE_SINGLE = (
    "This functionality requires package 'requests' to be present in the python "
    "environment, but 'requests' was not found. To install the requirement "
    "'requests', please run: `pip install requests` "
)
SKBASE_MULTI = (
    "Foo requires package 'scipy<1.7.0' or 'numpy' to be present in the python "
    "environment, but 'scipy<1.7.0' or 'numpy' was not found. To install the "
    "requirement 'scipy<1.7.0' or 'numpy', please run: `pip install scipy<1.7.0` "
    "or `pip install numpy` "
)


def test_python_import_error_uses_its_name():
    err = ModuleNotFoundError("No module named 'foo'", name="foo")
    assert packages_from_error(err) == ["foo"]


def test_sktime_soft_dependency_error_is_read_from_the_message():
    """The reported bug: skbase raises with name=None, so err.name is useless."""
    err = ModuleNotFoundError(SKBASE_SINGLE)
    assert err.name is None
    assert packages_from_error(err) == ["requests"]


def test_multiple_requirements_are_all_reported():
    assert packages_from_error(ModuleNotFoundError(SKBASE_MULTI)) == [
        "scipy<1.7.0",
        "numpy",
    ]


def test_requires_clause_is_used_when_there_is_no_install_line():
    err = ModuleNotFoundError("Foo requires package 'rdata' to be present, sorry.")
    assert packages_from_error(err) == ["rdata"]


def test_unparseable_error_yields_no_packages():
    assert packages_from_error(ModuleNotFoundError("something went wrong")) == []


def test_from_module_not_found_builds_an_actionable_hint():
    error = from_module_not_found(ModuleNotFoundError(SKBASE_SINGLE), "datasets load")
    assert error.code == "missing_dependency"
    assert error.exit_code == 3
    assert "requests" in error.message
    assert error.hint == "uv pip install requests"
    assert "None" not in error.message
    assert "None" not in error.hint


def test_version_constrained_packages_are_quoted_for_the_shell():
    error = from_module_not_found(ModuleNotFoundError(SKBASE_MULTI))
    assert error.hint == 'uv pip install "scipy<1.7.0" numpy'


def test_unparseable_error_still_produces_a_usable_error():
    error = from_module_not_found(ModuleNotFoundError("mystery"), "run fit")
    assert error.code == "missing_dependency"
    assert "None" not in error.message
    assert error.detail == "mystery"


@pytest.mark.parametrize("packages", [[], [None], ["None"], ""])
def test_missing_dependency_never_prints_none(packages):
    error = missing_dependency("thing", packages)
    assert isinstance(error, CliError)
    assert "None" not in error.message
    assert "None" not in (error.hint or "")


def test_load_of_a_dataset_with_uninstalled_deps_names_the_package(invoke):
    """End-to-end: `datasets load fpp3:...` reported `install None` before 0.0.2."""
    result = invoke("datasets", "load", "fpp3:ansett", "--json")
    if result.exit_code == 0:
        pytest.skip("fpp3 dependencies are installed in this environment")
    import json

    error = json.loads(result.stderr)["error"]
    assert error["code"] == "missing_dependency"
    assert "None" not in error["message"]
    assert "None" not in error["hint"]


def test_sktime_frames_are_attributed_to_sktime():
    """A real sktime frame is sktime's, whatever directory it is installed under.

    Attribution used to look for the substring `"sktime"` in a frame's path
    while excluding `"sktime_cli"`. Installing the CLI under a directory named
    `sktime_cli` puts every genuine sktime frame under that name too, so real
    sktime failures were reported as internal CLI bugs. CI never saw it,
    because GitHub checks the repository out to `sktime-cli`, with a hyphen.
    """
    from sktime_cli._guard import _in_sktime, _sktime_root

    root = _sktime_root()
    assert root is not None, "sktime must be importable for this test"
    assert _in_sktime(os.path.join(root, "forecasting", "base.py"))
    assert not _in_sktime(os.path.join(os.path.dirname(root), "pandas", "core.py"))


def test_a_directory_named_after_the_cli_does_not_hide_sktime(monkeypatch):
    """The regression itself: sktime under a `sktime_cli` parent still counts."""
    import sktime_cli._guard as guard

    root = os.path.normcase(
        os.path.join(os.sep, "home", "u", "sktime_cli", ".venv", "lib", "sktime")
    )
    monkeypatch.setattr(guard, "_sktime_root", lambda: root)
    assert guard._in_sktime(os.path.join(root, "forecasting", "base.py"))


def test_cli_frames_are_not_attributed_to_sktime():
    """The CLI's own package is never mistaken for sktime, however it is named."""
    import sktime_cli
    from sktime_cli._guard import _in_sktime

    cli_root = os.path.dirname(os.path.abspath(sktime_cli.__file__))
    assert not _in_sktime(os.path.join(cli_root, "_guard.py"))


def test_sibling_directories_are_not_inside_sktime(monkeypatch):
    """A path that merely starts with sktime's root is outside it."""
    import sktime_cli._guard as guard

    root = os.path.normcase(os.path.join(os.sep, "env", "sktime"))
    monkeypatch.setattr(guard, "_sktime_root", lambda: root)
    assert not guard._in_sktime(os.path.join(os.sep, "env", "sktime_extras", "x.py"))


# check_estimator's message offers two ways to get pytest and restates the
# first, so a naive scan reported it as three requirements.
SKBASE_ALTERNATIVES_REPEATED = (
    "check_estimator is a testing utility for developers, and requires pytest to "
    "be present in the python environment, but pytest was not found. Please run: "
    "`pip install pytest` to install the pytest package. To install sktime with "
    "all developer dependencies, run: `pip install sktime[dev]`To install the "
    "requirement 'pytest', please run: `pip install pytest`"
)


def test_a_restated_requirement_is_reported_once():
    """`check` used to hint `uv pip install pytest sktime pytest`."""
    assert packages_from_error(ModuleNotFoundError(SKBASE_ALTERNATIVES_REPEATED)) == [
        "pytest",
        "sktime[dev]",
    ]


def test_distinct_alternatives_are_all_kept():
    """Deduplication must not collapse genuinely different requirements."""
    assert packages_from_error(ModuleNotFoundError(SKBASE_MULTI)) == [
        "scipy<1.7.0",
        "numpy",
    ]


def test_extras_are_quoted_for_the_shell():
    """Unquoted, sktime[dev] is a glob pattern and the install command fails."""
    error = from_module_not_found(ModuleNotFoundError(SKBASE_ALTERNATIVES_REPEATED))
    assert error.hint == 'uv pip install pytest "sktime[dev]"'
