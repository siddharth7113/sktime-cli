# sktime-cli v0.0.1 — Plan & Checklist

A stateless, agent-first CLI on top of sktime. Every command is a single process:
read files/names, call sktime, write files/stdout, exit with a meaningful code.
State lives on disk only (Hugging Face CLI model).

## Design decisions

- **Scope v0.0.1**: discovery + one-shot runs. No sessions/handles, no async jobs, no daemon.
- **State**: cache/workspace dir via `SKTIME_CLI_HOME` (default `~/.cache/sktime-cli`);
  models/datasets addressed by explicit paths or names.
- **Output**: `--format auto|human|agent|json|quiet` global option (from `hf` CLI);
  `auto` = human on TTY, agent-TSV otherwise. Results on stdout, everything else stderr.
- **Params**: skorch-style `--set key=value` with sklearn `__` nesting.
- **Framework**: Typer + Rich. Console script: `sktime-cli` (no `sktime` short name).
- **MCP relation**: independent of [sktime-mcp](https://github.com/sktime/sktime-mcp),
  but command vocabulary mirrors its tool names so agent knowledge transfers.
- **Estimator specs**: positional spec strings (`"NaiveForecaster(sp=12)"`,
  compositions via `*`/`+`/`|`) resolved sktime-first with a fallback to
  `registry.craft` — never depending on the upstream pytest bug.

## Exit codes / error codes

| exit | code(s) | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `sktime_error`, `internal` | library or unexpected failure |
| 2 | `usage` | bad flags/arguments |
| 3 | `missing_dependency` | soft dep absent (hint says what to install) |
| 4 | `not_found` | unknown estimator/dataset/tag/model path |
| 5 | `data_error`, `spec_error` | data validation or bad spec string |

Errors are emitted to stderr as `{"error": {"code", "message", "hint", "command"}}`
in agent/json formats.

## Milestones

- [x] **M0 — Bootstrap**: repo, pyproject (hatchling, uv), `.gitignore`,
      `app.py` skeleton with global options + `version`, `__main__.py`.
      Done when `uv run sktime-cli version --json` works and 1 CliRunner test is green.
- [x] **M1 — Foundations**: `_output.py` (format dispatch), `_errors.py`
      (CliError + exit codes), `_cache.py` (home resolution).
      Done when format matrix + error-JSON + exit-code tests are green.
- [x] **M2 — Registry**: disk-cached registry crawl;
      `registry search/describe/tags/types`.
      Done when warm search is fast, tag filters work, missing-dep estimators
      show install hints.
- [x] **M3 — Spec engine**: `_specs.py` (spec → estimator, `--set` overrides)
      + `model inspect`.
      Done when expression/composition/return-block specs build, sklearn-in-spec
      degrades cleanly, spec round-trips via `model inspect --spec`.
- [x] **M4 — Data IO**: `_io.py` (csv/parquet/json/.ts/.tsf, fh parsing)
      + `data inspect/convert/split`.
      Done when airline CSV round-trips losslessly (incl. PeriodIndex) and
      split writes `_train`/`_test`.
- [x] **M5 — Datasets**: `_datasets.py` name resolution
      + `datasets list/describe/load` (ucr/tsf behind `network` test marker).
      Done when `datasets load airline` works offline with a JSON manifest.
- [x] **M6 — Run**: `run fit` / `run predict` / `run fit-predict`
      for forecasting + classification on core deps.
- [x] **M7 — Evaluate**: `run evaluate` with `--cv` splitter specs and
      `--metric` resolution; per-fold + aggregate output.
- [x] **M8 — Polish**: `doctor`/`env`/`cache info|clear`, SKILL.md (ships in
      wheel), README, full verification pass, tag `v0.0.1`.

## Deferred to v0.0.2+

`data transform`, `run update`, `predict_interval`/`predict_quantiles`
(needs a stable flattening schema for MultiIndex columns first), `call_method`,
full `export_code`, benchmarking module, catalogues, plotting, mlflow flavor,
HF Hub push, absolute/dated `--fh`, `check_estimator` smoke command.

## Verification (run after M8)

```bash
sktime-cli version --json
sktime-cli doctor
sktime-cli registry search forecaster -t capability:missing_values=true --json | jq 'length'
sktime-cli registry describe NaiveForecaster --json | jq '.params.sp.default'
sktime-cli datasets load airline --output /tmp/airline.csv --json
sktime-cli data inspect /tmp/airline.csv --json | jq '.scitype,.mtype'
sktime-cli data split /tmp/airline.csv --test-size 12 --json
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --model-out /tmp/m.zip --json
sktime-cli run predict --model /tmp/m.zip --fh 1:12 --json
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline \
  --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3,4,5,6,7,8,9,10,11,12])" \
  --metric MeanAbsolutePercentageError --json
sktime-cli run fit "AutoARIMA()" --data airline; echo $?   # missing_dependency, exit 3
cd /tmp && sktime-cli registry types                       # works from any cwd
```

## Upstream sktime gotchas encoded in the implementation

1. `registry.craft()` raises `ModuleNotFoundError: pytest` (sklearn conftest crawl) —
   spec engine resolves sktime names itself and only falls back to `craft`.
2. `registry.check_tag_is_valid` is broken upstream — validate against
   `ESTIMATOR_TAG_REGISTER` directly.
3. `registry.ALIAS_DICT` is empty — no alias support built on it.
4. Bare `datatypes.mtype(obj)` is ambiguous for `pd.Series` — always pass
   `as_scitype` / use `check_is_scitype`.
5. Registry crawl is slow (worse with soft deps) — disk cache keyed by
   sktime version + python version + env hash.
6. A `sktime/` dir in cwd shadows `import sktime` for `python -m` — the
   console script is immune; dev checkout lives at `../sktime`.
7. Lean envs have zero soft deps — every command degrades with an
   actionable `uv pip install X` hint.
8. No CSV/parquet ingestion in sktime — `_io.py` owns that layer.
