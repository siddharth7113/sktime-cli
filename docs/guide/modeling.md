# Fitting and evaluating models

The `run` command group covers the whole modeling loop: fit an estimator,
save it, predict from it, and backtest it. Estimators are named with spec
strings, which is the one piece of syntax the CLI adds.

## Spec strings

A spec string is a constructor expression written the way you would write it
in Python:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --model-out model.zip
```

Compositions use sktime's own operators, so a spec can build a pipeline or a
multiplexer without any extra syntax:

```bash
# pipeline: deseasonalize, then forecast
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" --data airline

# multiplexer: switch between components
sktime-cli run fit "NaiveForecaster() | ThetaForecaster()" --data airline

# union: combine two transformers into one feature set
sktime-cli run fit "(Detrender() + Deseasonalizer()) * NaiveForecaster()" \
    --data airline
```

`+` unions transformers; forecasters don't define it. Ensembles are a class
rather than an operator, and a class name is just as usable in a spec:

```bash
sktime-cli run evaluate \
    "EnsembleForecaster([('ets', AutoETS()), ('naive', NaiveForecaster())])" \
    --data airline --fh 1:12
```

Names are resolved against the cached registry, so anything `registry search`
finds is usable in a spec. Only the modules you actually name get imported. If
an estimator's dependencies are missing, the command exits with code `3` and a
hint naming the install command.

Specs are evaluated in a namespace that holds only the resolved sktime classes
and a small set of safe builtins. Imports, attribute access, and file access
don't work inside a spec. For the details, see
[Design](../contributing/design.md).

### Override parameters

`--set key=value` applies overrides through scikit-learn's `set_params`, so
the `__` convention reaches nested components. The flag is repeatable:

```bash
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" \
    --data airline \
    --set NaiveForecaster__sp=4 \
    --set forecaster__strategy=mean
```

Use `--set` when you want to sweep one parameter without rewriting the spec.

## Fit a model

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --model-out model.zip
```

`--data` takes a file path or a dataset name. A path is read as a file and a
local `airline.csv` shadows the built-in `airline` dataset.

The other input options match the ones in [Working with data](data.md):
`--target COL` picks the target from a multi-column file, `--exog PATH` adds
exogenous data, and `--index-col` and `--freq` control indexing.

`run fit` dispatches by scitype. Forecasters are fitted as `fit(y, X, fh)`,
so passing `--fh` at fit time is meaningful for estimators that need the
horizon up front. Panel scitypes, meaning classifiers, regressors, and
clusterers, are fitted as `fit(X, y)`.

If you omit `--model-out`, the model goes to the `models/` directory in the
workspace and the CLI prints the path.

## Predict

```bash
sktime-cli run predict --model model.zip --fh 1:12
```

`--fh` accepts `1:12`, `1,2,12`, or `6`, always relative to the end of
training. For panel models, pass the data to predict on with `--data`. For
forecasters, `--data` supplies exogenous values instead.

`--proba` returns class probabilities for classifiers. `--output PATH` writes
the predictions to a file instead of stdout, in the format the suffix names.

### Uncertainty around a forecast

Four flags turn a point forecast into a probabilistic one:

```bash
sktime-cli run predict --model model.zip --fh 1:12 --interval 0.8,0.95
sktime-cli run predict --model model.zip --fh 1:12 --quantiles 0.1,0.9
sktime-cli run predict --model model.zip --fh 1:12 --var
sktime-cli run predict --model model.zip --data airline.csv --residuals
```

They are mutually exclusive. sktime returns intervals and quantiles with
MultiIndex columns, whose shape changes with the number of levels you ask for.
The CLI flattens them to long form instead, so the columns are fixed:

| flag | columns |
| --- | --- |
| `--interval` | `time`, `variable`, `coverage`, `bound`, `value` |
| `--quantiles` | `time`, `variable`, `quantile`, `value` |
| `--var` | `time`, `variable`, `value` |

The first column is the time index, named `time` when the input had no index
name. For panel input it is the index levels instead.

Asking for three coverages instead of one adds rows, never columns, which is
what makes the output safe to parse. Pass `--wide` if you want sktime's native
layout instead, with the column levels joined by `__`.

Not every forecaster can do this. The ones that can carry the
`capability:pred_int` tag, and the others fail with a usage error that names
it:

```bash
sktime-cli registry search forecaster -t capability:pred_int=True --installable-only
```

To do both steps in one process, use `run fit-predict`. It takes the fit
options plus `--output`, and forecasters require `--fh`:

```bash
sktime-cli run fit-predict "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --fh 1:12 \
    --output forecast.csv
```

## Transform data

Transformers are the largest family in sktime. `run transform` fits one and
applies it in a single step:

```bash
sktime-cli run transform "Detrender()" --data airline.csv --output detrended.csv
```

Pass `--model-out` to keep the fitted transformer, then reuse it on new data
with `--model` instead of a spec. That distinction matters: refitting a
transformer on new data would learn new parameters, while reloading applies
the ones learned before.

```bash
sktime-cli run transform "Differencer()" --data train.csv --model-out diff.zip -o out.csv
sktime-cli run transform --model diff.zip --data test.csv -o test_diff.csv
sktime-cli run transform --model diff.zip --data test_diff.csv --inverse
```

`--inverse` calls `inverse_transform`, which needs the
`capability:inverse_transform` tag; transformers without it fail with a usage
error rather than an sktime traceback.

Reconcilers are transformers in sktime's class hierarchy, so hierarchical
reconciliation runs through this command too.

## Detect anomalies, change points, and segments

```bash
sktime-cli run detect "HampelDetector()" --data series.csv
sktime-cli run detect "ClusterSegmenter()" --data series.csv --kind segments
```

`--kind` defaults to `auto`, which reads the detector's `task` tag and picks
`predict_points` for anomaly and change point detectors, `predict_segments`
for segmenters. Detectors that return segments as intervals are flattened to
`start` and `end` columns so the result survives a CSV round trip.

Discover what is available, and what each one does, with the `task` tag:

```bash
sktime-cli registry search detector --with-tags task --installable-only
```

## Backtest with run evaluate

`run evaluate` scores an estimator over a rolling split. The simple form
derives the splitter from a horizon:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline \
    --fh 1:12 \
    --metric MeanAbsolutePercentageError
```

Add `--initial-window N` to set how much data the first fold trains on.

For full control, pass a splitter as a spec string with `--cv`:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline \
    --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])" \
    --metric MeanAbsolutePercentageError
```

`--cv` and `--fh` are alternatives, so pass one or the other.

`--metric` is repeatable and takes either a metric name or a spec string, so
you can parameterize a metric the same way you parameterize an estimator. The
default is `MeanAbsolutePercentageError`.

`--strategy` takes `refit`, `update`, or `no-update_params`, and controls what
happens to the model between folds.

The output has one row per fold plus an aggregate block:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline --fh 1:12 --json \
    | jq '.aggregate'
```

The aggregate holds a `mean` and `std` for each metric, keyed as
`test_<Metric>`.

### Backtesting a classifier

`run evaluate` also cross-validates classifiers and regressors. Panel folds are
drawn across instances rather than across time, so the splitters that fit are
sklearn's, and `--cv` accepts them by name:

```bash
sktime-cli run evaluate "DummyClassifier()" \
    --data train.ts \
    --cv "KFold(n_splits=5)" \
    --metric accuracy_score
```

Without `--cv` the default is 3-fold cross-validation. `--metric` here takes
the name of an `sklearn.metrics` function, falling back to sktime's registry.
A fold that fails is reported as an error rather than a `NaN` score, so a
metric that needs extra arguments tells you so instead of quietly producing an
empty column.

:::{note}
sktime has no cross-validation utility for clusterers or detectors, so
`run evaluate` does not cover them.
:::

## Inspect a saved model

`model inspect` opens a `.zip` artifact and reports its class, spec, params,
and tags:

```bash
sktime-cli model inspect model.zip
```

`--fitted` adds the fitted parameters. `--spec` prints only the spec string,
and that output is itself a valid spec for `run fit`:

```bash
spec=$(sktime-cli model inspect model.zip --spec)
sktime-cli run fit "$spec" --data airline.csv --model-out refit.zip
```

That round trip is the reproducibility loop: a saved model can always tell you
the command that would rebuild it.

## What to read next

- [Output formats and errors](output.md) for the JSON contract and exit codes.
- [CLI reference](../reference/cli.md) for every `run` and `model` option.
- [Roadmap](../roadmap.md) for the workflows that aren't covered yet.
