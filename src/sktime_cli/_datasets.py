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
    "unit_test": {"loader": "load_unit_test", "task": "classification"},
    "covid_3month": {"loader": "load_covid_3month", "task": "regression"},
}

REMOTE_SOURCES = ("ucr", "tsf", "fpp3")


def display_source(source: str) -> str:
    """Name a source the way users select it: both local kinds are ``builtin``."""
    return "builtin" if source in ("object", "loader") else source


_REMOTE_TASK = {"ucr": "classification", "tsf": "forecasting", "fpp3": "forecasting"}

# sktime `task_type` tag value -> the CLI's task vocabulary
_TASK_FROM_TAG = {
    "forecaster": "forecasting",
    "classifier": "classification",
    "regressor": "regression",
}


def task_of(record: dict) -> str:
    """Map a dataset object's ``task_type`` tag to the CLI task name."""
    tag = record["tags"].get("task_type")
    values = tag if isinstance(tag, list) else [tag]
    for value in values:
        if value in _TASK_FROM_TAG:
            return _TASK_FROM_TAG[value]
    return "unknown"


def object_index() -> dict[str, dict]:
    """Map dataset id -> registry record, for every named sktime dataset object."""
    index: dict[str, dict] = {}
    for record in _cache.get_registry():
        if not any(s.startswith("dataset") for s in record["scitypes"]):
            continue
        name = record["tags"].get("name")
        if isinstance(name, str) and name:
            index[name] = record
    return index


def _remote_names() -> dict[str, list[str]]:
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
    """Resolve a dataset id to ``(source, canonical_name)``.

    ``source`` is ``object`` (an sktime dataset object), ``loader`` (a loader
    function with no object), or one of the remote namespaces.
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
    """Instantiate an sktime dataset object and load the requested split."""
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

    if task == "forecasting":
        # forecasting objects return the series as y and exogenous data as X
        return {"task": task, "y": y, "X": X, "tags": record["tags"]}
    return {"task": task, "X": X, "y": y, "tags": record["tags"]}


def _load_loader(name: str, split: str | None) -> dict[str, Any]:
    """Load one of the datasets sktime exposes only as a loader function."""
    import sktime.datasets as skd

    entry = LOADER_ONLY[name]
    loader = getattr(skd, entry["loader"])
    kwargs = {"split": split.upper()} if split else {}
    X, y = loader(**kwargs)
    return {"task": entry["task"], "X": X, "y": y}


def load(source: str, name: str, split: str | None = None) -> dict[str, Any]:
    """Load a dataset; returns ``{task, y?, X?, metadata?, tags?}``."""
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
        return {"task": "classification", "X": X, "y": y}

    if source == "tsf":
        data, metadata = skd.load_forecastingdata(
            name, extract_path=str(subdir("downloads/tsf"))
        )
        return {"task": "forecasting", "y": data, "metadata": metadata}

    if source == "fpp3":
        data = skd.load_fpp3(name, temp_folder=str(subdir("downloads/fpp3")))
        return {"task": "forecasting", "y": data}

    raise CliError("internal", f"unhandled dataset source: {source}")


# tags worth surfacing in ``datasets describe``, in display order
DESCRIBE_TAGS = [
    "n_instances",
    "n_timepoints",
    "n_dimensions",
    "frequency",
    "is_univariate",
    "is_equally_spaced",
    "has_nans",
    "has_exogenous",
    "n_splits",
    "n_panels",
    "n_hierarchy_levels",
]


def describe_tags(record: dict) -> dict:
    """Pick the informative tags of a dataset object, skipping empty ones."""
    tags = record["tags"]
    return {key: tags[key] for key in DESCRIBE_TAGS if tags.get(key) is not None}


def listing(
    source: str | None = None, task: str | None = None, contains: str | None = None
) -> list[dict]:
    """Rows for ``datasets list``."""
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
    """Report whether loading the dataset downloads rather than reads bundled data."""
    module = record.get("module", "")
    # sktime bundles its builtin datasets except the download-backed ones
    return any(part in module for part in ("solar", "m5"))
