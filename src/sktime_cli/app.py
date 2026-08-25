"""Typer application root for sktime-cli."""

from __future__ import annotations

from pathlib import Path

import typer

from sktime_cli import __version__, _cache
from sktime_cli._errors import CliError
from sktime_cli._output import OutputFormat, set_root_format

app = typer.Typer(
    name="sktime-cli",
    help=(
        "Command-line interface for sktime, designed for AI agents and humans.\n\n"
        "Discover estimators (registry), fetch datasets, inspect and convert "
        "time series files (data), and run one-shot fit/predict/evaluate "
        "workflows. All commands support --format json for machine-readable "
        "output."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    """Print the version and exit, before any other option is processed.

    Eager, so ``--version`` works without the arguments a subcommand would
    otherwise require.
    """
    if value:
        print(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    format_: OutputFormat = typer.Option(
        OutputFormat.auto,
        "--format",
        envvar="SKTIME_CLI_FORMAT",
        help="Output format: auto|human|agent|json|quiet.",
    ),
    json_: bool = typer.Option(False, "--json", help="Shorthand for --format json."),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Workspace/cache directory (default: $SKTIME_CLI_HOME or XDG cache).",
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Bypass the registry disk cache."
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print sktime-cli version and exit.",
    ),
) -> None:
    """Configure global options; every subcommand runs after this."""
    if json_ and format_ not in (OutputFormat.auto, OutputFormat.json):
        raise CliError("usage", f"cannot combine --json with --format {format_.value}")
    set_root_format(OutputFormat.json if json_ else format_)
    _cache.set_cache_dir(cache_dir)
    _cache.set_no_cache(no_cache)


def _register_commands() -> None:
    """Attach every command group to the root application.

    Kept a function, with its imports inside, so the order in which command
    modules are imported is explicit and the help listing order is the one
    written here rather than an accident of import order.
    """
    from sktime_cli.commands import (
        catalogues,
        check,
        data,
        datasets,
        env,
        metrics,
        model,
        registry,
        run,
    )

    app.command("version")(env.version)
    app.command("env")(env.env_info)
    app.command("doctor")(env.doctor)
    app.add_typer(env.cache_app, name="cache")
    app.add_typer(registry.app, name="registry", help="Discover sktime objects.")
    app.add_typer(datasets.app, name="datasets", help="List and fetch datasets.")
    app.add_typer(
        catalogues.app, name="catalogues", help="Browse benchmark catalogues."
    )
    app.add_typer(data.app, name="data", help="Inspect, convert, split data files.")
    app.add_typer(
        run.app, name="run", help="One-shot fit/predict/transform/detect/evaluate."
    )
    app.add_typer(model.app, name="model", help="Inspect saved model artifacts.")
    app.add_typer(metrics.app, name="metrics", help="List metrics and score results.")
    app.command("check")(check.check)


_register_commands()


def main() -> None:
    """Run the CLI. This is the ``sktime-cli`` console-script entry point."""
    app()
