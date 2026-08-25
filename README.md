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

## Why sktime-cli

Every command is one process. It reads files or names, calls sktime, writes
results, and exits with a meaningful code. No state is hidden in a session, so
the same command behaves the same way in a shell, a Makefile, a CI job, or an
AI agent.

- **Stateless commands.** No sessions, handles, daemons, or background jobs.
  Fitted models are `.zip` files you can see with `ls`, and the rest of the
  state lives under one cache directory, the same model the Hugging Face CLI
  uses.
- **Registry-native discovery.** `registry search` filters sktime's full
  estimator registry by scitype and capability tag, served from a disk cache,
  so repeat searches don't pay for the crawl again.
- **Estimators named the way you write them.** Models are constructor
  expressions: `"NaiveForecaster(sp=12)"`, with pipelines via `*`, ensembles
  via `+`, and multiplexers via `|`.
- **Many formats in, many formats out.** csv, parquet, json, `.ts`, `.tsf`,
  and `.arff` go in. Every command reads
  `--format human|agent|json|quiet` on the way out.
- **Errors that name the fix.** One JSON document on stdout, structured errors
  on stderr, stable exit codes, and a
  [ready-to-use agent skill](https://github.com/siddharth7113/sktime-cli/blob/main/skills/sktime-cli/SKILL.md).

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

For a longer walkthrough, see the
[quickstart](https://sktime-cli.readthedocs.io/en/latest/quickstart.html).

## Commands

| Group | Commands | What it does |
|---|---|---|
| `registry` | `search` · `describe` · `tags` · `types` | Find sktime estimators by scitype, name, and capability tag |
| `datasets` | `list` · `describe` · `load` | Browse and fetch built-in, UCR/UEA, Monash, and fpp3 datasets |
| `data` | `inspect` · `convert` · `split` | Detect mtypes and scitypes, convert formats, split temporally |
| `run` | `fit` · `predict` · `fit-predict` · `evaluate` | One-shot workflows for forecasting and classification |
| `model` | `inspect` | Look inside a saved model artifact and round-trip its spec |
| *(top level)* | `version` · `env` · `doctor` · `cache` | Environment info, health check, workspace management |

Every option is listed in the
[CLI reference](https://sktime-cli.readthedocs.io/en/latest/reference/cli.html),
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

The full agent contract and task recipes live in
[skills/sktime-cli/SKILL.md](https://github.com/siddharth7113/sktime-cli/blob/main/skills/sktime-cli/SKILL.md). Copy the `skills/`
directory into your agent's skill directory, such as `.claude/skills/`, and
the agent knows how to drive the CLI. The same file ships inside the wheel.

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
- [CLI reference](https://sktime-cli.readthedocs.io/en/latest/reference/cli.html)
- [Architecture](https://sktime-cli.readthedocs.io/en/latest/contributing/architecture.html)
  and [design decisions](https://sktime-cli.readthedocs.io/en/latest/contributing/design.html)

## Status

`sktime-cli` is an independent, unofficial command-line client for sktime. It
is not maintained by or affiliated with the sktime project.

Version 0.0.1 is an early alpha release. Discovery and one-shot runs work, and
the [roadmap](https://sktime-cli.readthedocs.io/en/latest/roadmap.html) lists
what comes next.

## Contributing

Issues and pull requests are welcome. To set up a development environment, run
the checks, and build the docs, see
[Contributing](https://sktime-cli.readthedocs.io/en/latest/contributing/index.html).

## License

[BSD 3-Clause](https://github.com/siddharth7113/sktime-cli/blob/main/LICENSE), matching sktime.
