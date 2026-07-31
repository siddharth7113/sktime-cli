# sktime-cli

Command-line interface for [sktime](https://github.com/sktime/sktime), designed
for AI agents and humans.

`sktime-cli` is a stateless layer on top of sktime: discover estimators through
sktime's native registry, fetch datasets, inspect and convert time series files,
and run one-shot fit / predict / evaluate workflows — all from the shell, with
machine-readable output.

It is the CLI sibling of [sktime-mcp](https://github.com/sktime/sktime-mcp) and
share same commands (`registry search` ~ `query_registry`,
`registry describe` ~ `describe_component`, `fit`/`predict`/`evaluate`.

## Install

```bash
uv tool install sktime-cli   # or: pip install sktime-cli
```

## Quickstart

```bash
# what can I use?
sktime-cli registry search forecaster -t capability:missing_values=true
sktime-cli registry describe NaiveForecaster

# get data
sktime-cli datasets load airline --output airline.csv
sktime-cli data inspect airline.csv

# fit, predict, evaluate — estimators are given as sktime spec strings
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline.csv --model-out model.zip
sktime-cli run predict --model model.zip --fh 1:12 --json
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline.csv --fh 1:12 \
  --metric MeanAbsolutePercentageError
```

## For agents

- every command accepts `--format json` (or `--json`) for a single parseable
  JSON document on stdout; errors are JSON on stderr with stable codes;
- exit codes: `0` ok, `1` library error, `2` usage, `3` missing dependency,
  `4` not found, `5` data/spec error;
- see [skills/sktime-cli/SKILL.md](skills/sktime-cli/SKILL.md) for the full
  agent-facing contract and task-oriented workflows (drop the `skills/` folder
  into your agent's skill directory, e.g. `.claude/skills/`).

## Agent benchmark

The versioned [adversarial benchmark](benchmarks/README.md) supplies a
foundation tier and a [hard end-to-end tier](benchmarks/hard/README.md), plus a
provider-neutral run-record schema, detailed scoring keys, and a scorer for
comparing how different AI models use this skill and which CLI gaps they
identify. Benchmark agents are restricted to `sktime-cli`; every command,
stdout/stderr stream, exit code, final answer, model setting, and skill version
is retained for audit.

## Status

v0.0.1 — early alpha. See [PLAN.md](PLAN.md) for the roadmap and checklist.

## License

BSD 3-Clause, consistent with sktime.
