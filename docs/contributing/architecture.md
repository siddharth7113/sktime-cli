# Architecture

`sktime-cli` is a thin, stateless layer over sktime: a Typer application, six
command groups, and a set of small internal modules that each own exactly one
concern. This page maps the repository, the modules, and the path a command
takes from argv to output.

## Repository layout

```
sktime_cli/
├── pyproject.toml            # hatchling build, uv-managed, ruff config
├── src/sktime_cli/
│   ├── app.py                # Typer root: global options, command registration
│   ├── __main__.py           # `python -m sktime_cli`
│   ├── _errors.py            # CliError + error-code → exit-code table
│   ├── _guard.py             # the one exception handler; shared --format/--json options
│   ├── _output.py            # format dispatch: human/agent/json/quiet emitters
│   ├── _cache.py             # workspace dirs + registry disk cache
│   ├── _specs.py             # "NaiveForecaster(sp=12)" → estimator instance
│   ├── _scitypes.py          # which sktime scitypes `run` dispatches on, classified once
│   ├── _io.py                # csv/parquet/json/.ts/.tsf/.arff read & write, --fh parsing
│   ├── _input.py             # --data (path or dataset id) → the y/X a workflow needs
│   ├── _frames.py            # flattens MultiIndex forecasts and segments into long form
│   ├── _datasets.py          # dataset name resolution and loaders (builtin/ucr/tsf/fpp3)
│   ├── _models.py            # model .zip save/load
│   ├── .agents/skills/sktime-cli/SKILL.md   # agent-facing contract, shipped in the wheel
│   └── commands/
│       ├── registry.py       # search · describe · tags · types
│       ├── datasets.py       # list · describe · load
│       ├── catalogues.py     # list · get
│       ├── data.py           # inspect · convert · split
│       ├── run.py            # fit · predict · fit-predict · transform · detect · evaluate
│       ├── model.py          # inspect
│       ├── metrics.py        # list · score
│       ├── check.py          # validate an object against sktime's API contract
│       └── env.py            # version · env · doctor · cache info/clear
├── tests/                    # pytest + Typer CliRunner, network tests marked
├── scripts/scitype_coverage.py  # regenerates the scitype coverage breakdown
└── docs/                     # this documentation site
    ├── conf.py               # Sphinx configuration
    ├── _ext/typer_cli.py     # generates the CLI reference from the live app
    └── assets/generate.py    # renders the terminal captures
```

## Dependency layering

Modules import strictly downwards; `_errors.py` and `_output.py` are the
leaves. There are no import cycles.

```mermaid
graph TD
    MAIN["__main__.py"] --> APP["app.py"]
    APP --> CMD["commands/*"]
    CMD --> GUARD["_guard.py"]
    CMD --> SPECS["_specs.py"]
    CMD --> SCI["_scitypes.py"]
    CMD --> INPUT["_input.py"]
    CMD --> FRAMES["_frames.py"]
    CMD --> IO["_io.py"]
    CMD --> DS["_datasets.py"]
    CMD --> MODELS["_models.py"]
    INPUT --> IO
    INPUT --> DS
    SPECS --> CACHE["_cache.py"]
    DS --> CACHE
    MODELS --> CACHE
    CMD --> OUT["_output.py"]
    GUARD --> OUT
    GUARD --> ERR["_errors.py"]
    CACHE --> ERR
    IO --> ERR
    INPUT --> ERR
    SCI --> ERR
    OUT --> ERR
```

`_frames.py` imports nothing from the package: it is pure pandas reshaping,
and a leaf like `_errors.py` and `_output.py`.

A deliberate import discipline keeps startup fast: **the only third-party
module imported at module level is `typer`**. Every sktime, pandas, numpy,
rich, and platformdirs import is function-local, so `sktime-cli --help` and
`--version` never pay sktime's import cost.

## Module responsibilities

| Module | Owns | Key entry points |
|---|---|---|
| `app.py` | Typer root, global options (`--format`, `--json`, `--cache-dir`, `--no-cache`, `--version`), command registration | `app`, `main()` |
| `_errors.py` | The error vocabulary. Codes are append-only and part of the published contract | `CliError`, `EXIT_CODES`, `missing_dependency()` |
| `_guard.py` | The single exception choke point; every leaf command is decorated with it | `handle_errors`, `FORMAT_OPT`, `JSON_OPT` |
| `_output.py` | Rendering for all five formats and the stdout/stderr split | `emit_record`, `emit_table`, `emit_frame`, `print_error`, `resolve_format` |
| `_cache.py` | Workspace resolution and the registry disk cache | `cli_home()`, `get_registry()`, `lookup()`, `import_object()` |
| `_specs.py` | Spec strings → estimator instances; `--set` overrides; metric/CV resolution | `build_estimator()`, `apply_sets()`, `resolve_metric()`, `resolve_cv()` |
| `_scitypes.py` | Which sktime scitypes `run` dispatches on, and why the rest are out of scope. Classified exactly once, asserted total by the tests | `handler_for()` |
| `_io.py` | File formats sktime doesn't handle itself; index conventions; `--fh` grammar | `read_any()`, `write_any()`, `parse_fh()`, `parse_size()` |
| `_input.py` | `--data` (a path or a dataset id) → the objects a workflow needs; which slot each fills is the estimator's call, not the file's | `load()`, `as_endogenous()` |
| `_frames.py` | Reshaping sktime results that don't survive a CSV round trip: MultiIndex probabilistic forecasts, `pd.Interval` segments | `melt()`, `widen()`, `segments_to_frame()`, `to_frame()` |
| `_datasets.py` | Dataset ID grammar (`airline`, `ucr:ArrowHead`, …) and loader normalization | `resolve()`, `load()`, `listing()`, `BUILTIN` |
| `_models.py` | Model artifact `.zip` in/out | `save_model()`, `load_model()`, `estimator_scitype()` |
| `commands/*` | Option surfaces and orchestration only, no domain logic | one `typer.Typer` per group |

## The life of a command

Taking `sktime-cli run fit "NaiveForecaster(sp=12)" --data airline.csv
--model-out model.zip` as the example:

1. **Root callback** (`app.py:_root`) stores the global `--format`/`--json`
   choice in `_output` and the cache flags in `_cache`. Global state is fine
   here because every invocation is one short-lived process.
2. **Guard**: the leaf command is wrapped by `_guard.handle_errors`, so from
   this point every failure becomes a structured error on stderr plus a
   meaningful exit code (see [the error model in Design](design.md#error-model)).
3. **Spec engine**: `_specs.build_estimator` parses the spec with `ast`,
   resolves `NaiveForecaster` against the cached registry, imports just that
   module, and evaluates the expression in a builtins-free namespace.
4. **Data loading**: `_input.load` treats `--data` polymorphically: an
   existing path is read via `_io.read_any` (index conventions applied),
   anything else resolves as a dataset name via `_datasets.resolve`. It
   returns a neutral container; `_input.as_endogenous` then decides which slot
   each object fills, from the estimator's scitype rather than from the file.
5. **Fit dispatch**: forecasters get `fit(y, X, fh)`; panel scitypes
   (classifier/regressor/clusterer) get `fit(X, y)`.
6. **Artifact**: `_models.save_model` writes the `.zip` (defaulting into the
   workspace `models/` dir when `--model-out` is omitted).
7. **Output**: a result record goes through `_output.emit_record` in
   whichever format was resolved: rich table (human), TSV (agent), one JSON
   document (json), or just the essential value (quiet).

## Testing

Tests run the CLI in-process through `typer.testing.CliRunner` (`invoke`
fixture in `tests/conftest.py`). A session-scoped autouse fixture points
`SKTIME_CLI_HOME` at a temp directory, so tests never touch the real cache.
This works because `_cache.cli_home()` reads the environment at call time,
not import time. Tests that download data are marked `network` and excluded
by default (`addopts = "-m 'not network'"` in `pyproject.toml`).
