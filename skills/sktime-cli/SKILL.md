---
name: sktime-cli
description: >
  Run time series machine learning from the shell with sktime-cli: discover
  estimators in sktime's registry, fetch datasets, inspect and split series
  files, fit/predict/transform/detect/evaluate models, score predictions, and
  manage saved model artifacts. Use for any forecasting, time series
  classification, regression, transformation, anomaly or change point
  detection, or backtesting task when working from a terminal.
---

# sktime-cli: time series ML from the shell

`sktime-cli` is a stateless CLI over [sktime](https://github.com/sktime/sktime).
Every command reads files/names, calls sktime, writes results, and exits.
Fitted models are `.zip` artifacts on disk; there is no session state.

## Contract (read this first)

- Always pass `--json`: exactly one JSON document on stdout, nothing else.
  Logs and warnings go to stderr. `--format agent` gives TSV instead.
- Errors are JSON on **stderr**:
  `{"error": {"code", "message", "hint", "command"}}`. Follow the `hint`,
  it usually contains the exact fix (often an install command).
- Exit codes: `0` ok · `1` library error · `2` usage · `3` missing
  dependency · `4` not found · `5` bad data/spec.
- Estimators are given as **spec strings**, which are Python-like constructor
  expressions using sktime class names:
  `"NaiveForecaster(sp=12)"`, compositions with `*` (pipeline),
  `|` (multiplexer), `+` (transformer union): `"Deseasonalizer() * NaiveForecaster()"`.
  Forecaster ensembles are a class, not an operator:
  `"EnsembleForecaster([('a', AutoETS()), ('b', NaiveForecaster())])"`.
  Override params with repeatable `--set key=value` (`__` reaches nested
  components, named after the class, e.g. `--set NaiveForecaster__sp=4`).
- `SKTIME_CLI_HOME` (default `~/.cache/sktime-cli`) holds the registry cache,
  dataset downloads, and default model output. Health check: `sktime-cli doctor`.

## Task: discover what to use

```bash
sktime-cli registry types --json                  # 25 object categories
sktime-cli registry search forecaster --json      # all forecasters
# filter by capability tags (AND across -t, comma = OR):
sktime-cli registry search forecaster -t capability:missing_values=true \
  -t capability:insample=true --installable-only --json
sktime-cli registry tags forecaster --json        # all filterable tags
sktime-cli registry describe NaiveForecaster --json   # params, tags, deps
```

`--installable-only` keeps estimators whose soft deps are installed; without
it, `installable: false` rows tell you what `uv pip install` would unlock.

## Task: get data

```bash
sktime-cli datasets list --source builtin --json          # offline datasets
sktime-cli datasets list --task classifier -n arrow --json
sktime-cli datasets describe airline --no-load --json     # shape/frequency from tags
sktime-cli datasets load airline --output airline.csv --json
sktime-cli datasets load ucr:ArrowHead --output arrow.ts --json   # downloads
sktime-cli data inspect airline.csv --json                # scitype/mtype/NaNs
```

Builtin dataset ids are sktime's own names (`gun_point`, `arrow_head`,
`hierarchical_sales_toydata`); a near miss is reported with a suggestion.
`datasets describe --no-load` answers from tags without reading the data.

Own data conventions: wide CSV = first column is the time index (override
`--index-col`, force frequency with `--freq M`); a single value column becomes
a univariate series. Panels (classification) use `.ts` files. Long panel CSV:
`--long --id-col <instance> --time-col <time>`. JSON files use pandas "split"
orient. Convert between them with `sktime-cli data convert`.

## Task: forecasting end-to-end

```bash
# hold out the last 12 points for honest evaluation
sktime-cli data split airline.csv --test-size 12 --json
# or write one file pair per cross-validation fold:
sktime-cli data split airline.csv \
  --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])" --json

# fit on train, save the model artifact
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline_train.csv \
  --model-out model.zip --json

# forecast 12 steps ahead: {"index": [...], "columns": [...], "data": [[...]]}
sktime-cli run predict --model model.zip --fh 1:12 --json

# or one process, no artifact:
sktime-cli run fit-predict "NaiveForecaster(sp=12)" --data airline.csv \
  --fh 1:12 --json
```

`--fh` grammar: `1:12` (inclusive range), `1,2,12`, or `6`. Exogenous data:
`--exog X.csv` at fit and predict time. Multi-column files: `--target <col>`
picks y, remaining columns become X.

## Task: uncertainty around a forecast

```bash
sktime-cli run predict --model model.zip --fh 1:12 --interval 0.8,0.95 --json
sktime-cli run predict --model model.zip --fh 1:12 --quantiles 0.1,0.9 --json
sktime-cli run predict --model model.zip --fh 1:12 --var --json
sktime-cli run predict --model model.zip --data airline.csv --residuals --json
```

Results are **long form**: `--interval` gives columns
`variable, coverage, bound, value` and `--quantiles` gives
`variable, quantile, value`, so the column count never changes with the number
of levels requested. Add `--wide` for sktime's native columns joined with `__`.
Not every forecaster supports this; exit 2 names the missing tag. Find ones
that do:

```bash
sktime-cli registry search forecaster -t capability:pred_int=True --json
```

## Task: transform a series

```bash
sktime-cli run transform "Detrender()" --data airline.csv -o detrended.csv --json
sktime-cli run transform "Differencer()" --data airline.csv \
  --model-out diff.zip -o out.csv --json        # persist the fitted transformer
sktime-cli run transform --model diff.zip --data airline.csv --inverse --json
```

`--inverse` needs `capability:inverse_transform`; exit 2 says so and shows the
search that finds transformers which have it.

## Task: detect anomalies, change points, or segments

```bash
sktime-cli run detect "HampelDetector()" --data series.csv --json
sktime-cli run detect "CAPA()" --data series.csv --kind segments --json
```

`--kind auto` (the default) reads the detector's `task` tag. Segment results
are flattened to `start`/`end` columns. Discover detectors with
`registry search detector --with-tags task --json`.

## Task: score predictions you already have

```bash
sktime-cli metrics list metric_forecasting --json
sktime-cli metrics score --true test.csv --pred pred.csv \
  --metric MeanAbsolutePercentageError --metric MeanAbsoluteError --json
# metrics scored against the training series need it explicitly:
sktime-cli metrics score --true test.csv --pred pred.csv \
  --metric MeanAbsoluteScaledError --train train.csv --json
```

## Task: check an estimator against sktime's API

```bash
sktime-cli check "NaiveForecaster(sp=12)" --json          # full contract suite
sktime-cli check "MyForecaster()" --failed-only --json    # only what breaks
```

Exit 1 when any check fails. Use it to validate a third-party estimator, or to
confirm a composed spec is a well-formed sktime object before running it.

## Task: backtest / compare forecasters

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline.csv \
  --fh 1:12 --initial-window 72 --json
# full control + several metrics:
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline.csv \
  --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3,4,5,6,7,8,9,10,11,12])" \
  --metric MeanAbsolutePercentageError --metric MeanAbsoluteError --json
```

Output: `{"folds": [...], "aggregate": {"test_<Metric>": {"mean", "std"}}}`.
Run it once per candidate spec and compare aggregates. Splitters and metrics
are discoverable: `registry search splitter`, `registry search metric_forecasting`.

## Task: time series classification / regression

```bash
sktime-cli datasets load unit_test --output train.ts --json   # or your own .ts
sktime-cli run fit "DummyClassifier()" --data train.ts --model-out clf.zip --json
sktime-cli run predict --model clf.zip --data test.ts --json
sktime-cli run predict --model clf.zip --data test.ts --proba --json  # per-class probs
```

Panel data comes from `.ts` files, a named classification dataset, or a
long-format file read with `--long --id-col <instance> --time-col <time>`.
Regressors and clusterers work the same way
(`registry search regressor|clusterer`). Cross-validate a classifier with
`run evaluate`, which uses sklearn splitters for panel folds:

```bash
sktime-cli run evaluate "DummyClassifier()" --data train.ts \
  --cv "KFold(n_splits=5)" --metric accuracy_score --json
```

## Task: work with saved models

```bash
sktime-cli model inspect model.zip --json      # class, params, tags, cutoff
sktime-cli model inspect model.zip --spec      # prints the spec string only
sktime-cli model inspect model.zip --fitted --json   # learned parameters
```

`--spec` output is a valid spec for `run fit`, which closes the reproducibility loop.

## Troubleshooting

- exit 3 → a soft dependency is missing; the `hint` has the install command.
- exit 4 with a dataset/estimator → check the `hint` for close-match
  suggestions, or search: `registry search -n <part>`, `datasets list -n <part>`.
- Slow first registry call builds a cache; later calls are fast.
  `--no-cache` forces a live crawl; `sktime-cli cache clear` resets.
- `sktime-cli env --json` reports every dependency version for bug reports.
