# CLI reference

This page is generated from the application itself, so it matches
`sktime-cli --help` for the version you're reading.

Global options are accepted before any subcommand. `--format` and `--json` are
also accepted on every leaf command, where they override the global value.

```{typer-cli} sktime_cli.app:app
:prog: sktime-cli
```
