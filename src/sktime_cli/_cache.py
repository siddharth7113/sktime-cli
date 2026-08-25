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

#: Version of the record layout written to the cache file. Bump this whenever
#: the shape of a record changes, so caches written by an older sktime-cli are
#: discarded and rebuilt rather than misread.
REGISTRY_SCHEMA_VERSION = 1

# root-level flags, set by the app callback
_cache_dir_override: Path | None = None
_no_cache: bool = False


def set_cache_dir(path: Path | None) -> None:
    """Record the ``--cache-dir`` root option for the rest of the process.

    Parameters
    ----------
    path : Path or None
        Workspace directory, or ``None`` to fall back to the environment and
        then the platform cache directory.
    """
    global _cache_dir_override
    _cache_dir_override = path


def set_no_cache(flag: bool) -> None:
    """Record the ``--no-cache`` root option for the rest of the process.

    Parameters
    ----------
    flag : bool
        When true, the registry is crawled live and the result is not written
        to disk.
    """
    global _no_cache
    _no_cache = flag


def no_cache() -> bool:
    """Report whether ``--no-cache`` was passed.

    Returns
    -------
    bool
        True when the disk cache should be bypassed.
    """
    return _no_cache


def cli_home() -> Path:
    """Resolve the workspace directory.

    Returns
    -------
    Path
        The first of: ``--cache-dir``, ``$SKTIME_CLI_HOME``, or the platform
        cache directory. The directory is not created here; see :func:`subdir`.
    """
    if _cache_dir_override is not None:
        return _cache_dir_override
    env = os.environ.get("SKTIME_CLI_HOME")
    if env:
        return Path(env)
    import platformdirs

    return Path(platformdirs.user_cache_dir("sktime-cli"))


def subdir(name: str) -> Path:
    """Return a subdirectory of the workspace, creating it if needed.

    Parameters
    ----------
    name : str
        Path relative to the workspace root, e.g. ``"models"`` or
        ``"downloads/ucr"``.

    Returns
    -------
    Path
        The directory, which exists by the time this returns.
    """
    path = cli_home() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env_hash() -> str:
    """Fingerprint the installed distributions.

    The registry depends on which packages are installed, because soft
    dependencies decide what is importable. Hashing the whole distribution
    list means installing anything invalidates the cache, which is blunt but
    never wrong.

    Returns
    -------
    str
        Eight hex characters, stable for a given set of package versions.
    """
    from importlib.metadata import distributions

    entries = sorted(
        (dist.metadata["Name"] or "?", dist.version or "?") for dist in distributions()
    )
    digest = hashlib.sha256(json.dumps(entries).encode()).hexdigest()
    return digest[:8]


def _registry_cache_path() -> Path:
    """Build the cache file path for the current environment.

    The filename carries the sktime version, the Python version, and the
    environment hash, so caches for different environments coexist and a
    change to any of them is a miss rather than stale data.

    Returns
    -------
    Path
        The cache file, which may not exist yet.
    """
    import platform

    import sktime

    py = f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}"
    name = f"registry-{sktime.__version__}-py{py}-{_env_hash()}.json"
    return cli_home() / "registry" / name


def _jsonify_tag(value: Any) -> Any:
    """Make a tag value JSON-storable, falling back to its repr.

    Tags can hold arbitrary Python objects, such as classes or callables, and
    the cache has to survive a JSON round trip. Anything unserializable
    becomes its repr, which stays readable for a human even though it can no
    longer be reconstructed.

    Parameters
    ----------
    value : Any
        The tag value as sktime reported it.

    Returns
    -------
    Any
        A JSON-serializable equivalent.
    """
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, (list, tuple)):
            return [_jsonify_tag(v) for v in value]
        return repr(value)


def build_registry() -> list[dict]:
    """Crawl sktime's registry into JSON-safe records.

    This is the expensive operation the cache exists to avoid: it imports
    every registered class to read its tags.

    Returns
    -------
    list of dict
        One record per object, each with ``name``, ``module``, ``scitypes``,
        ``tags``, ``python_dependencies``, ``installable``, ``params``, and
        ``param_defaults``. ``installable`` records whether the object's soft
        dependencies were satisfied when the crawl ran.

    Notes
    -----
    Parameter introspection is allowed to fail per object rather than aborting
    the crawl, because one malformed class should not make the whole registry
    unavailable.
    """
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
    """Return the registry records, reading the disk cache when possible.

    This is the latency lever for agents: the first call crawls and
    serializes, and every later call is a JSON load.

    Parameters
    ----------
    force_rebuild : bool, default False
        Crawl even when a valid cache exists, and rewrite it.

    Returns
    -------
    list of dict
        Records as described in :func:`build_registry`.

    Notes
    -----
    A cache that is corrupt, or written under a different
    :data:`REGISTRY_SCHEMA_VERSION`, is discarded and rebuilt rather than
    read. A cache directory that cannot be written is not an error; the live
    crawl is still served.
    """
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
    """Find one registry record by exact object name.

    Parameters
    ----------
    name : str
        Object name as sktime registers it, e.g. ``"NaiveForecaster"``.

    Returns
    -------
    dict or None
        The record, or ``None`` if no object has that name. Callers turn the
        ``None`` into a ``not_found`` error with a suggestion.
    """
    for record in get_registry():
        if record["name"] == name:
            return record
    return None


def import_object(record: dict):
    """Import the class a registry record points to.

    Records store a module path rather than the class itself, so that the
    cache stays JSON and only the modules actually used get imported.

    Parameters
    ----------
    record : dict
        A record from :func:`get_registry` or :func:`lookup`.

    Returns
    -------
    type
        The class.

    Raises
    ------
    CliError
        ``missing_dependency`` if the module needs a package that is not
        installed. The record's declared dependencies are preferred for the
        message, falling back to whatever the import error named.
    """
    import importlib

    from sktime_cli._errors import missing_dependency, packages_from_error

    try:
        module = importlib.import_module(record["module"])
        return getattr(module, record["name"])
    except ModuleNotFoundError as err:
        deps = record.get("python_dependencies") or packages_from_error(err)
        raise missing_dependency(record["name"], deps) from err
