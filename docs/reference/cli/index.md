# CLI reference

This section is generated from the application itself, so it matches
`sktime-cli --help` for the version you're reading. Each command group has its
own page, listed in the sidebar and at the bottom of this one.

Global options are accepted before any subcommand. `--format` and `--json` are
also accepted on every leaf command, where they override the global value and
so are not repeated in each command's option list.

```{typer-cli} sktime_cli.app:app
:prog: sktime-cli
:no-subcommands:
```

## Command groups

::::{grid} 1 2 2 3
:gutter: 2

:::{grid-item-card} `registry`
:link: registry
:link-type: doc

Discover sktime objects.
:::

:::{grid-item-card} `datasets`
:link: datasets
:link-type: doc

List and fetch datasets.
:::

:::{grid-item-card} `catalogues`
:link: catalogues
:link-type: doc

Browse benchmark catalogues.
:::

:::{grid-item-card} `data`
:link: data
:link-type: doc

Inspect, convert, and split data files.
:::

:::{grid-item-card} `run`
:link: run
:link-type: doc

Fit, predict, transform, detect, evaluate.
:::

:::{grid-item-card} `model`
:link: model
:link-type: doc

Inspect saved model artifacts.
:::

:::{grid-item-card} `metrics`
:link: metrics
:link-type: doc

List metrics and score results.
:::

:::{grid-item-card} Environment
:link: environment-commands
:link-type: doc

`version`, `env`, `doctor`, `check`, and `cache`.
:::

::::

```{toctree}
:hidden:

registry
datasets
catalogues
data
run
model
metrics
environment-commands
```
