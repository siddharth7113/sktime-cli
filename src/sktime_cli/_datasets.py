"""Dataset name resolution and loading, driven by sktime's dataset objects.

Dataset ids are namespaced: bare names (``airline``, ``arrow_head``) resolve to
sktime dataset *objects* in the registry, ``ucr:ArrowHead``
(timeseriesclassification.com), ``tsf:m1_yearly_dataset``
(forecastingdata.org), and ``fpp3:aus_arrivals`` (Forecasting: Principles and
Practice) resolve to the corresponding remote loaders. Bare names are resolved
object-first, then across the remote registries; ambiguity is an error listing
the namespaced candidates.

Bare names are exactly the ``name`` tags sktime's dataset objects declare, so
they follow upstream rather than a local spelling (``gun_point``, not
``gunpoint``).

The bare-name catalogue is *not* hand-maintained: it comes from the ``name``
tag of every dataset object in the registry, so a dataset added upstream is
available here with no change. Each object also carries ``task_type``,
``n_timepoints``, ``frequency``, ``is_univariate`` and friends as tags, which
is what lets ``datasets describe`` answer without downloading anything.
"""

from __future__ import annotations

import difflib
from typing import Any

from sktime_cli import _cache
from sktime_cli._cache import subdir
from sktime_cli._errors import CliError, missing_dependency

# datasets sktime ships only as loader functions, with no registry object.
LOADER_ONLY: dict[str, dict[str, Any]] = {
    "unit_test": {"loader": "load_unit_test", "task": "classifier"},
    "covid_3month": {"loader": "load_covid_3month", "task": "regressor"},
}

REMOTE_SOURCES = ("ucr", "tsf", "fpp3")


# The dataset scitypes sktime declares, read from the registry rather than
# listed here, so a new dataset category is picked up automatically.
def dataset_scitypes() -> tuple[str, ...]:
    """Return every scitype sktime uses for datasets.

    Read from the registry rather than listed here, so a dataset category
    added upstream is recognized without a change.

    Returns
    -------
    tuple of str
        Scitype names, e.g. ``("dataset", "dataset_forecasting", ...)``.
    """
    from sktime.registry import BASE_CLASS_SCITYPE_LIST

    return tuple(s for s in BASE_CLASS_SCITYPE_LIST if s.startswith("dataset"))


def display_source(source: str) -> str:
    """Name a source the way a user selects it.

    Resolution distinguishes ``object`` from ``loader`` because they load
    differently, but that split is an implementation detail: both are the
    built-in catalogue as far as ``--source`` is concerned.

    Parameters
    ----------
    source : str
        A source from :func:`resolve`.

    Returns
    -------
    str
        ``"builtin"`` for either local kind, otherwise the source unchanged.
    """
    return "builtin" if source in ("object", "loader") else source


# Remote sources publish no metadata, so their task is stated here. The values
# are sktime's own scitype names, the same vocabulary `registry search` uses,
# so no translation table is needed for the datasets that do carry tags.
_REMOTE_TASK = {"ucr": "classifier", "tsf": "forecaster", "fpp3": "forecaster"}


def task_of(record: dict) -> str:
    """Return which task a dataset is for.

    The value is sktime's own scitype name, the same vocabulary
    ``registry search`` takes, so no translation table is needed.

    Parameters
    ----------
    record : dict
        A registry record for a dataset object.

    Returns
    -------
    str
        ``"forecaster"``, ``"classifier"``, ``"regressor"``, or ``"unknown"``
        when the object declares no task.
    """
    tag = record["tags"].get("task_type")
    values = tag if isinstance(tag, list) else [tag]
    return next((v for v in values if v), "unknown")


def object_index() -> dict[str, dict]:
    """Build the catalogue of built-in datasets from the registry.

    The catalogue is not maintained here: it is every dataset object sktime
    registers, keyed by the ``name`` tag the object declares. A dataset added
    upstream appears with no change to this project.

    Returns
    -------
    dict
        Dataset id to registry record. Objects with no ``name`` tag are
        parameterized loaders such as ``UCRUEADataset``, and are reached
        through a namespace prefix instead.
    """
    index: dict[str, dict] = {}
    for record in _cache.get_registry():
        if not any(s.startswith("dataset") for s in record["scitypes"]):
            continue
        name = record["tags"].get("name")
        if isinstance(name, str) and name:
            index[name] = record
    return index


def _remote_names() -> dict[str, list[str]]:
    """List the dataset names each remote archive publishes.

    Returns
    -------
    dict
        Source name to sorted dataset names, for ``ucr``, ``tsf``, and
        ``fpp3``. These are catalogue listings only; nothing is downloaded.
    """
    from sktime.datasets import DATASET_NAMES_FPP3, tsc_dataset_names
    from sktime.datasets.tsf_dataset_names import tsf_all

    return {
        "ucr": sorted(
            set(tsc_dataset_names.univariate) | set(tsc_dataset_names.multivariate)
        ),
        "tsf": sorted(tsf_all),
        "fpp3": sorted(DATASET_NAMES_FPP3),
    }


def resolve(name: str) -> tuple[str, str]:
    """Resolve a dataset id to the source that can load it.

    A prefixed id pins its source. A bare name is looked up in the built-in
    catalogue first, then case-insensitively across the remote archives.

    Parameters
    ----------
    name : str
        A dataset id, e.g. ``"airline"`` or ``"ucr:ArrowHead"``.

    Returns
    -------
    tuple of str
        ``(source, canonical_name)``. The source is ``object`` for an sktime
        dataset object, ``loader`` for one sktime exposes only as a function,
        or a remote namespace.

    Raises
    ------
    CliError
        ``not_found`` for an unknown name, with close matches as the hint;
        ``usage`` for an unknown namespace, or a bare name that several
        archives publish, listing the prefixed forms to disambiguate.
    """
    if ":" in name:
        source, _, rest = name.partition(":")
        if source not in REMOTE_SOURCES:
            raise CliError(
                "usage", f"unknown dataset namespace {source!r}: use ucr:|tsf:|fpp3:"
            )
        remote = _remote_names()[source]
        if rest not in remote:
            close = difflib.get_close_matches(rest, remote, n=3)
            raise CliError(
                "not_found",
                f"unknown {source} dataset: {rest}",
                hint=f"did you mean: {', '.join(close)}" if close else None,
            )
        return source, rest

    if name in object_index():
        return "object", name
    if name in LOADER_ONLY:
        return "loader", name

    remote = _remote_names()
    matches = [
        f"{source}:{candidate}"
        for source, names in remote.items()
        for candidate in names
        if candidate.lower() == name.lower()
    ]
    if len(matches) == 1:
        source, _, rest = matches[0].partition(":")
        return source, rest
    if len(matches) > 1:
        raise CliError(
            "usage",
            f"ambiguous dataset name {name!r}",
            hint=f"use one of: {', '.join(matches)}",
        )
    pool = (
        list(object_index())
        + list(LOADER_ONLY)
        + [f"{s}:{n}" for s, names in remote.items() for n in names]
    )
    close = difflib.get_close_matches(name, pool, n=3)
    raise CliError(
        "not_found",
        f"unknown dataset: {name}",
        hint=f"did you mean: {', '.join(close)}"
        if close
        else "list datasets with: sktime-cli datasets list",
    )


def _load_object(name: str, split: str | None) -> dict[str, Any]:
    """Load a dataset through its sktime dataset object.

    Parameters
    ----------
    name : str
        A key of :func:`object_index`.
    split : str or None
        ``"train"`` or ``"test"``, for datasets that define splits.

    Returns
    -------
    dict
        With ``task``, the data as ``X`` and ``y``, and the object's ``tags``.
        For forecasting datasets the series is ``y`` and exogenous data is
        ``X``.

    Raises
    ------
    CliError
        ``missing_dependency`` if the dataset needs an uninstalled package;
        ``usage`` if a split was asked for that the dataset does not define,
        listing the parts it does have.
    """
    record = object_index()[name]
    if not record.get("installable", True):
        raise missing_dependency(
            f"dataset {name}", record.get("python_dependencies") or []
        )
    dataset = _cache.import_object(record)()
    task = task_of(record)

    keys = list(dataset.keys())
    if split:
        wanted = [f"X_{split.lower()}", f"y_{split.lower()}"]
        missing = [key for key in wanted if key not in keys]
        if missing:
            raise CliError(
                "usage",
                f"dataset {name} has no {split} split",
                hint=f"available parts: {', '.join(keys)}",
            )
        X, y = dataset.load(*wanted)
    else:
        X, y = dataset.load("X", "y")

    if task == "forecaster":
        # forecasting objects return the series as y and exogenous data as X
        return {"task": task, "y": y, "X": X, "tags": record["tags"]}
    return {"task": task, "X": X, "y": y, "tags": record["tags"]}


def _load_loader(name: str, split: str | None) -> dict[str, Any]:
    """Load a dataset that sktime exposes only as a loader function.

    A small fallback for the datasets with no registry object, kept so that
    dropping the old hand-maintained table cost no coverage.

    Parameters
    ----------
    name : str
        A key of :data:`LOADER_ONLY`.
    split : str or None
        ``"train"`` or ``"test"``.

    Returns
    -------
    dict
        With ``task``, ``X``, and ``y``.
    """
    import sktime.datasets as skd

    entry = LOADER_ONLY[name]
    loader = getattr(skd, entry["loader"])
    kwargs = {"split": split.upper()} if split else {}
    X, y = loader(**kwargs)
    return {"task": entry["task"], "X": X, "y": y}


def load(source: str, name: str, split: str | None = None) -> dict[str, Any]:
    """Load a dataset from whichever source :func:`resolve` identified.

    Parameters
    ----------
    source : str
        A source from :func:`resolve`.
    name : str
        The canonical name from :func:`resolve`.
    split : str or None
        ``"train"`` or ``"test"``, where the source supports it.

    Returns
    -------
    dict
        Always carries ``task``, plus ``y`` and ``X`` as the task implies.
        Dataset objects add ``tags``, and Monash datasets add ``metadata``.

    Raises
    ------
    CliError
        ``missing_dependency`` if loading needs an uninstalled package, which
        is common for the remote archives; ``usage`` for an unavailable split.

    Notes
    -----
    Remote archives download into the workspace directory, so
    ``sktime-cli cache clear`` reclaims the space.
    """
    import sktime.datasets as skd

    if source == "object":
        return _load_object(name, split)
    if source == "loader":
        return _load_loader(name, split)

    if source == "ucr":
        X, y = skd.load_UCR_UEA_dataset(
            name,
            split=split.upper() if split else None,
            return_X_y=True,
            extract_path=str(subdir("downloads/ucr")),
        )
        return {"task": "classifier", "X": X, "y": y}

    if source == "tsf":
        data, metadata = skd.load_forecastingdata(
            name, extract_path=str(subdir("downloads/tsf"))
        )
        return {"task": "forecaster", "y": data, "metadata": metadata}

    if source == "fpp3":
        data = skd.load_fpp3(name, temp_folder=str(subdir("downloads/fpp3")))
        return {"task": "forecaster", "y": data}

    raise CliError("internal", f"unhandled dataset source: {source}")


# sktime's housekeeping tag namespaces: identity, packaging, and test control.
# Everything else a dataset object declares describes the data, so it is
# reported. Excluding by namespace means a tag added upstream shows up rather
# than being silently dropped by an allow-list.
_INTERNAL_TAG_PREFIXES = ("tests:", "python_", "property:", "capability:")
_INTERNAL_TAGS = frozenset({"name", "object_type", "env_marker", "sktime_version"})


def describe_tags(record: dict) -> dict:
    """Pick out the tags of a dataset object that describe the data.

    Selection is by excluding sktime's housekeeping namespaces rather than by
    listing what to keep, so a descriptive tag added upstream is surfaced
    instead of being silently dropped.

    Parameters
    ----------
    record : dict
        A registry record for a dataset object.

    Returns
    -------
    dict
        Tags such as ``frequency``, ``n_timepoints``, ``is_univariate``, and
        ``has_exogenous``. Tags set to ``None`` are omitted.
    """
    return {
        key: value
        for key, value in record["tags"].items()
        if value is not None
        and key not in _INTERNAL_TAGS
        and not key.startswith(_INTERNAL_TAG_PREFIXES)
    }


def listing(
    source: str | None = None, task: str | None = None, contains: str | None = None
) -> list[dict]:
    """Build the rows for ``datasets list``.

    Parameters
    ----------
    source : str or None
        Restrict to ``builtin`` or one remote archive. ``None`` lists all.
    task : str or None
        Restrict to a task, using sktime's scitype names.
    contains : str or None
        Case-insensitive substring the name must contain.

    Returns
    -------
    list of dict
        Rows with ``name``, ``source``, ``task``, ``offline``, and
        ``installable``. ``offline`` marks datasets that need no download.
    """
    rows: list[dict] = []

    if source in (None, "builtin"):
        for name, record in sorted(object_index().items()):
            rows.append(
                {
                    "name": name,
                    "source": "builtin",
                    "task": task_of(record),
                    "offline": not _needs_network(record),
                    "installable": record.get("installable", True),
                }
            )
        for name, entry in LOADER_ONLY.items():
            rows.append(
                {
                    "name": name,
                    "source": "builtin",
                    "task": entry["task"],
                    "offline": True,
                    "installable": True,
                }
            )

    if source in (None, *REMOTE_SOURCES):
        remote = _remote_names()
        for src, names in remote.items():
            if source not in (None, src):
                continue
            rows.extend(
                {
                    "name": f"{src}:{n}",
                    "source": src,
                    "task": _REMOTE_TASK[src],
                    "offline": False,
                    "installable": True,
                }
                for n in names
            )

    if task:
        rows = [r for r in rows if r["task"] and task in str(r["task"])]
    if contains:
        rows = [r for r in rows if contains.lower() in r["name"].lower()]
    return rows


def _needs_network(record: dict) -> bool:
    """Report whether loading a dataset downloads rather than reads bundled data.

    Parameters
    ----------
    record : dict
        A registry record for a dataset object.

    Returns
    -------
    bool
        True for the download-backed datasets. sktime bundles the rest, so
        this recognizes the exceptions by module.
    """
    module = record.get("module", "")
    # sktime bundles its builtin datasets except the download-backed ones
    return any(part in module for part in ("solar", "m5"))
