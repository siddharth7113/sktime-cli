"""The registry-drift guard: every sktime scitype must be classified."""

import pytest

from sktime_cli._errors import CliError
from sktime_cli._scitypes import SUPPORTED, UNSUPPORTED, handler_for


def _declared_scitypes():
    from sktime.registry import BASE_CLASS_SCITYPE_LIST

    return set(BASE_CLASS_SCITYPE_LIST)


def _observed_scitypes():
    """Every object_type tag actually carried by a registry object."""
    from sktime_cli._cache import get_registry

    return {st for record in get_registry() for st in record["scitypes"]}


def test_supported_and_unsupported_are_disjoint():
    assert not set(SUPPORTED) & set(UNSUPPORTED)


def test_every_declared_scitype_is_classified():
    """A scitype added to sktime must be classified here, not silently ignored."""
    unclassified = _declared_scitypes() - set(SUPPORTED) - set(UNSUPPORTED)
    assert not unclassified, (
        f"unclassified sktime scitypes: {sorted(unclassified)}; "
        "add them to SUPPORTED or UNSUPPORTED in _scitypes.py"
    )


def test_every_observed_scitype_is_classified():
    """Catches scitypes carried by objects but missing from the declared list."""
    unclassified = _observed_scitypes() - set(SUPPORTED) - set(UNSUPPORTED)
    assert not unclassified, (
        f"unclassified object_type tags in the registry: {sorted(unclassified)}; "
        "add them to SUPPORTED or UNSUPPORTED in _scitypes.py"
    )


def test_classification_does_not_drift_from_sktime():
    """No stale entries: everything we classify must still exist upstream."""
    known = _declared_scitypes() | _observed_scitypes()
    stale = (set(SUPPORTED) | set(UNSUPPORTED)) - known
    assert not stale, f"scitypes classified but no longer in sktime: {sorted(stale)}"


@pytest.mark.parametrize("scitype", sorted(SUPPORTED))
def test_supported_scitypes_resolve_to_a_handler(scitype):
    assert handler_for(scitype) == SUPPORTED[scitype]


@pytest.mark.parametrize("scitype", sorted(UNSUPPORTED))
def test_unsupported_scitypes_raise_with_a_hint(scitype):
    with pytest.raises(CliError) as excinfo:
        handler_for(scitype)
    assert excinfo.value.code == "usage"
    assert excinfo.value.hint, f"{scitype} needs an actionable hint"


def test_unknown_scitype_reports_a_report_url():
    with pytest.raises(CliError) as excinfo:
        handler_for("teleporter")
    assert "issues" in excinfo.value.hint
