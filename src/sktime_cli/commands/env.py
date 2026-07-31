"""Environment commands: version, env, doctor, cache info/clear."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import time

import typer

from sktime_cli._cache import cli_home
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._output import OutputFormat, emit_record, emit_table, resolve_format


def _optional_deps() -> list[str]:
    """List optional packages worth reporting on, derived from metadata.

    Sources: sktime-cli's own extras (declared in pyproject.toml, read back
    via importlib.metadata) and sktime's canonical soft-dependency list
    (``DEFAULT_DEPS_TO_SHOW``), never a hand-maintained copy.
    """
    import re
    from importlib.metadata import PackageNotFoundError, requires

    deps: list[str] = []
    try:
        for requirement in requires("sktime-cli") or []:
            if "extra ==" in requirement:
                name = re.split(r"[<>=!;\s\[]", requirement.strip(), 1)[0]
                if name and name not in deps:
                    deps.append(name)
    except PackageNotFoundError:
        pass
    try:
        from sktime.utils._maint._show_versions import DEFAULT_DEPS_TO_SHOW

        core = {"pip", "sktime", "scikit-learn", "scikit-base"}
        for name in DEFAULT_DEPS_TO_SHOW:
            if name not in deps and name not in core:
                deps.append(name)
    except ImportError:
        pass
    return deps


@handle_errors
def version(
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Show sktime-cli, sktime, and python versions."""
    import sktime

    import sktime_cli

    fmt = resolve_format(format_, json_)
    record = {
        "sktime_cli": sktime_cli.__version__,
        "sktime": sktime.__version__,
        "python": platform.python_version(),
    }
    emit_record(record, fmt, quiet_value=sktime_cli.__version__)


@handle_errors
def env_info(
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Report system info and versions of sktime's dependencies."""
    from sktime.utils._maint._show_versions import _get_deps_info, _get_sys_info

    fmt = resolve_format(format_, json_)
    record = {
        "system": _get_sys_info(),
        "dependencies": _get_deps_info(),
        "cli_home": str(cli_home()),
    }
    emit_record(record, fmt)


@handle_errors
def doctor(
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Check that sktime-cli is healthy: imports, cache dir, optional deps."""
    fmt = resolve_format(format_, json_)
    checks: list[dict] = []

    start = time.perf_counter()
    try:
        import sktime

        elapsed = time.perf_counter() - start
        checks.append(
            {
                "check": "sktime import",
                "status": "ok",
                "detail": f"version {sktime.__version__}, {elapsed:.2f}s",
            }
        )
        failed = False
    except Exception as err:  # noqa: BLE001 - reported, not raised
        checks.append({"check": "sktime import", "status": "fail", "detail": str(err)})
        failed = True

    home = cli_home()
    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        checks.append({"check": "cache dir", "status": "ok", "detail": str(home)})
    except OSError as err:
        checks.append(
            {"check": "cache dir", "status": "warn", "detail": f"{home}: {err}"}
        )

    registry_dir = home / "registry"
    cached = (
        sorted(registry_dir.glob("registry-*.json")) if registry_dir.exists() else []
    )
    checks.append(
        {
            "check": "registry cache",
            "status": "ok" if cached else "warn",
            "detail": cached[-1].name
            if cached
            else "not built yet (first registry command builds it)",
        }
    )

    for dep in _optional_deps():
        present = importlib.util.find_spec(dep) is not None
        checks.append(
            {
                "check": f"optional: {dep}",
                "status": "ok" if present else "warn",
                "detail": "installed" if present else f"uv pip install {dep}",
            }
        )

    emit_table(checks, fmt, columns=["check", "status", "detail"], quiet_key=None)
    if failed:
        raise typer.Exit(1)


cache_app = typer.Typer(no_args_is_help=True, help="Manage the sktime-cli cache dir.")


def _dir_size(path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


@cache_app.command("info")
@handle_errors
def cache_info(
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Show cache location and per-directory sizes."""
    fmt = resolve_format(format_, json_)
    home = cli_home()
    record: dict = {"home": str(home), "exists": home.exists()}
    if home.exists():
        for sub in ("registry", "downloads", "models"):
            path = home / sub
            if path.exists():
                files = [f for f in path.rglob("*") if f.is_file()]
                record[sub] = {
                    "files": len(files),
                    "bytes": sum(f.stat().st_size for f in files),
                }
    emit_record(record, fmt, quiet_value=str(home))


@cache_app.command("clear")
@handle_errors
def cache_clear(
    all_: bool = typer.Option(
        False, "--all", help="Also delete saved models under the cache dir."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Delete cached registry data and downloads (models only with --all)."""
    fmt = resolve_format(format_, json_)
    home = cli_home()
    targets = ["registry", "downloads"] + (["models"] if all_ else [])
    removed = []
    for sub in targets:
        path = home / sub
        if path.exists():
            shutil.rmtree(path)
            removed.append(sub)
    emit_record(
        {"home": str(home), "removed": removed},
        fmt,
        quiet_value=" ".join(removed),
    )
