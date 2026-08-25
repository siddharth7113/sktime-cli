# Changelog

All notable changes to `sktime-cli` are recorded here. The project follows
[semantic versioning](https://semver.org/), with the caveat that `0.0.x`
releases may break the command surface while the design settles.

## 0.0.2 (unreleased)

The framework-coverage release. `run` dispatched on 4 of sktime's 25 scitypes
in 0.0.1, reaching about 40% of the registry; it now dispatches on 8, reaching
66%. Run `python scripts/scitype_coverage.py` to regenerate the breakdown.

### Added

- `run transform` and `run fit-transform` for sktime's 153 transformers, with
  `--inverse` for `inverse_transform`, gated on the `capability:inverse_transform`
  tag. Reconcilers subclass `BaseTransformer`, so they are covered too.
- `run detect` for the 28 objects in `sktime.detection`, with
  `--kind points|segments|scores` and an `auto` default read from the
  detector's `task` tag. Interval segments are flattened to `start`/`end`
  columns so they survive a CSV round trip.
- Probabilistic forecasting on `run predict`: `--interval`, `--quantiles`,
  `--var` and `--residuals`. Results are emitted in long form
  (`variable, coverage, bound, value`), whose column count does not change with
  the number of coverages requested; `--wide` keeps sktime's native MultiIndex
  columns, joined with `__`. Forecasters without `capability:pred_int` fail with
  a CLI error naming the tag instead of an sktime traceback.
- `run evaluate` now backtests classifiers and regressors, not only
  forecasters. Panel folds use sklearn splitters, which `--cv` accepts by name.
- `--long`, `--id-col` and `--time-col` on every `run` command. `--id-col`
  takes a comma-separated list; more than one id level yields Hierarchical
  rather than Panel data.
- `sktime-cli check` wraps `sktime.utils.estimator_checks.check_estimator`, so
  a third-party estimator or a crafted spec can be validated against sktime's
  API contract from the command line.
- `sktime-cli metrics list` and `sktime-cli metrics score`, closing the
  predict-then-score loop for the 92 metric objects that were previously
  reachable only inside `run evaluate`.
- `sktime-cli catalogues list` and `catalogues get` for sktime's benchmark
  catalogues (`BakeOffCatalogue`, the M4 competition catalogues).
- `data split --cv` writes one train/test file pair per cross-validation fold
  plus a fold manifest, using any of the registry's 15 splitters.
- `datasets describe --no-load` answers from tag metadata without loading.
- `datasets load` writes panel datasets in formats other than `.ts`, putting
  the labels in a companion `_y` file.
- CI now runs a matrix over sktime versions (the declared floor and the newest
  release) as well as Python versions, plus a non-blocking job that tests
  against sktime `main` and one that turns upstream deprecation warnings into
  failures.

### Changed

- **Breaking.** Builtin dataset ids are now exactly the `name` tags sktime's
  dataset objects declare, rather than a hand-maintained table. Two ids were
  renamed to match upstream: `gunpoint` is now `gun_point`, and
  `hierarchical_sales` is now `hierarchical_sales_toydata`. A near miss
  suggests the correct spelling. `m5_forecasting_accuracy` is newly available,
  and datasets added to sktime appear with no change here.
- `datasets describe` reports the dataset object's tags (`frequency`,
  `n_timepoints`, `is_univariate`, `has_exogenous`, `n_splits`, and more)
  alongside the shape information it already returned.
- `run evaluate` passes `error_score="raise"`, so a fold that fails is an error
  with a code rather than a silent `NaN` column.
- `sktime_cli.__version__` is read from installed package metadata instead of
  being duplicated in the source.
- `--source objects` was removed from `datasets list`; dataset objects are the
  builtin catalogue, so `--source builtin` covers them.
- **Breaking.** `datasets list --task` and the `task` field of `datasets
  describe` use sktime's scitype names (`forecaster`, `classifier`,
  `regressor`) rather than a separate vocabulary (`forecasting`,
  `classification`, `regression`). This matches `registry search` and removes
  a translation table.
- `data inspect` reports every metadata field sktime computes, rather than a
  fixed subset, so a field added upstream appears without a change here. The
  metric and dataset scitype lists, the tags `datasets describe` surfaces, and
  the module that cross-validates a panel estimator are likewise derived from
  sktime rather than listed in this project.
- Docstrings across the source tree follow the numpydoc convention the project
  configures for ruff, with Parameters, Returns and Raises sections on the
  functions that take or return anything non-obvious.

### Fixed

- `run` could not read long-format panel files: `--long` and friends existed on
  `data` but were never threaded through `run`, so the instance id column
  survived as data and sktime failed with
  `Forecasters do not support categorical features in endogeneous y`. The flags
  now work everywhere, and a non-numeric target column is reported as a CLI
  error naming the flags that fix it.
- Global and hierarchical forecasting worked from dataset ids but not from
  files, because file input was classified as a Panel and rejected. sktime
  forecasters accept Panel and Hierarchical `y`, and so does `run` now.
- `run transform`/`run detect` reported a persisted `--model-out` path only when
  `--output` was also given. The path now goes to stderr when the result itself
  is streaming to stdout, keeping stdout a single parseable document.
- Missing soft dependencies were reported as `missing package: None` with the
  hint `uv pip install None`, because sktime's dependency checks raise
  `ModuleNotFoundError` with no `name` set and the requirement stated only in
  the message. The requirement is now read back out of the error, so
  `datasets load fpp3:ansett` says `uv pip install requests`. This affected
  every sktime soft-dependency check, not just datasets, and needs no table of
  which feature requires which package.
- Error messages no longer hardcode `v0.0.1`.
- Missing-dependency errors named every package an estimator declares, not the
  ones actually absent, so the hint told you to install packages you already
  had and contradicted `doctor`. Each requirement is now re-checked.
- `run detect --kind scores` leaked `NotImplementedError` from sktime for
  detectors that do not implement it. It is now a usage error naming the kinds
  that do work.
- A nested `--set` key that does not exist raised a bare `KeyError` with exit 1,
  while a top-level one was correctly a usage error. Both are now usage errors
  listing the valid parameters.
- `registry search` returned an empty list for a tag no object of that scitype
  carries, which reads the same as a genuine no-match. It is now a `not_found`
  error with close matches, which also catches tags that exist but not on the
  scitype being searched.
- `datasets list --task` accepted any value and silently returned nothing.
  It now validates like `--source` does.
- `--format agent` printed no header line at all for an empty result, so a
  script skipping the header would consume its first row of data.
- `run predict --var` labelled its variable column `0` while `--interval` and
  `--quantiles` used the series name. All three now agree.
- Documentation fixes found by running every example: the `scitype:y` tag
  filter (no forecaster carries it), the `--set forecaster__sp` key (steps are
  named after their class), the `StratifiedKFold` backtest example (sktime does
  not pass `y` to the splitter), the `--kind scores` example, the `.npy` output
  claim, the exit-code shell snippet (`$?` after `if ! cmd` is always 0), the
  "an existing file wins" description of `--data`, the probabilistic column
  table (it omitted the time index), the sample error record, the README command
  table, and the version stated in the README and docs index.

## 0.0.1 (2026-08-25)

First release: registry discovery, dataset listing and loading, data
inspection, conversion and splitting, one-shot fit/predict/evaluate for
forecasting and classification, saved model artifacts, and environment
reporting. See [the roadmap](docs/roadmap.md) for the scope of that release.
