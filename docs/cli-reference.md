# CLI reference

Every command, with its options. Authoritative source: `sktime-cli <command>
--help`; this page is the map.

## Global options

Accepted before any subcommand; `--format`/`--json` are also accepted on
every leaf command, where they override the global value.

| Option | Meaning |
|---|---|
| `--format auto\|human\|agent\|json\|quiet` | Output format (env var `SKTIME_CLI_FORMAT`). `auto` = human on a TTY, agent otherwise |
| `--json` | Shorthand for `--format json` |
| `--cache-dir PATH` | Workspace/cache directory (default `$SKTIME_CLI_HOME`, else the platform cache dir) |
| `--no-cache` | Bypass the registry disk cache |
| `--version` | Print the version and exit |

## Top-level commands

| Command | Purpose |
|---|---|
| `version` | Versions of sktime-cli, sktime, and Python |
| `env` | System info, dependency versions, workspace location |
| `doctor` | Health check: sktime import, cache writability, registry cache, optional dependencies with install hints. Exits 1 only if sktime itself won't import |
| `cache info` | Workspace location and per-subdirectory file counts/sizes |
| `cache clear [--all]` | Remove registry cache and downloads; `--all` also removes saved models |

## `registry` — discover sktime objects

| Command | Options |
|---|---|
| `search [SCITYPE]` | `-t/--filter-tag KEY=VALUE` (repeatable, AND; comma in VALUE = OR) · `-n/--name SUBSTR` · `--exclude NAME` (repeatable) · `--with-tags CSV` (extra columns) · `--installable-only` · `--limit N` |
| `describe NAME` | `--test-params` (include test parameter sets) · `--no-doc` (skip importing for the docstring) |
| `tags [SCITYPE]` | List valid tags per scitype |
| `types` | List scitypes with live object counts |

Examples:

```bash
sktime-cli registry search forecaster -t capability:missing_values=true
sktime-cli registry search classifier -n rocket --installable-only
sktime-cli registry describe NaiveForecaster --json
```

## `datasets` — list and fetch datasets

Dataset IDs: bare builtin names (`airline`) or namespaced remotes
(`ucr:ArrowHead`, `tsf:m1_yearly_dataset`, `fpp3:aus_arrivals`).

| Command | Options |
|---|---|
| `list` | `--source builtin\|ucr\|tsf\|fpp3\|objects` · `--task forecasting\|classification\|regression` · `-n/--name SUBSTR` |
| `describe NAME` | Shape/classes for builtins; source note for remotes (no download) |
| `load NAME` | `-o/--output PATH` · `--output-dir DIR` · `--split train\|test` · `--file-format csv\|parquet\|json\|ts` |

`load` prints a manifest of exactly what it wrote; panel datasets write as
`.ts`, MultiIndex forecasting data writes long-format csv, and an exogenous
`X` lands next to `y` as `<stem>_X<suffix>`.

## `data` — inspect, convert, split files

Shared input options on `inspect` and `convert`:
`--input-format csv|parquet|json|ts|tsf|arff` · `--index-col NAME|auto|none` ·
`--freq PANDAS_FREQ` · `--long` · `--id-col` · `--time-col`.

| Command | Options |
|---|---|
| `inspect PATH` | Reports scitype, mtype, shape, metadata, index details |
| `convert PATH` | `-o/--output PATH` (required) · `--to csv\|parquet\|json\|ts\|npy` · `--to-mtype MTYPE` |
| `split PATH` | `--test-size N\|FRACTION` or `--fh SPEC` (mutually exclusive) · `--train-size` · `--exog PATH` · `--train-out` / `--test-out` (default `<stem>_train/_test<suffix>`) · `--input-format` · `--index-col` · `--freq` |

## `run` — one-shot workflows

Estimators are spec strings (see [design.md](design.md#spec-strings-naming-models-like-youd-write-them)).
`--data` accepts a file path **or** a dataset name — an existing file wins.
Common options: `--target COL` (pick y from a multi-column file), `--exog
PATH`, `--index-col`, `--freq`, `--set key=value` (repeatable, `__` nesting).

| Command | Options |
|---|---|
| `fit SPEC` | `--data` (required) · `--fh` · `--model-out PATH` (default: workspace `models/`) |
| `predict` | `--model PATH` (required) · `--fh` · `--data` (required for panel models; exogenous data for forecasters) · `--proba` · `-o/--output` |
| `fit-predict SPEC` | fit options + `-o/--output`; forecasters require `--fh` |
| `evaluate SPEC` | `--cv SPLITTER_SPEC` or `--fh` (+ `--initial-window`) · `--metric NAME_OR_SPEC` (repeatable; default MeanAbsolutePercentageError) · `--strategy refit\|update\|no-update_params` · `-o/--output` |

`--fh` grammar: `1:12` (inclusive range), `1,2,12` (list), `6` (single step).

Evaluate output: per-fold rows plus `{"aggregate": {"test_<Metric>":
{"mean", "std"}}}` (forecasters only in v0.0.1).

Examples:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --model-out m.zip
sktime-cli run predict --model m.zip --fh 1:12 --json
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline \
  --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])" \
  --metric MeanAbsolutePercentageError --json
```

## `model` — inspect saved artifacts

| Command | Options |
|---|---|
| `inspect PATH` | `--fitted` (include fitted params) · `--spec` (print only the spec string) |

`model inspect --spec` output is itself a valid spec for `run fit` — the
reproducibility loop.

## Exit codes

`0` success · `1` library/internal error · `2` usage · `3` missing optional
dependency · `4` not found · `5` data or spec error. Details in
[design.md](design.md#error-model).
