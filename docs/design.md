# Design

The decisions behind `sktime-cli`, and why they were made. The one-line
philosophy: **every command is a single process that reads files, calls
sktime, writes files or stdout, and exits with a meaningful code.**

## State model: stateless commands, state on disk

There are no sessions, handles, daemons, or async jobs. Anything that needs
to survive between invocations lives on disk under one workspace directory —
the same model as the Hugging Face CLI:

```
$SKTIME_CLI_HOME/                       (default: ~/.cache/sktime-cli)
├── registry/registry-<sktime>-py<X.Y>-<envhash>.json
├── downloads/{ucr,tsf,fpp3}/           # dataset fetch targets
└── models/                             # default `run fit` output
```

Resolution order for the workspace: `--cache-dir` flag → `$SKTIME_CLI_HOME` →
the platform cache dir (via platformdirs). It is resolved lazily on every
call, which is also what lets the test suite redirect it with a plain
environment variable.

Models and datasets are addressed by explicit paths or names — the CLI never
holds a reference you can't see with `ls`.

## Output contract

One global option, five formats: `--format auto|human|agent|json|quiet`
(plus `--json` as shorthand), modeled on the `hf` CLI.

- **Results go to stdout; everything else — logs, warnings, errors, result
  counts — goes to stderr.** You can always pipe stdout.
- `json` emits **exactly one JSON document per invocation**, no envelope.
- `agent` emits tab-separated values with a header row, never truncated.
- `auto` resolves to `human` on a TTY and `agent` otherwise, so piping into
  a tool or an agent transparently switches to machine output.
- `quiet` prints only the essential value (a name, a path), for shell
  substitution.

Format resolution is leaf-beats-root-beats-TTY: a `--format` on the
subcommand overrides one before the subcommand, which overrides the sniff.

## Error model

Errors are part of the API. Every failure is emitted to stderr as

```json
{"error": {"code": "...", "message": "...", "hint": "...", "command": "..."}}
```

in machine formats, or rich-styled text for humans. Codes map to stable exit
codes, and the table is **append-only** — codes are never renamed:

| exit | code(s) | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `sktime_error`, `internal` | library or unexpected failure |
| 2 | `usage` | bad flags/arguments |
| 3 | `missing_dependency` | soft dependency absent; the hint is a runnable install command |
| 4 | `not_found` | unknown estimator/dataset/tag/model path |
| 5 | `data_error`, `spec_error` | data validation or bad spec string |

Mechanically, commands raise `CliError(code, message, hint=...)` and a single
decorator (`_guard.handle_errors`) catches everything: `CliError` is emitted
as-is; a bare `ModuleNotFoundError` is converted to `missing_dependency` with
an install hint; any other exception is classified by walking its traceback —
a frame inside sktime (but not sktime_cli) makes it `sktime_error`, otherwise
`internal`. Tracebacks never reach the user; the location is preserved in the
error's `detail` field instead.

The `hint` field is a design commitment: wherever the CLI can know the fix
(install this package, use one of these names, try this flag grammar), the
hint says it verbatim. Agents are told to follow it, and the test suite
treats a missing hint on these paths as a bug.

## Spec strings: naming models like you'd write them

Estimators are given as Python-like constructor expressions:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" ...
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" ...      # pipeline
sktime-cli run evaluate "AutoETS() + NaiveForecaster()" ...        # ensemble
```

Compositions need no special parser — `*`, `+`, `|` are sktime's own
`BaseObject` operator overloads, so the CLI just has to resolve the names and
evaluate the expression.

How it works (`_specs.build_estimator`):

1. Parse with `ast` (expression mode; multi-line `return`-blocks fall back to
   exec mode — the same grammar as `sktime.registry.craft`).
2. Collect free names from the AST and resolve them **registry-first**
   against the cached registry; only the modules actually named get imported.
   A name whose soft dependencies are missing fails immediately with exit 3
   and an install hint.
3. Evaluate with `{"__builtins__": {}}` and a namespace containing only the
   resolved sktime classes plus a small safe-builtin allowlist
   (`range`, `list`, `dict`, `tuple`, `abs`, `min`, `max`). No file, import,
   or attribute access sneaks in through a spec.
4. Apply `--set key=value` overrides via sklearn's `set_params`, so nested
   components are reachable with the `__` convention
   (`--set forecaster__sp=4`).

`sktime.registry.craft` is only a **fallback** for names the registry doesn't
know (typically raw sklearn estimators). Upstream `craft` crawls sklearn and
trips over sklearn's `conftest.py` importing pytest in lean environments —
resolving sktime names locally sidesteps that bug entirely, and the fallback
converts it into an actionable error when it does occur.

## Registry cache: the latency lever

sktime's `all_estimators` crawl takes seconds (worse with soft dependencies
installed). The CLI runs it once and serializes every record — name, module,
scitypes, tags, parameters, installability — to JSON in the workspace.
Warm `registry search` and every spec-name lookup then cost a JSON load plus
a filter.

The cache key is structural, not temporal: the filename embeds the sktime
version, the Python version, and an 8-char hash over all installed
distributions. Any install/upgrade/removal changes the filename, so a stale
cache is *unreachable* rather than invalidated. A schema version inside the
payload guards format changes; corrupt files silently rebuild; a read-only
cache dir degrades to a live crawl. `--no-cache` bypasses it entirely.

## Data IO: the layer sktime doesn't have

sktime has no csv/parquet ingestion, so `_io.py` owns it, with documented
conventions rather than guesses:

- The **first column is the time index** by default (`--index-col` to
  override or `none` to disable). Datetime-looking indexes become a
  `PeriodIndex` (with `--freq` or inferred); integer indexes are used as-is.
- After indexing, a single remaining column is squeezed to a Series.
- Long-format panel data via `--long --id-col ... --time-col ...` becomes
  sktime's `pd-multiindex` mtype.
- JSON uses pandas **split orient** (`{"index", "columns", "data"}`) in both
  directions — the one JSON shape that round-trips indexes losslessly.
- `.ts`, `.tsf`, `.arff` delegate to sktime's own readers; parquet needs the
  `parquet` extra and fails with exit 3 and the install hint otherwise.
- `--fh` accepts `1:12` (inclusive range), `1,2,12` (list), or `6` (single),
  always as a relative horizon.

`data inspect` answers "what would sktime think this file is": it routes
through `check_is_scitype` and reports the scitype, mtype, and metadata —
useful for humans, and the designed first move for agents handed an unknown
file.

## Datasets: one grammar over four sources

Dataset IDs are namespaced: bare names (`airline`) resolve builtin-first,
then case-insensitively across remotes; explicit prefixes (`ucr:ArrowHead`,
`tsf:m1_yearly_dataset`, `fpp3:aus_arrivals`) pin the source. Unknown names
get did-you-mean suggestions; ambiguous bare names list the namespaced
candidates instead of guessing. All loader return shapes are normalized to
one `{task, y, X?, metadata?}` dict, and remote downloads land inside the
workspace so `cache clear` reclaims them.

## Agents as first-class users

The CLI ships its own manual for agents:
[skills/sktime-cli/SKILL.md](../skills/sktime-cli/SKILL.md) documents the
contract (always `--json`, read errors from stderr, follow the hint, exit
codes) plus task recipes for discovery, data prep, forecasting, backtesting,
and classification. The file is force-included into the wheel at
`sktime_cli/SKILL.md`, so an installed environment carries its own
documentation. The command vocabulary deliberately mirrors
[sktime-mcp](https://github.com/sktime/sktime-mcp)'s tool names so agent
knowledge transfers between the CLI and MCP surfaces.

## Conventions and tooling

- **Derive, don't duplicate**: configuration comes from `pyproject.toml` and
  `importlib.metadata` where possible — e.g. `doctor`'s optional-dependency
  list is computed from package metadata, not hand-maintained.
- **uv** for environment management (`uv.lock` committed; sktime as an
  editable path source during development), **hatchling** for builds.
- **ruff** (format + lint, numpy docstring convention, security rules) and
  **pre-commit** are mandatory; `pytest` with a `network` marker keeps the
  default test run offline.
- Typer + rich for the frontend; the console script is `sktime-cli` only —
  no `sktime` short name that could collide with the library.

## Known limitations (v0.0.1)

- `run evaluate` supports forecasters only.
- `datasets load` writes panels only as `.ts`.
- No `predict_interval`/`predict_quantiles` yet (needs a stable flattening
  schema for MultiIndex columns first).
- See [PLAN.md](../PLAN.md) for the full deferred list and the upstream
  sktime gotchas the implementation works around.
