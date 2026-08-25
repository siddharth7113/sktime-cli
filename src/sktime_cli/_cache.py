"""Workspace/cache directory (``SKTIME_CLI_HOME``) and the registry disk cache.

Layout::

    $SKTIME_CLI_HOME/
    ├── registry/registry-<sktime>-py<X.Y>-<envhash8>.json
    ├── downloads/{ucr,tsf}/    # extract_path for sktime dataset fetchers
    └── models/                 # default --model-out target

The registry cache is the latency lever for agents: one full
``all_estimators`` crawl is serialized once, then every ``registry search`` /
spec lookup is a JSON load + filter instead of a package crawl.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

REGISTRY_SCHEMA_VERSION = 1

# root-level flags, set by the app callback
_cache_dir_override: Path | None = None
_no_cache: bool = False


def set_cache_dir(path: Path | None) -> None:
    """Record the ``--cache-dir`` root option."""
    global _cache_dir_override
    _cache_dir_override = path


def set_no_cache(flag: bool) -> None:
    """Record the ``--no-cache`` root option."""
    global _no_cache
    _no_cache = flag


def no_cache() -> bool:
    """Return True when ``--no-cache`` was passed."""
    return _no_cache


def cli_home() -> Path:
    """Resolve the workspace dir: --cache-dir > $SKTIME_CLI_HOME > XDG cache."""
    if _cache_dir_override is not None:
        return _cache_dir_override
    env = os.environ.get("SKTIME_CLI_HOME")
    if env:
        return Path(env)
    import platformdirs

    return Path(platformdirs.user_cache_dir("sktime-cli"))


def subdir(name: str) -> Path:
    """Return (and create) a subdirectory of the workspace."""
    path = cli_home() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env_hash() -> str:
    """Hash of the installed distributions; changes when any package changes."""
    from importlib.metadata import distributions

    entries = sorted(
        (dist.metadata["Name"] or "?", dist.version or "?") for dist in distributions()
    )
    digest = hashlib.sha256(json.dumps(entries).encode()).hexdigest()
    return digest[:8]


def _registry_cache_path() -> Path:
    import platform

    import sktime

    py = f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}"
    name = f"registry-{sktime.__version__}-py{py}-{_env_hash()}.json"
    return cli_home() / "registry" / name


def _jsonify_tag(value: Any) -> Any:
    """Coerce a tag value into something JSON-storable, else its repr."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, (list, tuple)):
            return [_jsonify_tag(v) for v in value]
        return repr(value)


def build_registry() -> list[dict]:
    """Crawl sktime's registry into a JSON-safe list of object records."""
    from sktime.registry import all_estimators
    from sktime.utils.dependencies import _check_estimator_deps

    records = []
    for name, cls in all_estimators(return_names=True):
        tags = {k: _jsonify_tag(v) for k, v in cls.get_class_tags().items()}
        scitypes = tags.get("object_type", "object")
        if not isinstance(scitypes, list):
            scitypes = [scitypes]
        deps = tags.get("python_dependencies") or []
        if isinstance(deps, str):
            deps = [deps]
        try:
            params = list(cls.get_param_names())
            defaults = {k: repr(v) for k, v in cls.get_param_defaults().items()}
        except Exception:  # noqa: S110 - introspection must never break the crawl
            params, defaults = [], {}
        records.append(
            {
                "name": name,
                "module": cls.__module__,
                "scitypes": scitypes,
                "tags": tags,
                "python_dependencies": deps,
                "installable": bool(_check_estimator_deps(cls, severity="none")),
                "params": params,
                "param_defaults": defaults,
            }
        )
    return records


def get_registry(force_rebuild: bool = False) -> list[dict]:
    """Return the registry records, from disk cache when possible."""
    path = _registry_cache_path()
    if not force_rebuild and not _no_cache and path.exists():
        try:
            payload = json.loads(path.read_text())
            if payload.get("schema_version") == REGISTRY_SCHEMA_VERSION:
                return payload["records"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # stale or corrupt cache: rebuild below
    records = build_registry()
    if not _no_cache:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {"schema_version": REGISTRY_SCHEMA_VERSION, "records": records}
                )
            )
        except OSError:
            pass  # cache dir not writable: still serve the live crawl
    return records


def lookup(name: str) -> dict | None:
    """Find a registry record by exact object name."""
    for record in get_registry():
        if record["name"] == name:
            return record
    return None


def import_object(record: dict):
    """Import and return the class a registry record points to."""
    import importlib

    from sktime_cli._errors import missing_dependency, packages_from_error

    try:
        module = importlib.import_module(record["module"])
        return getattr(module, record["name"])
    except ModuleNotFoundError as err:
        deps = record.get("python_dependencies") or packages_from_error(err)
        raise missing_dependency(record["name"], deps) from err
