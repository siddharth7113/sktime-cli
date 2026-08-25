<div align="center">

# sktime-cli

**The command line for [sktime](https://github.com/sktime/sktime), built for AI agents and humans.**

Search estimators, fetch datasets, inspect time series files, and run
fit / predict / evaluate workflows straight from your shell.

[![PyPI](https://img.shields.io/pypi/v/sktime-cli?color=1a6690)](https://pypi.org/project/sktime-cli/)
[![Python](https://img.shields.io/pypi/pyversions/sktime-cli)](https://pypi.org/project/sktime-cli/)
[![Docs](https://img.shields.io/readthedocs/sktime-cli)](https://sktime-cli.readthedocs.io)
[![CI](https://github.com/siddharth7113/sktime-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/siddharth7113/sktime-cli/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green)](https://github.com/siddharth7113/sktime-cli/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

<img src="https://raw.githubusercontent.com/siddharth7113/sktime-cli/main/docs/assets/demo.svg" alt="Terminal session running registry search, datasets load, run fit, and run predict" width="900">

**[Read the documentation](https://sktime-cli.readthedocs.io)**

</div>

---

## Why a CLI

sktime is a Python library, so trying a forecaster usually means opening an
editor:

```python
import pandas as pd
from sktime.forecasting.naive import NaiveForecaster

y = pd.read_csv("airline.csv", index_col=0).squeeze()
y.index = pd.PeriodIndex(y.index, freq="M")

forecaster = NaiveForecaster(sp=12)
forecaster.fit(y)
print(forecaster.predict(fh=range(1, 13)))
```

The same forecast, from the shell:

```bash
sktime-cli run fit-predict "NaiveForecaster(sp=12)" --data airline.csv --fh 1:12
```

Both print the same twelve numbers. The difference is what you needed to know
first: that `NaiveForecaster` lives in `sktime.forecasting.naive`, and that
sktime wants a `PeriodIndex` rather than the strings the csv gave you. The
CLI works both of those out for you, from the file and the estimator name.

## What you get

Every command is one process. It reads files or names, calls sktime, writes
results, and exits with a meaningful code.

- **Fitted models are ordinary files.** No sessions, handles, or daemons.
  `run fit` writes a `.zip` you can copy, commit, or delete, and any later
  command picks it up by path. Run something twice and you get the same
  answer.
- **Search for an estimator instead of looking one up.**
  `registry search forecaster -t capability:missing_values=true` lists every
  forecaster that handles gaps, marking the ones whose dependencies you
  already have. Results come from a disk cache, so repeat searches are cheap.
- **Name a model instead of building one.** `"NaiveForecaster(sp=12)"` is the
  whole configuration. `*` composes a pipeline, `|` a multiplexer, and `+`
  a transformer union, so `"Deseasonalizer() * NaiveForecaster()"` is a
  model too.
- **Reads the files you already have.** csv, parquet, json, `.ts`, `.tsf`,
  and `.arff` go in. `--format human|agent|json|quiet` comes out.
- **Failures say what to do next.** A missing optional dependency exits `3`
  with the install command in the error's `hint`. Nothing fails with a bare
  traceback.

## Installation

```bash
uv tool install sktime-cli   # or: pip install sktime-cli
```

Check the setup and see which optional dependencies are available:

```bash
sktime-cli doctor
```

<div align="center">
<img src="https://raw.githubusercontent.com/siddharth7113/sktime-cli/main/docs/assets/doctor.svg" alt="Output of sktime-cli doctor, listing sktime version, cache state, and optional dependencies" width="900">
</div>

## Quickstart

```bash
# What can I use?
sktime-cli registry search forecaster -t capability:missing_values=true
sktime-cli registry describe NaiveForecaster

# Get data.
sktime-cli datasets load airline --output airline.csv
sktime-cli data inspect airline.csv

# Fit, predict, evaluate. Estimators are given as sktime spec strings.
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline.csv --model-out model.zip
sktime-cli run predict --model model.zip --fh 1:12
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline.csv --fh 1:12 \
  --metric MeanAbsolutePercentageError
```

`--data` takes either a file path or a dataset name, so once you know the name
you can skip the download and pass `--data airline` directly. A path is read
wins, so a local `airline.csv` shadows the built-in `airline` dataset.

For a longer walkthrough, see the
[quickstart](https://sktime-cli.readthedocs.io/en/latest/quickstart.html).

## Commands

| Group | Commands | What it does |
|---|---|---|
| `registry` | `search` · `describe` · `tags` · `types` | Find sktime estimators by scitype, name, and capability tag |
| `datasets` | `list` · `describe` · `load` | Browse and fetch built-in, UCR/UEA, Monash, and fpp3 datasets |
| `catalogues` | `list` · `get` | Browse sktime's benchmark catalogues |
| `data` | `inspect` · `convert` · `split` | Detect mtypes and scitypes, convert formats, split temporally and into folds |
| `run` | `fit` · `predict` · `fit-predict` · `transform` · `detect` · `evaluate` | One-shot workflows for forecasting, classification, transformation and detection |
| `model` | `inspect` | Look inside a saved model artifact and round-trip its spec |
| `metrics` | `list` · `score` | List metric objects and score predictions against observations |
| *(top level)* | `check` · `version` · `env` · `doctor` · `cache` | Validate an object against sktime's API, environment info, health check, workspace |

Every option is listed in the
[CLI reference](https://sktime-cli.readthedocs.io/en/latest/reference/cli/index.html),
which is generated from the application itself.

## Built for AI agents

Add `--json` to any command and you get exactly one parseable JSON document on
stdout. Errors are JSON on stderr, with stable codes and a `hint` field that
usually contains the fix.

<div align="center">
<img src="https://raw.githubusercontent.com/siddharth7113/sktime-cli/main/docs/assets/agent.svg" alt="JSON output from a command next to a structured error record and its exit code" width="900">
</div>

| Exit | Meaning |
|---|---|
| `0` | Success |
| `1` | Library or unexpected failure |
| `2` | Usage error |
| `3` | Missing optional dependency, and the hint says what to install |
| `4` | Estimator, dataset, or model not found |
| `5` | Data validation or spec error |

### Install the skill

The full agent contract and task recipes live in an
[agent skill](https://github.com/siddharth7113/sktime-cli/blob/main/src/sktime_cli/.agents/skills/sktime-cli/SKILL.md)
that ships inside the package, at the location package-bundled skills use. Add
`sktime-cli` to the project, then let
[library-skills](https://library-skills.io) find it:

```bash
uv add sktime-cli                  # or: pip install sktime-cli
uvx library-skills --claude        # installs the skills you pick from your packages
```

That symlinks the skill into `.agents/skills/`, and `--claude` adds
`.claude/skills/` for Claude Code. Your agent then knows how to drive the CLI.
To skip the prompt, name it: `uvx library-skills --claude --skill sktime-cli`.

If you installed the CLI as a standalone tool rather than as a project
dependency, copy the file instead:

```bash
mkdir -p ~/.claude/skills/sktime-cli
curl -fsSL https://raw.githubusercontent.com/siddharth7113/sktime-cli/main/src/sktime_cli/.agents/skills/sktime-cli/SKILL.md \
  -o ~/.claude/skills/sktime-cli/SKILL.md
```

For the details, see
[using sktime-cli from an agent](https://sktime-cli.readthedocs.io/en/latest/guide/agents.html).

## Documentation

Full documentation is at
**[sktime-cli.readthedocs.io](https://sktime-cli.readthedocs.io)**:

- [Quickstart](https://sktime-cli.readthedocs.io/en/latest/quickstart.html)
- [Finding estimators](https://sktime-cli.readthedocs.io/en/latest/guide/discovery.html)
- [Working with data](https://sktime-cli.readthedocs.io/en/latest/guide/data.html)
- [Fitting and evaluating models](https://sktime-cli.readthedocs.io/en/latest/guide/modeling.html)
- [Output formats and errors](https://sktime-cli.readthedocs.io/en/latest/guide/output.html)
- [CLI reference](https://sktime-cli.readthedocs.io/en/latest/reference/cli/index.html)
- [Architecture](https://sktime-cli.readthedocs.io/en/latest/contributing/architecture.html)
  and [design decisions](https://sktime-cli.readthedocs.io/en/latest/contributing/design.html)

## Status

`sktime-cli` is an independent, unofficial command-line client for sktime. It
is not maintained by or affiliated with the sktime project.

Version 0.0.2 is an early alpha release. Discovery and one-shot runs work, and
the [roadmap](https://sktime-cli.readthedocs.io/en/latest/roadmap.html) lists
what comes next.

## Contributing

Issues and pull requests are welcome. To set up a development environment, run
the checks, and build the docs, see
[Contributing](https://sktime-cli.readthedocs.io/en/latest/contributing/index.html).

## License

[BSD 3-Clause](https://github.com/siddharth7113/sktime-cli/blob/main/LICENSE), matching sktime.
