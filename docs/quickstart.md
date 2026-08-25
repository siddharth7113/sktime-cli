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

```{code-block} text
:caption: Output

 name                               scitypes        module                              installable
 ARIMA                              ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoARIMA                          ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoETS                            ["forecaster"]  sktime.forecasting.ets              true
 BaggingForecaster                  ["forecaster"]  sktime.forecasting.compose._baggi…  true
 DirRecTabularRegressionForecaster  ["forecaster"]  sktime.forecasting.compose._reduce  true
 ...
29 result(s)
```

`installable` is `false` when an estimator needs a package you don't have.

The first search builds a disk cache of the registry and takes a few seconds.
Later searches read the cache instead.

To read an estimator's parameters, defaults, tags, and dependencies, use
`registry describe`:

```bash
sktime-cli registry describe NaiveForecaster
```

```{code-block} text
:caption: Output

name                 NaiveForecaster
module               sktime.forecasting.naive._naive
scitypes             ["forecaster"]
installable          true
python_dependencies  []
params               {"sp": {"default": "1", "required": false}, "strategy": {"default": "'last'",
                     "required": false}, "window_length": {"default": "None", "required": false}}
tags                 {...}
summary              Forecast based on naive assumptions about past trends continuing.
```

For more ways to narrow a search, see [Finding
estimators](guide/discovery.md).

## Get some data

`datasets load` fetches a dataset and writes it in the format you name:

```bash
sktime-cli datasets load airline --output airline.csv
```

```{code-block} text
:caption: Output

dataset  airline
source   builtin
task     forecaster
shape    [144]
files    ["airline.csv"]
```

`airline` is one of sktime's built-in datasets, so this works offline. Names
such as `ucr:ArrowHead` and `tsf:m1_yearly_dataset` download from remote
sources into the cache directory.

To check what the CLI makes of a file, use `data inspect`:

```bash
sktime-cli data inspect airline.csv
```

```{code-block} text
:caption: Output

path      airline.csv
scitype   Series
mtype     pd.Series
shape     [144]
metadata  {"dtypekind_dfip": [2], "feature_kind": [2], "feature_names": ["Number of airline
          passengers"], "has_nans": false, "is_empty": false, "is_equally_spaced": true,
          "is_univariate": true, "n_features": 1}
index     {"type": "PeriodIndex", "dtype": "period[M]", "start": "1949-01", "end": "1960-12"}
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

```{code-block} text
:caption: Output

model      model.zip
estimator  NaiveForecaster(sp=12)
scitype    forecaster
n_obs      144
cutoff     1960-12
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

```{code-block} text
:caption: Output

 index    Number of airline passengers
 1961-01                         417.0
 1961-02                         391.0
 1961-03                         419.0
 1961-04                         461.0
 1961-05                         472.0
 1961-06                         535.0
 1961-07                         622.0
 1961-08                         606.0
 1961-09                         508.0
 1961-10                         461.0
 1961-11                         390.0
 1961-12                         432.0
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

```{code-block} text
:caption: Output

files  ["forecast.csv"]
n      12
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

```{code-block} text
:caption: Output

 index  test_MeanAbsoluteP…              fit_time            pred_time  len_train_window     cutoff
 0      0.15666934262154927  0.00151077800001075…  0.0115759139989677…                72  "1954-12"
 ...
 60     0.09987532920823484  0.00130832399918290…  0.0097127629996975…               132  "1959-12"
test_MeanAbsolutePercentageError.mean  0.104007700568499
test_MeanAbsolutePercentageError.std   0.036494730005964454
```

For control over the splitter, pass a `--cv` spec string instead of `--fh`:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])" \
    --metric MeanAbsolutePercentageError
```

```{code-block} text
:caption: Output

 index  test_MeanAbsoluteP…              fit_time            pred_time  len_train_window     cutoff
 0      0.15666934262154927  0.00151077800001075…  0.0115759139989677…                72  "1954-12"
 1      0.15482026530374263  0.001348194000456715  0.0098441819991421…                84  "1955-12"
 2      0.09589915982651807  0.00131347400019876…  0.0099034260001644…                96  "1956-12"
 3      0.0478543722989734…  0.00130262200036668…  0.0101766749994567…               108  "1957-12"
 4      0.07803512612949999  0.00139050799953110…  0.0099195889997645…               120  "1958-12"
 5      0.09767886451997902  0.00129603200002748…  0.0094878910003899…               132  "1959-12"
test_MeanAbsolutePercentageError.mean  0.10515952178337706
test_MeanAbsolutePercentageError.std   0.04308312575349776
```

Six folds instead of 61: the default splitter advances one observation at a
time, and `step_length=12` advances a year.

For pipelines, ensembles, parameter overrides, and classification workflows,
see [Fitting and evaluating models](guide/modeling.md).

## Get machine-readable output

Add `--json` to any command to get exactly one JSON document on stdout:

```bash
sktime-cli registry describe NaiveForecaster --json | jq '.params.sp.default'
```

```{code-block} text
:caption: Output

"1"
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
- [CLI reference](reference/cli/index.md) for every command and option.
