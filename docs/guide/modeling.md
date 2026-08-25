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

Compositions use sktime's own operators, so a spec can build a pipeline, an
ensemble, or a multiplexer without any extra syntax:

```bash
# pipeline: deseasonalize, then forecast
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" --data airline

# ensemble: average two forecasters
sktime-cli run evaluate "AutoETS() + NaiveForecaster()" --data airline --fh 1:12

# multiplexer: switch between components
sktime-cli run fit "NaiveForecaster() | ThetaForecaster()" --data airline
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
    --set forecaster__sp=4 \
    --set forecaster__strategy=mean
```

Use `--set` when you want to sweep one parameter without rewriting the spec.

## Fit a model

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --model-out model.zip
```

`--data` takes a file path or a dataset name. An existing file wins, so a
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

To do both steps in one process, use `run fit-predict`. It takes the fit
options plus `--output`, and forecasters require `--fh`:

```bash
sktime-cli run fit-predict "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --fh 1:12 \
    --output forecast.csv
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

:::{note}
In version 0.0.1, `run evaluate` supports forecasters only.
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
