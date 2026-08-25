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
from sktime_cli._errors import CliError, missing_dependency, packages_from_error

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
    """Parse a value from the command line into a Python object.

    Tried in order: Python literal, then JSON, then the raw string. That order
    means ``12`` is an int, ``true`` is the string ``"true"`` while ``True`` is
    the boolean, and ``[1, 2]`` is a list either way.

    Parameters
    ----------
    text : str
        The value as typed, e.g. the right side of ``--set sp=12``.

    Returns
    -------
    Any
        The parsed value, or the stripped string when neither parser accepted
        it.
    """
    text = text.strip()
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def _collect_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Find every name a parsed spec reads and every name it assigns.

    Subtracting one from the other gives the free names, which are the ones
    that have to be resolved from the registry. A multi-line spec that binds
    an intermediate variable should not send that variable to the registry.

    Parameters
    ----------
    tree : ast.AST
        The parsed spec.

    Returns
    -------
    tuple of set of str
        ``(loaded, stored)`` names.
    """
    loads, stores = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (loads if isinstance(node.ctx, ast.Load) else stores).add(node.id)
    return loads, stores


def _resolve_namespace(
    names: set[str], extra: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Build the namespace a spec will be evaluated in.

    Only the modules actually named get imported, which is what keeps spec
    evaluation cheaper than sktime's own ``craft``.

    Parameters
    ----------
    names : set of str
        Free names appearing in the spec.
    extra : dict, optional
        Constructors to make available beyond the sktime registry, such as the
        sklearn splitters panel cross-validation expects.

    Returns
    -------
    tuple
        ``(namespace, unknown)``, where ``unknown`` lists names neither the
        registry nor ``extra`` provided. A non-empty ``unknown`` sends the
        caller to :func:`_craft_fallback`.

    Raises
    ------
    CliError
        ``missing_dependency`` if a named object exists but its soft
        dependencies are not installed.
    """
    namespace = dict(_SAFE_NAMES)
    namespace.update(extra or {})
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
    """Evaluate a spec that names objects outside sktime's registry.

    sktime's ``craft`` can resolve sklearn names, at the cost of crawling
    sklearn, which is slow and, in a lean environment, currently broken. It is
    therefore a fallback rather than the primary path.

    Parameters
    ----------
    spec : str
        The full spec string.
    unknown : list of str
        Names the registry could not resolve, reported if this fails too.

    Returns
    -------
    Any
        The constructed object.

    Raises
    ------
    CliError
        ``missing_dependency`` when the crawl needs a package that is absent,
        including the ``pytest`` case described in the module docstring;
        ``spec_error`` when the names are simply wrong.
    """
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
        raise missing_dependency(f"spec {spec!r}", packages_from_error(err)) from err
    except Exception as err:
        raise CliError(
            code="spec_error",
            message=f"unknown name(s) in spec: {', '.join(unknown)}",
            hint="list available objects with: sktime-cli registry search",
            detail=str(err),
        ) from err


def build_estimator(
    spec: str, sets: list[str] | tuple = (), extra_names: dict[str, Any] | None = None
):
    """Construct an sktime object from a spec string.

    This is how every command turns text into an estimator.

    Parameters
    ----------
    spec : str
        A constructor expression such as ``"NaiveForecaster(sp=12)"``, a
        composition such as ``"Deseasonalizer() * NaiveForecaster()"``, a bare
        class name, or a multi-line block ending in ``return``.
    sets : list of str, optional
        ``key=value`` overrides applied afterwards, where ``__`` reaches into
        nested components.
    extra_names : dict, optional
        Constructors to allow beyond the sktime registry.

    Returns
    -------
    Any
        The constructed object. A bare class name is instantiated with its
        defaults.

    Raises
    ------
    CliError
        ``spec_error`` for a spec that will not parse, names nothing known, or
        raises while constructing; ``missing_dependency`` when a named object
        needs a package that is absent; ``usage`` for a malformed ``--set``.

    Notes
    -----
    Specs are evaluated, not merely parsed, because composition operators need
    real objects. Evaluation runs with no builtins and a namespace holding
    only registry objects and a short list of safe constructors, so a spec
    cannot reach arbitrary Python.
    """
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
    namespace, unknown = _resolve_namespace(loads - stores, extra_names)
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
            raise missing_dependency(
                f"spec {spec!r}", packages_from_error(err)
            ) from err
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
    """Apply ``--set key=value`` overrides to a constructed object.

    Parameters
    ----------
    obj : Any
        The object to modify, in place.
    sets : list of str
        ``key=value`` strings. ``__`` reaches into nested components, e.g.
        ``forecaster__sp=4``. Values are parsed by :func:`parse_value`.

    Returns
    -------
    Any
        The same object, for chaining.

    Raises
    ------
    CliError
        ``usage`` for a string with no ``=``, or a parameter the object does
        not have. The error lists the parameters it does have.
    """
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
    """Resolve a ``--metric`` value to a metric object.

    Parameters
    ----------
    name_or_spec : str
        Either a bare metric name, which is instantiated with defaults, or a
        full spec string, which allows parameterizing the metric the same way
        an estimator is parameterized.

    Returns
    -------
    Any
        The metric object.

    Raises
    ------
    CliError
        ``not_found`` if the name is not a registered metric.
    """
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
    """Resolve ``--cv`` to a splitter for time series cross-validation.

    Parameters
    ----------
    spec : str or None
        A splitter spec string. When ``None`` an expanding window splitter is
        built from the remaining arguments.
    fh : ForecastingHorizon
        Horizon each fold forecasts, used only for the default splitter.
    initial_window : int or None
        How many observations the first fold trains on. Defaults to half the
        series.
    n_obs : int
        Length of the series, used to size that default.

    Returns
    -------
    Any
        A splitter object.
    """
    if spec:
        return build_estimator(spec)
    from sktime.split import ExpandingWindowSplitter

    window = initial_window or max(n_obs // 2, 1)
    return ExpandingWindowSplitter(initial_window=window, fh=fh.to_pandas().tolist())
