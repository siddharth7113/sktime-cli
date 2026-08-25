"""Dataset name resolution and loading.

Dataset IDs are namespaced: bare builtin names (``airline``, ``arrow_head``),
``ucr:ArrowHead`` (timeseriesclassification.com), ``tsf:m1_yearly_dataset``
(forecastingdata.org), ``fpp3:aus_arrivals`` (Forecasting: Principles and
Practice). Bare names are resolved builtin-first, then across the remote
registries; ambiguity is an error listing the namespaced candidates.
"""

from __future__ import annotations

import difflib
from typing import Any

from sktime_cli._cache import subdir
from sktime_cli._errors import CliError, missing_dependency

# builtin loaders bundled with sktime (offline unless noted).
# needs: soft deps; xy: loader returns (y, X) or (X, y) pairs.
BUILTIN: dict[str, dict[str, Any]] = {
    "airline": {"loader": "load_airline", "task": "forecasting"},
    "lynx": {"loader": "load_lynx", "task": "forecasting"},
    "shampoo_sales": {"loader": "load_shampoo_sales", "task": "forecasting"},
    "pbs": {"loader": "load_PBS_dataset", "task": "forecasting"},
    "longley": {"loader": "load_longley", "task": "forecasting", "xy": "y_X"},
    "uschange": {
        "loader": "load_uschange",
        "task": "forecasting",
        "xy": "y_X",
        "needs": ["statsmodels"],
    },
    "macroeconomic": {
        "loader": "load_macroeconomic",
        "task": "forecasting",
        "needs": ["statsmodels"],
    },
    "solar": {"loader": "load_solar", "task": "forecasting", "network": True},
    "hierarchical_sales": {
        "loader": "load_hierarchical_sales_toydata",
        "task": "forecasting",
        "hierarchical": True,
    },
    "arrow_head": {"loader": "load_arrow_head", "task": "classification"},
    "gunpoint": {"loader": "load_gunpoint", "task": "classification"},
    "basic_motions": {"loader": "load_basic_motions", "task": "classification"},
    "osuleaf": {"loader": "load_osuleaf", "task": "classification"},
    "acsf1": {"loader": "load_acsf1", "task": "classification"},
    "italy_power_demand": {
        "loader": "load_italy_power_demand",
        "task": "classification",
    },
    "japanese_vowels": {"loader": "load_japanese_vowels", "task": "classification"},
    "plaid": {"loader": "load_plaid", "task": "classification"},
    "unit_test": {"loader": "load_unit_test", "task": "classification"},
    "covid_3month": {"loader": "load_covid_3month", "task": "regression"},
    "tecator": {"loader": "load_tecator", "task": "regression"},
}


# soft dependencies a remote source needs on top of sktime itself
REMOTE_NEEDS: dict[str, list[str]] = {"fpp3": ["requests", "rdata"]}


def _require(what: str, deps: list[str]) -> None:
    """Fail with a ready-to-run install hint when soft dependencies are absent."""
    import importlib.util

    missing = [dep for dep in deps if importlib.util.find_spec(dep) is None]
    if missing:
        raise missing_dependency(what, missing)


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
    """Resolve a dataset id to (source, canonical_name)."""
    if ":" in name:
        source, _, rest = name.partition(":")
        if source not in ("ucr", "tsf", "fpp3"):
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

    if name in BUILTIN:
        return "builtin", name

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
    pool = list(BUILTIN) + [f"{s}:{n}" for s, names in remote.items() for n in names]
    close = difflib.get_close_matches(name, pool, n=3)
    raise CliError(
        "not_found",
        f"unknown dataset: {name}",
        hint=f"did you mean: {', '.join(close)}"
        if close
        else "list datasets with: sktime-cli datasets list",
    )


def load(source: str, name: str, split: str | None = None) -> dict[str, Any]:
    """Load a dataset; returns {task, y?, X?, metadata?}."""
    import sktime.datasets as skd

    if source == "builtin":
        entry = BUILTIN[name]
        _require(f"dataset {name}", entry.get("needs", []))
        loader = getattr(skd, entry["loader"])
        task = entry["task"]
        if task == "forecasting":
            result = loader()
            if entry.get("xy") == "y_X":
                y, X = result
                return {"task": task, "y": y, "X": X}
            return {"task": task, "y": result}
        kwargs = {"split": split.upper()} if split else {}
        X, y = loader(**kwargs)
        return {"task": task, "X": X, "y": y}

    _require(f"dataset {source}:{name}", REMOTE_NEEDS.get(source, []))

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


def listing(
    source: str | None = None, task: str | None = None, contains: str | None = None
) -> list[dict]:
    """Rows for ``datasets list``."""
    rows: list[dict] = []
    if source in (None, "builtin"):
        for name, entry in BUILTIN.items():
            rows.append(
                {
                    "name": name,
                    "source": "builtin",
                    "task": entry["task"],
                    "offline": not entry.get("network", False),
                }
            )
    if source in (None, "ucr", "tsf", "fpp3"):
        remote = _remote_names()
        remote_task = {
            "ucr": "classification",
            "tsf": "forecasting",
            "fpp3": "forecasting",
        }
        for src, names in remote.items():
            if source not in (None, src):
                continue
            rows.extend(
                {
                    "name": f"{src}:{n}",
                    "source": src,
                    "task": remote_task[src],
                    "offline": False,
                }
                for n in names
            )
    if source == "objects":
        from sktime_cli._cache import get_registry

        for record in get_registry():
            if any(s.startswith("dataset") for s in record["scitypes"]):
                tags = record["tags"]
                rows.append(
                    {
                        "name": record["name"],
                        "source": "objects",
                        "task": ",".join(tags.get("task_type") or [])
                        if isinstance(tags.get("task_type"), list)
                        else tags.get("task_type", ""),
                        "offline": False,
                    }
                )
    if task:
        rows = [r for r in rows if r["task"] and task in str(r["task"])]
    if contains:
        rows = [r for r in rows if contains.lower() in r["name"].lower()]
    return rows
