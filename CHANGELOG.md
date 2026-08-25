# Changelog

All notable changes to `sktime-cli` are recorded here. The project follows
[semantic versioning](https://semver.org/), with the caveat that `0.0.x`
releases may break the command surface while the design settles.

## Unreleased

### Fixed

- `uv sync` in a clone of this repository installed sktime as an editable
  install from a sibling `../sktime` checkout, because a maintainer-only
  `[tool.uv.sources]` table was committed to `pyproject.toml` and baked into
  `uv.lock`. Contributors with a local sktime clone silently developed against
  whatever was in it, and contributors without one could not sync at all.
  sktime now resolves from PyPI like any other dependency, and the
  `--no-sources` workarounds in CI and on Read the Docs are gone. To test
  against unreleased sktime, install it over the synced environment; see
  [Contributing](docs/contributing/index.md).
- Errors raised inside sktime were reported as `internal` CLI bugs, rather
  than `sktime_error`, whenever sktime-cli was installed under a directory
  named `sktime_cli`. Attribution walked the traceback for the substring
  `"sktime"` in a frame's path while excluding `"sktime_cli"`, and a
  virtualenv below such a directory puts that name in front of every sktime
  frame. Attribution now tests containment in sktime's real package
  directory. CI could not catch this, because GitHub checks the repository
  out to `sktime-cli`, with a hyphen.

## 0.0.2 (2026-08-25)

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
- A user guide page for `metrics`, `check` and `catalogues`, which had no guide
  coverage beyond the generated CLI reference.
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
- The agent skill moved from `skills/sktime-cli/SKILL.md` into the package, at
  `src/sktime_cli/.agents/skills/sktime-cli/SKILL.md`, which is the path
  libraries use to bundle [agent skills](https://agentskills.io). Installing
  `sktime-cli` now installs the skill with it, and
  `uvx library-skills --claude` links it into `.claude/skills/` without a
  checkout. The wheel no longer force-includes it at `sktime_cli/SKILL.md`.

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
- Writing a nested panel to csv, parquet or json produced cells holding the
  *text* of a pandas Series, at exit 0, so `data convert file.ts -o out.csv`
  silently destroyed the data. It is now a usage error naming the conversion
  that works, and `datasets load --file-format csv` performs that conversion
  itself. MultiIndex levels are also named on write, so the result can be read
  back with `--long`.
- Click's own usage errors, such as an unknown option or a missing argument,
  printed styled text even under `--json`, because they are raised before the
  command runs and never reached the error handler. They now follow the same
  contract as every other failure.
- An explicit `--format human` was ignored when deciding how to render an
  error, so redirecting human output to a file produced JSON errors.
- **Every builtin classification dataset was unusable with `run`.** sktime
  returns them as `nested_univ` panels, which have a flat index, and the input
  layer classified scitype by counting index levels, so `run fit
  "DummyClassifier()" --data arrow_head` was rejected as "a single series".
  The scitype now comes from sktime rather than from the index shape.
- `metrics score` compared positionally whenever the two files had the same
  number of rows, so scoring a 1949 series against a 1961 forecast returned a
  plausible number at exit 0. The periods must now overlap.
- `--long` guessed the id and time columns when they were not named, which
  turned a value column into the instance id and produced one instance per row.
  Both flags are now required, as the help always said.
- A probabilistic flag aimed at the wrong kind of estimator was silently
  ignored: `--interval` on a classifier returned point labels at exit 0, and
  `--proba` on a forecaster returned a point forecast. Both are now errors.
- `run detect --kind points` crashed on segmenters with an `AttributeError`,
  and the error for `--kind scores` recommended exactly that command.
- `model inspect --spec --json` printed a bare string, breaking the promise of
  one JSON document. It is now `{"spec": "..."}` under `--json` and stays bare
  in every other format, so `spec=$(... --spec)` still works.
- `model inspect` on a file that exists but is not an artifact reported a
  `.zip` path the user never typed.
- An empty or malformed CSV was reported as `internal` at exit 1 rather than
  `data_error` at exit 5.
- Writing a single series to `.ts` leaked a raw sktime `TypeError`; `.ts` holds
  panels, and now says so.
- `data split` accepted a test size larger than the series, and negative sizes,
  writing an empty train file at exit 0.
- `registry search --limit 0` returned every row and a negative limit returned
  one; both are now usage errors.
- `run evaluate` on a classifier accepted an sktime forecasting metric and
  crashed inside sktime. Panel metrics come from `sklearn.metrics`, and the
  error now says so.
- `check --tests` with a name that matches nothing reported a clean pass.
- `data split --exog` with a non-overlapping index dumped a raw pandas
  `KeyError`.
- `run transform` and `run detect` said "not both" when the user had passed
  neither a spec nor `--model`.
- `run fit-predict` silently ignored `--fh` when given a transformer.
- `registry describe` gave no close-match suggestion for an unknown name, while
  `datasets describe` did.
- The usage-error handler imported `typer._click`, which typer only vendors
  from 0.26, while the declared floor is `typer>=0.12`. On an older typer every
  invocation, including `--version`, died at import. The import is now optional;
  the renderer that typer actually calls has existed far longer.
- `datasets load` ignored `--file-format` and the output suffix for datasets
  with a MultiIndex, always writing CSV, so `-o out.json --file-format json`
  reported success and wrote CSV into a `.json` file.
- Panel and Hierarchical data written as JSON could not be read back: the
  MultiIndex was serialized as nested lists and rebuilt as a flat index, and the
  single-column case was squeezed to a Series, which is not a valid Panel mtype.
  All three scitypes now round-trip.
- `metrics score` keyed results by the metric's bare name, so
  `--metric X --metric "X(param=1)"` reported only one of the two scores.
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
