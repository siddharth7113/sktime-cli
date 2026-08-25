# Output formats and errors

Output is part of the CLI's contract, not an afterthought. One global option
selects the format, results and diagnostics go to different streams, and
failures carry stable codes. This page describes all three.

## The two streams

Results go to stdout. Everything else, meaning logs, warnings, result counts,
and errors, goes to stderr. You can always pipe stdout into another tool
without filtering noise out of it first:

```bash
sktime-cli registry search forecaster --json | jq 'length'
```

## Formats

`--format` takes five values, and `--json` is shorthand for `--format json`:

`auto`
: The default. Resolves to `human` when stdout is a terminal and `agent`
  otherwise. Piping a command into a tool switches it to machine output
  without a flag.

`human`
: Rich tables and styled text, sized for a terminal.

`agent`
: Tab-separated values with a header row, never truncated. Use it for `awk`,
  `cut`, and shell pipelines.

`json`
: Exactly one JSON document per invocation, with no envelope around it. Use it
  for `jq` and for programs that parse output.

`quiet`
: Only the essential value, such as a name or a path. Use it in shell
  substitution:

  ```bash
  model=$(sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --format quiet)
  ```

`--format` works before the subcommand and on the subcommand itself.
Resolution is leaf beats root beats terminal detection, so a `--format` on the
subcommand overrides one that comes earlier, which overrides the `auto` sniff.

The `SKTIME_CLI_FORMAT` environment variable sets the default format for a
shell session.

## Errors

Every failure is emitted to stderr. In `agent` and `json` formats it's a
single JSON object:

```json
{
  "error": {
    "code": "missing_dependency",
    "message": "AutoARIMA requires pmdarima",
    "hint": "uv pip install \"pmdarima\"",
    "command": "run fit"
  }
}
```

In `human` format the same record is rendered as styled text.

The `hint` field is a commitment, not a convenience. Wherever the CLI can know
the fix, meaning a package to install, a set of valid names, or the right flag
syntax, the hint states it. The test suite treats a missing hint on those
paths as a bug.

## Exit codes

Error codes map to exit codes, and the table is append-only, so codes are
never renamed or reused:

| Exit | Error codes | Meaning |
|---|---|---|
| `0` | | Success |
| `1` | `sktime_error`, `internal` | A library call or the CLI itself failed |
| `2` | `usage` | Bad flags or arguments |
| `3` | `missing_dependency` | An optional dependency is absent, and the hint names it |
| `4` | `not_found` | Unknown estimator, dataset, tag, or model path |
| `5` | `data_error`, `spec_error` | Data validation failed, or a spec string is invalid |

Exit code `3` is worth special handling in scripts, because it means the
command would have worked with one more package installed:

```bash
if ! sktime-cli run fit "AutoARIMA()" --data airline --json; then
  status=$?
  if [ "$status" -eq 3 ]; then
    echo "Install the missing dependency and retry."
  fi
fi
```

Tracebacks never reach the user. When an unexpected exception occurs, the CLI
records the failing location in the error's `detail` field instead.

## What to read next

- [Using sktime-cli from an agent](agents.md) for how an agent consumes this
  contract.
- [Environment and workspace](../reference/environment.md) for the
  environment variables that affect output.
