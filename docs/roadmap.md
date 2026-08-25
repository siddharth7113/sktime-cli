# Roadmap

`sktime-cli` is an early alpha. This page records what the current version
covers, where it stops, and what comes next.

## Coverage

sktime's registry holds 697 object registrations across 25 scitypes. Version
0.0.1 dispatched `run` on four of them, about 40% of the registry. Version
0.0.2 dispatches on eight, about 66%.

| scitype | objects | sktime-cli surface |
| --- | ---: | --- |
| forecaster | 156 | `run` (forecasting) |
| transformer | 153 | `run transform` |
| classifier | 78 | `run` (panel) |
| metric | 46 | `--metric`, `metrics score` |
| metric_forecasting | 32 | `--metric`, `metrics score` |
| regressor | 31 | `run` (panel) |
| detector | 28 | `run detect` |
| dataset | 21 | `datasets load` |
| transformer-pairwise-panel | 21 | used inside other estimators |
| param_est | 20 | not yet exposed |
| splitter | 15 | `--cv`, `data split --cv` |
| interval_scorer | 14 | used inside detectors |
| dataset_forecasting | 11 | `datasets load` |
| network | 11 | used inside classifiers and regressors |
| clusterer | 11 | `run` (panel) |
| dataset_classification | 9 | `datasets load` |
| catalogue | 9 | `catalogues list` |
| metric_forecasting_proba | 8 | `--metric`, `metrics score` |
| aligner | 7 | not yet exposed |
| metric_detection | 6 | `--metric`, `metrics score` |
| reconciler | 5 | `run transform` |
| object | 2 | abstract category |
| transformer-pairwise | 1 | used inside other estimators |
| early_classifier | 1 | `run` (panel) |
| dataset_regression | 1 | `datasets load` |

Regenerate this table with `python scripts/scitype_coverage.py`. Every scitype
is classified in `sktime_cli/_scitypes.py`, and `tests/test_scitypes.py` fails
if sktime adds one that is not, so the gap cannot widen unnoticed.

## What version 0.0.2 covers

- Registry search, describe, tags, and types, backed by a disk cache.
- Dataset listing, description, and loading from sktime's dataset objects plus
  the UCR/UEA, Monash, and fpp3 sources.
- Benchmark catalogues.
- Data inspection, format conversion, temporal splitting, and cross-validation
  fold generation.
- Fit, predict, transform, detect, and evaluate across forecasters,
  classifiers, regressors, clusterers, transformers, reconcilers, and
  detectors.
- Probabilistic forecasting: intervals, quantiles, variance, and residuals.
- Long-format and hierarchical file input, including global forecasting.
- Metric listing and scoring.
- API-contract checking with `sktime-cli check`.
- Saved model artifacts with a spec round trip through `model inspect`.
- Environment reporting through `version`, `env`, `doctor`, and `cache`.

There are no sessions, handles, async jobs, or daemons, and adding them isn't
planned. For the reasoning, see [Design](contributing/design.md).

## Known limitations

- `run evaluate` covers forecasters, classifiers, and regressors. sktime has no
  cross-validation utility for clusterers or detectors, so neither does this.
- Aligners, parameter estimators, and pairwise transformers are not exposed by
  `run`. A generic `call` command is the likely route rather than one command
  each.
- `--fh` accepts relative horizons only, so absolute and dated horizons are not
  supported.
- Spec strings naming non-sktime objects fall back to `sktime.registry.craft`,
  which needs `pytest` installed in lean environments. This is an upstream
  issue; see the note in `sktime_cli/_specs.py`.

## Planned for later versions

Model workflows
: `run update` for streaming updates, `run tune` over `ForecastingGridSearchCV`,
  and a generic `call_method` for any estimator method.

Data
: Absolute or dated `--fh` values.

Reproducibility
: A full `export_code` command that emits a runnable Python script for a run.

Ecosystem integration
: The benchmarking module, plotting, an mlflow flavor, and pushing models to
  the Hugging Face Hub.

## Related work

An adversarial agent benchmark suite, covering a foundation tier and a hard
tier with provider-neutral run records and scoring keys, is being developed on
the
[`feat/adversarial-benchmark`](https://github.com/siddharth7113/sktime-cli/tree/feat/adversarial-benchmark)
branch.
