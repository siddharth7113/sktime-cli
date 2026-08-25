---
name: sktime-cli
description: >
  Run time series machine learning from the shell with sktime-cli: discover
  forecasters/classifiers in sktime's registry, fetch datasets, inspect and
  split series files, fit/predict/evaluate models, and manage saved model
  artifacts. Use for any forecasting, time series classification, regression,
  or backtesting task when working from a terminal.
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
  `+` (ensemble), `|` (multiplexer): `"Deseasonalizer() * NaiveForecaster()"`.
  Override params with repeatable `--set key=value` (`__` reaches nested
  components, e.g. `--set forecaster__sp=4`).
- `SKTIME_CLI_HOME` (default `~/.cache/sktime-cli`) holds the registry cache,
  dataset downloads, and default model output. Health check: `sktime-cli doctor`.

## Task: discover what to use

```bash
sktime-cli registry types --json                  # 25 object categories
sktime-cli registry search forecaster --json      # all forecasters
# filter by capability tags (AND across -t, comma = OR):
sktime-cli registry search forecaster -t capability:missing_values=true \
  -t "scitype:y=univariate,both" --installable-only --json
sktime-cli registry tags forecaster --json        # all filterable tags
sktime-cli registry describe NaiveForecaster --json   # params, tags, deps
```

`--installable-only` keeps estimators whose soft deps are installed; without
it, `installable: false` rows tell you what `uv pip install` would unlock.

## Task: get data

```bash
sktime-cli datasets list --source builtin --json          # offline datasets
sktime-cli datasets list --task classification -n arrow --json
sktime-cli datasets load airline --output airline.csv --json
sktime-cli datasets load ucr:ArrowHead --output arrow.ts --json   # downloads
sktime-cli data inspect airline.csv --json                # scitype/mtype/NaNs
```

Own data conventions: wide CSV = first column is the time index (override
`--index-col`, force frequency with `--freq M`); a single value column becomes
a univariate series. Panels (classification) use `.ts` files. Long panel CSV:
`--long --id-col <instance> --time-col <time>`. JSON files use pandas "split"
orient. Convert between them with `sktime-cli data convert`.

## Task: forecasting end-to-end

```bash
# hold out the last 12 points for honest evaluation
sktime-cli data split airline.csv --test-size 12 --json

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

Panel data must be `.ts` files (or a named classification dataset). Regressors
and clusterers work the same way (`registry search regressor|clusterer`).

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
