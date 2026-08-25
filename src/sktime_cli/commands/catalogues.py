"""``sktime-cli catalogues``: browse sktime's benchmark catalogues.

A catalogue bundles the datasets, estimators, metrics and splitters that make
up a published benchmark (the M4 competition, the classification bake-off), so
a run can be reproduced without transcribing the setup by hand.
"""

from __future__ import annotations

import typer

from sktime_cli import _cache
from sktime_cli._errors import CliError
from sktime_cli._guard import FORMAT_OPT, JSON_OPT, handle_errors
from sktime_cli._output import OutputFormat, emit_record, emit_table, resolve_format

app = typer.Typer(no_args_is_help=True)

CATALOGUE_SCITYPE = "catalogue"


def _records() -> list[dict]:
    """Return the registry records of every catalogue this sktime ships.

    Returns
    -------
    list of dict
        Registry records carrying the catalogue scitype.
    """
    return [
        record
        for record in _cache.get_registry()
        if CATALOGUE_SCITYPE in record["scitypes"]
    ]


def _lookup(name: str) -> dict:
    """Find one catalogue by exact name.

    Parameters
    ----------
    name : str
        Catalogue name, e.g. ``"BakeOffCatalogue"``.

    Returns
    -------
    dict
        Its registry record.

    Raises
    ------
    CliError
        ``not_found`` pointing at the listing command.
    """
    for record in _records():
        if record["name"] == name:
            return record
    raise CliError(
        "not_found",
        f"unknown catalogue: {name}",
        hint="list them with: sktime-cli catalogues list",
    )


@app.command("list")
@handle_errors
def list_(
    name: str | None = typer.Option(
        None, "--name", "-n", help="Substring match on the catalogue name."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """List the benchmark catalogues this sktime version ships."""
    fmt = resolve_format(format_, json_)
    rows = [
        {
            "name": record["name"],
            "catalogue_type": record["tags"].get("catalogue_type"),
            "installable": record["installable"],
        }
        for record in _records()
        if not name or name.lower() in record["name"].lower()
    ]
    emit_table(rows, fmt, quiet_key="name")


@app.command("get")
@handle_errors
def get(
    name: str = typer.Argument(..., help="Catalogue name, e.g. BakeOffCatalogue."),
    object_type: str = typer.Option(
        "all", "--type", help="Category to return: all, or one of its categories."
    ),
    format_: OutputFormat = FORMAT_OPT,
    json_: bool = JSON_OPT,
) -> None:
    """Show a catalogue's contents as specs reusable with `run` and `--cv`."""
    fmt = resolve_format(format_, json_)
    record = _lookup(name)
    catalogue = _cache.import_object(record)()

    categories = list(catalogue.available_categories())
    if object_type != "all" and object_type not in categories:
        raise CliError(
            "usage",
            f"catalogue {name} has no {object_type!r} entries",
            hint=f"available categories: {', '.join(categories)}",
        )

    entries = catalogue.get(object_type=object_type)
    emit_record(
        {
            "name": name,
            "catalogue_type": record["tags"].get("catalogue_type"),
            "categories": categories,
            "entries": [_entry(item) for item in entries],
        },
        fmt,
        quiet_value="\n".join(str(_entry(item)) for item in entries),
    )


def _entry(item):
    """Render one catalogue entry as a string usable as a spec.

    Catalogues mix bare names with ``{name: spec}`` pairs; the pair's value is
    the constructed form, which is what a caller can pass back to ``run``.

    Parameters
    ----------
    item : str or dict
        One entry as the catalogue returned it.

    Returns
    -------
    str
        The entry as a spec string.
    """
    if isinstance(item, dict):
        # {name: spec} pairs carry the constructed form as the value
        return next(iter(item.values()))
    return str(item)
