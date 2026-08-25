"""``sktime-cli registry``: discover sktime objects (mirrors query_registry)."""

from __future__ import annotations

import difflib

import typer

from sktime_cli import _cache
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._output import OutputFormat, emit_record, emit_table, resolve_format
from sktime_cli._specs import parse_value

app = typer.Typer(no_args_is_help=True)


def _parse_tag_filters(filters: list[str]) -> dict:
    """Parse repeated ``--filter-tag KEY=VALUE`` options into a filter mapping.

    Parameters
    ----------
    filters : list of str
        Raw option values. A comma in the value means "any of", so
        ``scitype:y=univariate,both`` matches either.

    Returns
    -------
    dict
        Tag name to wanted value, or to a list of acceptable values.

    Raises
    ------
    CliError
        ``usage`` for a value with no ``=``.
    """
    parsed = {}
    for item in filters:
        if "=" not in item:
            raise CliError("usage", f"--filter-tag expects KEY=VALUE, got {item!r}")
        key, _, raw = item.partition("=")
        if "," in raw:
            parsed[key.strip()] = [parse_value(part) for part in raw.split(",")]
        else:
            parsed[key.strip()] = parse_value(raw)
    return parsed


def _tag_matches(tag_value, wanted) -> bool:
    """Test one tag value against a wanted value.

    Both sides may be lists, and they mean different things: a list of wanted
    values is a disjunction, while a list tag value is a set the wanted value
    must appear in.

    Parameters
    ----------
    tag_value : Any
        The value the object declares.
    wanted : Any
        The value, or values, asked for.

    Returns
    -------
    bool
        Whether the object matches.
    """
    if isinstance(wanted, list):
        return any(_tag_matches(tag_value, w) for w in wanted)
    if isinstance(tag_value, list):
        return wanted in tag_value
    return tag_value == wanted


def _validate_scitype(scitype: str) -> None:
    """Check a scitype exists before filtering on it.

    Catching a typo here turns a confusing empty result into an error that
    points at the command listing the valid names.

    Parameters
    ----------
    scitype : str
        The name to check.

    Raises
    ------
    CliError
        ``not_found`` if sktime declares no such scitype.
    """
    from sktime.registry import BASE_CLASS_SCITYPE_LIST

    if scitype not in BASE_CLASS_SCITYPE_LIST:
        raise CliError(
            "not_found",
            f"unknown scitype: {scitype}",
            hint="list scitypes with: sktime-cli registry types",
        )


def _validate_tags(names: list[str], scitype: str | None) -> None:
    """Reject tag names that cannot match, so a typo is not an empty result.

    Filtering on a tag no object carries can only return nothing, which reads
    the same as a genuine no-match. Restricting to a scitype narrows this
    further: a tag can be real and still never appear on the kind of object
    being searched, which is the more common mistake, since sktime moves tags
    between object types across releases.

    Parameters
    ----------
    names : list of str
        Tag names from ``--filter-tag`` and ``--with-tags``.
    scitype : str or None
        The scitype being searched, if one was given.

    Raises
    ------
    CliError
        ``not_found`` naming the tags that cannot match, with close matches
        drawn from the tags that are actually available here.
    """
    if not names:
        return
    available = {
        tag
        for record in _cache.get_registry()
        if not scitype or scitype in record["scitypes"]
        for tag in record["tags"]
    }
    unknown = [name for name in names if name not in available]
    if not unknown:
        return
    subject = f"{scitype}s" if scitype else "sktime objects"
    close = difflib.get_close_matches(unknown[0], sorted(available), n=3)
    raise CliError(
        "not_found",
        f"no {subject} carry the tag(s): {', '.join(unknown)}",
        hint=(
            f"did you mean: {', '.join(close)}"
            if close
            else f"list tags with: sktime-cli registry tags {scitype or ''}".strip()
        ),
    )


@app.command("search")
@handle_errors
def search(
    scitype: str | None = typer.Argument(
        None, help="Restrict to one scitype, e.g. forecaster, classifier."
    ),
    filter_tag: list[str] = typer.Option(
        [],
        "--filter-tag",
        "-t",
        help="Tag filter KEY=VALUE (repeatable, AND); comma in VALUE means OR.",
    ),
    name: str | None = typer.Option(
        None, "--name", "-n", help="Substring match on the object name."
    ),
    exclude: list[str] = typer.Option([], "--exclude", help="Exclude object names."),
    with_tags: str | None = typer.Option(
        None, "--with-tags", help="Comma-separated tags to add as columns."
    ),
    installable_only: bool = typer.Option(
        False,
        "--installable-only",
        help="Only objects whose soft dependencies are installed.",
    ),
    limit: int | None = typer.Option(None, "--limit", help="Maximum results."),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Search sktime's estimator registry."""
    fmt = resolve_format(format_, json_)
    if scitype:
        _validate_scitype(scitype)
    filters = _parse_tag_filters(filter_tag)
    extra_tags = [t.strip() for t in with_tags.split(",")] if with_tags else []
    _validate_tags([*filters, *extra_tags], scitype)

    rows = []
    for record in _cache.get_registry():
        if scitype and scitype not in record["scitypes"]:
            continue
        if record["name"] in exclude:
            continue
        if name and name.lower() not in record["name"].lower():
            continue
        if installable_only and not record["installable"]:
            continue
        tags = record["tags"]
        if any(
            key not in tags or not _tag_matches(tags[key], wanted)
            for key, wanted in filters.items()
        ):
            continue
        row = {
            "name": record["name"],
            "scitypes": record["scitypes"],
            "module": record["module"],
            "installable": record["installable"],
        }
        for tag in extra_tags:
            row[tag] = tags.get(tag)
        rows.append(row)
        if limit and len(rows) >= limit:
            break
    emit_table(rows, fmt, quiet_key="name")


@app.command("describe")
@handle_errors
def describe(
    name: str = typer.Argument(..., help="Exact object name, e.g. NaiveForecaster."),
    test_params: bool = typer.Option(
        False, "--test-params", help="Include get_test_params() example configs."
    ),
    no_doc: bool = typer.Option(
        False, "--no-doc", help="Skip the docstring (avoids importing the module)."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Describe one sktime object: params, tags, dependencies, docstring."""
    fmt = resolve_format(format_, json_)
    record = _cache.lookup(name)
    if record is None:
        raise CliError(
            "not_found",
            f"unknown object: {name}",
            hint="search with: sktime-cli registry search -n " + name,
        )

    defaults = record["param_defaults"]
    result = {
        "name": record["name"],
        "module": record["module"],
        "scitypes": record["scitypes"],
        "installable": record["installable"],
        "python_dependencies": record["python_dependencies"],
        "params": {
            param: {"default": defaults.get(param), "required": param not in defaults}
            for param in record["params"]
        },
        "tags": record["tags"],
    }
    if not record["installable"]:
        result["hint"] = "uv pip install " + " ".join(
            f'"{d}"' for d in record["python_dependencies"]
        )

    if not no_doc or test_params:
        try:
            cls = _cache.import_object(record)
            if not no_doc and cls.__doc__:
                doc = cls.__doc__.strip().splitlines()
                result["summary"] = doc[0].strip()
            if test_params:
                result["test_params"] = [
                    {k: repr(v) for k, v in params.items()}
                    for params in cls.get_test_params()
                ]
        except CliError:
            if test_params:
                raise  # doc is optional, test params are not
    emit_record(result, fmt, quiet_value=record["name"])


@app.command("tags")
@handle_errors
def tags(
    scitype: str | None = typer.Argument(
        None, help="Restrict to tags applicable to one scitype."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """List registry tags usable with --filter-tag."""
    from sktime.registry import all_tags

    fmt = resolve_format(format_, json_)
    if scitype:
        _validate_scitype(scitype)
    rows = [
        {
            "name": tag_name,
            "scitype": tag_scitypes
            if isinstance(tag_scitypes, str)
            else list(tag_scitypes),
            "type": str(tag_type),
            "description": description,
        }
        for tag_name, tag_scitypes, tag_type, description in all_tags(
            estimator_types=scitype
        )
    ]
    emit_table(rows, fmt, quiet_key="name")


@app.command("types")
@handle_errors
def types(
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """List sktime scitypes (object categories) with object counts."""
    from sktime.registry import BASE_CLASS_REGISTER

    fmt = resolve_format(format_, json_)
    counts: dict[str, int] = {}
    for record in _cache.get_registry():
        for st in record["scitypes"]:
            counts[st] = counts.get(st, 0) + 1
    rows = [
        {
            "scitype": entry[0],
            "description": entry[2] if len(entry) > 2 else "",
            "count": counts.get(entry[0], 0),
        }
        for entry in BASE_CLASS_REGISTER
    ]
    emit_table(rows, fmt, quiet_key="scitype")
