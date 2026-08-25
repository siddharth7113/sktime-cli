# Scoring, checking, and benchmark catalogues

Three commands sit alongside the modelling ones. `metrics` scores predictions
you already have, `check` tells you whether an object satisfies sktime's API,
and `catalogues` lists the benchmark setups sktime ships.

## Score predictions you already have

`run evaluate` scores an estimator by backtesting it. `metrics score` does the
other thing: it takes two files and compares them, so you can score a forecast
that was produced separately, or one that did not come from sktime at all.

```bash
sktime-cli data split airline.csv --test-size 12
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline_train.csv --model-out m.zip
sktime-cli run predict --model m.zip --fh 1:12 --output pred.csv

sktime-cli metrics score --true airline_test.csv --pred pred.csv \
    --metric MeanAbsolutePercentageError \
    --metric MeanAbsoluteError
```

The output is one field per metric:

```json
{"MeanAbsolutePercentageError": 0.0998, "MeanAbsoluteError": 47.83}
```

`--metric` is repeatable and takes either a name or a spec string, so a metric
can be parameterized the same way an estimator is:
`--metric "MeanAbsolutePercentageError(symmetric=True)"`. The default is
`MeanAbsolutePercentageError`.

The two files must cover the same periods. Comparing a forecast against the
wrong stretch of history is a `data_error`, not a number, even when the two
files happen to have the same number of rows.

Some metrics score against the training data as well. Those declare it in their
tags, and the command asks for it rather than failing:

```bash
sktime-cli metrics score --true airline_test.csv --pred pred.csv \
    --metric MeanAbsoluteScaledError \
    --train airline_train.csv
```

### Finding a metric

```bash
sktime-cli metrics list --json
sktime-cli metrics list metric_forecasting -n Absolute
```

Each row reports `lower_is_better`, which is what tells you the direction to
optimize. These are sktime's metric objects, so they are for forecasting.
Classification and regression are scored per instance, and `run evaluate` takes
`sklearn.metrics` names for those, such as `accuracy_score`.

## Check an object against sktime's API

`check` runs the same contract suite sktime runs against its own estimators:

```bash
sktime-cli check "NaiveForecaster(sp=12)"
```

```
test                                    status  detail
test_constructor[NaiveForecaster]       pass
test_fit_idempotent[NaiveForecaster-0]  pass
...
total    379
passed   379
failed   0
```

The exit code is `1` when any check fails, so this works in CI. Use
`--failed-only` to see just the failures, and `--tests` or `--exclude` to narrow
the run to particular test names:

```bash
sktime-cli check "MyForecaster()" --failed-only --json
sktime-cli check "NaiveForecaster()" --tests test_constructor,test_get_params
```

Two things this is good for. If you have written your own estimator, it tells
you whether it really satisfies the interface before you rely on it. And if you
have composed a spec string, it confirms the result is a well-formed sktime
object before you spend time running it.

A `--tests` filter that matches nothing is an error rather than a silent pass,
so a typo cannot look like success.

## Browse benchmark catalogues

A catalogue bundles the datasets, estimators, metrics and splitters that make up
a published benchmark, so a comparison can be reproduced without transcribing
the setup by hand.

```bash
sktime-cli catalogues list
sktime-cli catalogues get M4CompetitionCatalogueYearly
```

`get` returns the entries as spec strings, which is what makes them useful: each
one can be passed straight back to `run` or to `--cv`.

```bash
sktime-cli catalogues get DummyForecastingCatalogue --json
```

```json
{
  "name": "DummyForecastingCatalogue",
  "categories": ["dataset", "forecaster", "metric", "cv_splitter"],
  "entries": ["Airline", "NaiveForecaster(strategy='last')",
              "MeanAbsoluteError()", "MeanAbsolutePercentageError()",
              "ExpandingWindowSplitter(initial_window=12, step_length=6, fh=6)"]
}
```

`--type` narrows the result to one category, which is how you pull just the
splitter or just the metrics out of a benchmark definition.

## What to read next

- [Fitting and evaluating models](modeling.md) for the estimators these score.
- [Output formats and errors](output.md) for the exit codes `check` uses.
