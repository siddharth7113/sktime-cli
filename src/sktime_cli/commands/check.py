"""``sktime-cli check``: validate an object against sktime's API contract.

Wraps ``sktime.utils.estimator_checks.check_estimator``, the same suite sktime
runs against its own estimators. Third-party estimator authors can point it at
their class to see whether it satisfies the interface, and agents can use it to
confirm a crafted spec is a well-formed sktime object before running it.
"""

from __future__ import annotations

import typer

from sktime_cli._errors import CliError, from_module_not_found
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._models import estimator_scitype
from sktime_cli._output import OutputFormat, emit_record, emit_table, resolve_format
from sktime_cli._specs import build_estimator


def _split_csv(value: str | None) -> list[str] | None:
    """Split a comma-separated option value into a list.

    Parameters
    ----------
    value : str or None
        The raw option value.

    Returns
    -------
    list of str or None
        The parts, or ``None`` when the option was absent, which the check
        runner reads as "no restriction".
    """
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _rows(results: dict) -> list[dict]:
    """Turn ``check_estimator``'s result mapping into table rows.

    Parameters
    ----------
    results : dict
        Test fixture name to outcome, where a pass is the string ``PASSED``
        and a failure is the exception that was raised.

    Returns
    -------
    list of dict
        Rows with ``test``, ``status``, and ``detail``, sorted by test name so
        two runs can be diffed.
    """
    rows = []
    for fixture, outcome in sorted(results.items()):
        # check_estimator reports a pass as the string "PASSED" and a failure
        # as the exception that was raised
        passed = outcome == "PASSED"
        rows.append(
            {
                "test": fixture,
                "status": "pass" if passed else "fail",
                "detail": ""
                if passed
                else f"{type(outcome).__name__}: {outcome}"
                if isinstance(outcome, BaseException)
                else str(outcome),
            }
        )
    return rows


@handle_errors
def check(
    spec: str = typer.Argument(
        ..., help='Object spec, e.g. "NaiveForecaster(sp=12)" or a class name.'
    ),
    tests: str | None = typer.Option(
        None, "--tests", help="Comma-separated test names to run (default: all)."
    ),
    exclude: str | None = typer.Option(
        None, "--exclude", help="Comma-separated test names to skip."
    ),
    failed_only: bool = typer.Option(
        False, "--failed-only", help="Report only the checks that failed."
    ),
    set_: list[str] = typer.Option(
        [], "--set", help="Parameter override key=value (repeatable)."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Run sktime's estimator contract checks against an object spec."""
    fmt = resolve_format(format_, json_)
    try:
        from sktime.utils.estimator_checks import check_estimator
    except ImportError as err:  # pragma: no cover - depends on the sktime version
        raise CliError(
            "missing_dependency",
            "this sktime version has no check_estimator utility",
            detail=str(err),
        ) from err

    obj = build_estimator(spec, set_)
    try:
        results = check_estimator(
            obj,
            raise_exceptions=False,
            verbose=False,
            tests_to_run=_split_csv(tests),
            tests_to_exclude=_split_csv(exclude),
        )
    except ModuleNotFoundError as err:
        raise from_module_not_found(err, "the contract checks") from err

    rows = _rows(results)
    failed = [row for row in rows if row["status"] == "fail"]
    shown = failed if failed_only else rows

    if fmt == OutputFormat.json:
        emit_record(
            {
                "object": str(obj),
                "scitype": estimator_scitype(obj),
                "total": len(rows),
                "passed": len(rows) - len(failed),
                "failed": len(failed),
                "checks": shown,
            },
            fmt,
        )
    else:
        emit_table(shown, fmt, columns=["test", "status", "detail"], quiet_key="test")
        emit_record(
            {
                "total": len(rows),
                "passed": len(rows) - len(failed),
                "failed": len(failed),
            },
            fmt,
        )
    if failed:
        raise typer.Exit(1)
