# Roadmap

`sktime-cli` 0.0.1 is an early alpha release. This page records what the
current version covers, where it stops, and what comes next.

## What version 0.0.1 covers

The scope of the first release is discovery plus one-shot runs:

- Registry search, describe, tags, and types, backed by a disk cache.
- Dataset listing, description, and loading from the built-in, UCR/UEA,
  Monash, and fpp3 sources.
- Data inspection, format conversion, and temporal splitting.
- Fit, predict, fit-predict, and evaluate for forecasting, and fit,
  predict, and fit-predict for classification.
- Saved model artifacts with a spec round trip through `model inspect`.
- Environment reporting through `version`, `env`, `doctor`, and `cache`.

There are no sessions, handles, async jobs, or daemons, and adding them isn't
planned. For the reasoning, see [Design](contributing/design.md).

## Known limitations

- `run evaluate` supports forecasters only.
- `datasets load` writes panel data as `.ts` only.
- `predict_interval` and `predict_quantiles` are not exposed. They need a
  stable flattening schema for MultiIndex columns first.
- `--fh` accepts relative horizons only, so absolute and dated horizons are
  not supported.

## Planned for later versions

The following items are deferred, in no particular order:

Data and transforms
: A `data transform` command, and absolute or dated `--fh` values.

Model workflows
: `run update` for streaming updates, `call_method` for arbitrary estimator
  methods, and a `check_estimator` smoke command.

Probabilistic forecasting
: `predict_interval` and `predict_quantiles`, once the MultiIndex column
  schema is settled.

Reproducibility
: A full `export_code` command that emits a runnable Python script for a run.

Ecosystem integration
: A benchmarking module, catalogues, plotting, an mlflow flavor, and pushing
  models to the Hugging Face Hub.

## Related work

An adversarial agent benchmark suite, covering a foundation tier and a hard
tier with provider-neutral run records and scoring keys, is being developed on
the
[`feat/adversarial-benchmark`](https://github.com/siddharth7113/sktime-cli/tree/feat/adversarial-benchmark)
branch.
