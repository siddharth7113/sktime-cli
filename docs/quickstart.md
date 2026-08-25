# Quickstart

This page takes you from an empty shell to a fitted forecaster, a set of
predictions, and a backtest score. Each step is one command, and each command
writes its result to a file or to stdout.

Before you start, install the CLI as described in
[Installation](installation.md).

## Pick an estimator

`registry search` filters sktime's estimator registry. Pass a scitype to
restrict the search, and repeat `-t` to filter on capability tags:

```bash
sktime-cli registry search forecaster -t capability:missing_values=true
```

The first search builds a disk cache of the registry and takes a few seconds.
Later searches read the cache instead.

To read an estimator's parameters, defaults, tags, and dependencies, use
`registry describe`:

```bash
sktime-cli registry describe NaiveForecaster
```

For more ways to narrow a search, see [Finding
estimators](guide/discovery.md).

## Get some data

`datasets load` fetches a dataset and writes it in the format you name:

```bash
sktime-cli datasets load airline --output airline.csv
```

`airline` is one of sktime's built-in datasets, so this works offline. Names
such as `ucr:ArrowHead` and `tsf:m1_yearly_dataset` download from remote
sources into the cache directory.

To check what the CLI makes of a file, use `data inspect`:

```bash
sktime-cli data inspect airline.csv
```

The command reports the scitype, the mtype, the shape, and index details.
When you have a file from somewhere else and aren't sure how sktime reads it,
start here. For the file format conventions, see [Working with
data](guide/data.md).

## Fit a model

Estimators are given as spec strings, which are constructor expressions
written the way you would write them in Python:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --model-out model.zip
```

`--data` accepts a file path or a dataset name. A path is read as a file and a bare name as a dataset, so
`--data airline` also works and loads the built-in dataset directly.

The fitted model is a `.zip` artifact. If you omit `--model-out`, the CLI
writes it into the `models/` directory inside its workspace and prints the
path.

## Predict

`run predict` loads a saved model and forecasts a horizon:

```bash
sktime-cli run predict --model model.zip --fh 1:12
```

`--fh` takes an inclusive range (`1:12`), a list (`1,2,12`), or a single step
(`6`). Horizons are relative to the end of the training data.

To write the forecast to a file instead of stdout, add `--output
forecast.csv`.

To fit and predict in one step, use `run fit-predict`:

```bash
sktime-cli run fit-predict "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --fh 1:12 \
    --output forecast.csv
```

## Score the model

`run evaluate` backtests an estimator over a rolling split and reports
per-fold scores plus an aggregate:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --fh 1:12 \
    --metric MeanAbsolutePercentageError
```

For control over the splitter, pass a `--cv` spec string instead of `--fh`:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])" \
    --metric MeanAbsolutePercentageError
```

For pipelines, ensembles, parameter overrides, and classification workflows,
see [Fitting and evaluating models](guide/modeling.md).

## Get machine-readable output

Add `--json` to any command to get exactly one JSON document on stdout:

```bash
sktime-cli registry describe NaiveForecaster --json | jq '.params.sp.default'
```

Results go to stdout and everything else goes to stderr, so you can always
pipe stdout into another tool. For the other formats and the error contract,
see [Output formats and errors](guide/output.md).

## What to read next

- [Finding estimators](guide/discovery.md) for registry searches and tag
  filters.
- [Working with data](guide/data.md) for file formats, index conventions, and
  splitting.
- [Fitting and evaluating models](guide/modeling.md) for spec strings and the
  `run` commands.
- [Using sktime-cli from an agent](guide/agents.md) for the JSON contract and
  the agent skill file.
- [CLI reference](reference/cli.md) for every command and option.
