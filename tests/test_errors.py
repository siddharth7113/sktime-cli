"""Missing-dependency reporting, including sktime's nameless import errors."""

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
