"""Estimator spec-string engine.

Specs are the CLI's way to name models: ``"NaiveForecaster(sp=12)"``,
compositions like ``"Deseasonalizer() * NaiveForecaster()"``, or a multi-line
block ending in ``return`` (same grammar as ``sktime.registry.craft``).

Resolution is sktime-first from the cached registry (imports only the modules
actually named). ``registry.craft`` is used only as a fallback for non-sktime
names, because upstream ``craft`` crawls sklearn and currently fails with
``ModuleNotFoundError: pytest`` in lean environments (sklearn's conftest.py is
imported by the crawl).
"""

from __future__ import annotations

import ast
import json
import textwrap
from typing import Any

from sktime_cli import _cache
from sktime_cli._errors import CliError, missing_dependency

# names allowed in specs beyond registry objects; keep minimal and boring
_SAFE_NAMES: dict[str, Any] = {
    "range": range,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "abs": abs,
    "min": min,
    "max": max,
}


def parse_value(text: str) -> Any:
    """Parse a CLI value: python literal, then JSON, then raw string."""
    text = text.strip()
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def _collect_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    loads, stores = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (loads if isinstance(node.ctx, ast.Load) else stores).add(node.id)
    return loads, stores


def _resolve_namespace(names: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Import registry objects for ``names``; return (namespace, unknown)."""
    namespace = dict(_SAFE_NAMES)
    unknown = []
    for name in sorted(names):
        if name in namespace:
            continue
        record = _cache.lookup(name)
        if record is None:
            unknown.append(name)
            continue
        if not record.get("installable", True):
            raise missing_dependency(name, record.get("python_dependencies") or [])
        namespace[name] = _cache.import_object(record)
    return namespace, unknown


def _craft_fallback(spec: str, unknown: list[str]):
    """Delegate to sktime's craft for specs using non-sktime names."""
    try:
        from sktime.registry import craft

        return craft(spec)
    except ModuleNotFoundError as err:
        if err.name == "pytest":
            raise CliError(
                code="missing_dependency",
                message=(
                    f"spec uses non-sktime name(s) {unknown}; resolving those "
                    "requires sktime's sklearn crawl, which needs pytest"
                ),
                hint=(
                    "uv pip install pytest  # or use sktime-native components; "
                    "find them with: sktime-cli registry search"
                ),
            ) from err
        raise missing_dependency(f"spec {spec!r}", str(err.name)) from err
    except Exception as err:
        raise CliError(
            code="spec_error",
            message=f"unknown name(s) in spec: {', '.join(unknown)}",
            hint="list available objects with: sktime-cli registry search",
            detail=str(err),
        ) from err


def build_estimator(spec: str, sets: list[str] | tuple = ()):
    """Construct an estimator/object from a spec string, then apply --set."""
    spec = textwrap.dedent(spec).strip()
    if not spec:
        raise CliError("spec_error", "empty spec string")

    try:
        tree: ast.AST = ast.parse(spec, mode="eval")
        mode = "eval"
    except SyntaxError:
        src = "def _build():\n" + textwrap.indent(spec, "    ")
        try:
            tree = ast.parse(src)
            mode = "exec"
        except SyntaxError as err:
            raise CliError(
                "spec_error", f"invalid spec: {err.msg}", detail=spec
            ) from None

    loads, stores = _collect_names(tree)
    namespace, unknown = _resolve_namespace(loads - stores)
    if unknown:
        obj = _craft_fallback(spec, unknown)
    else:
        try:
            if mode == "eval":
                code = compile(tree, "<spec>", "eval")
                obj = eval(code, {"__builtins__": {}}, namespace)  # noqa: S307
            else:
                globalns: dict[str, Any] = {"__builtins__": {}, **namespace}
                exec(compile(tree, "<spec>", "exec"), globalns)  # noqa: S102
                obj = globalns["_build"]()
        except CliError:
            raise
        except ModuleNotFoundError as err:
            raise missing_dependency(f"spec {spec!r}", str(err.name)) from err
        except Exception as err:
            raise CliError(
                "spec_error",
                f"spec failed to construct: {type(err).__name__}: {err}",
                detail=spec,
            ) from err

    if isinstance(obj, type):  # bare class name: instantiate with defaults
        obj = obj()
    return apply_sets(obj, sets)


def apply_sets(obj, sets: list[str] | tuple):
    """Apply repeatable ``--set key=value`` overrides via ``set_params``."""
    if not sets:
        return obj
    params = {}
    for item in sets:
        if "=" not in item:
            raise CliError("usage", f"--set expects key=value, got {item!r}")
        key, _, value = item.partition("=")
        params[key.strip()] = parse_value(value)
    try:
        obj.set_params(**params)
    except ValueError as err:
        raise CliError(
            "usage",
            f"invalid --set parameter: {err}",
            hint=f"valid params: {', '.join(obj.get_params(deep=True))}",
        ) from err
    return obj


def resolve_metric(name_or_spec: str):
    """Resolve a --metric value: a registry name or a full spec string."""
    if "(" in name_or_spec:
        return build_estimator(name_or_spec)
    record = _cache.lookup(name_or_spec)
    if record is None or not any(
        s.startswith("metric") for s in record.get("scitypes", [])
    ):
        raise CliError(
            "not_found",
            f"unknown metric: {name_or_spec}",
            hint="list metrics with: sktime-cli registry search metric_forecasting",
        )
    return _cache.import_object(record)()


def resolve_cv(spec: str | None, fh, initial_window: int | None, n_obs: int):
    """Resolve --cv: a splitter spec string, or a default expanding window."""
    if spec:
        return build_estimator(spec)
    from sktime.split import ExpandingWindowSplitter

    window = initial_window or max(n_obs // 2, 1)
    return ExpandingWindowSplitter(initial_window=window, fh=fh.to_pandas().tolist())
