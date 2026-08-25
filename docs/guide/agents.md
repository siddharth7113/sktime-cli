# Using sktime-cli from an agent

`sktime-cli` treats AI agents as first-class users. An agent needs three
things from a tool: predictable output, failures it can act on, and
documentation it can read. The CLI provides all three.

## The contract

An agent should follow four rules:

1. Pass `--json` on every call. The command then writes exactly one JSON
   document to stdout and nothing else.
2. Read errors from stderr. A failure is a JSON object with `code`,
   `message`, and `command`, plus `hint` and `detail` where they apply.
3. Branch on `code`, which is stable across releases. Act on the `hint` when
   there is one: it usually contains the exact command that fixes the problem,
   most often an install command.
4. Branch on the exit code. Code `3` means a missing optional dependency, `4`
   means something wasn't found, and `5` means the data or the spec was
   invalid.

The following capture shows a JSON result and a structured error side by side:

:::{div} .terminal-capture
```{image} ../assets/agent.svg
:alt: JSON output from a command next to a structured error record and its exit code
:align: center
```
:::

For the full format and error tables, see [Output formats and
errors](output.md).

## Install the skill file

The repository ships an agent skill at `skills/sktime-cli/SKILL.md`. It
documents the contract and gives task recipes for discovery, data preparation,
forecasting, backtesting, and classification.

To give an agent the skill, copy the `skills/` directory into the agent's
skill directory. For Claude Code, that's `.claude/skills/`:

```bash
git clone https://github.com/siddharth7113/sktime-cli
cp -r sktime-cli/skills/sktime-cli .claude/skills/
```

The same file ships inside the wheel at `sktime_cli/SKILL.md`, so an installed
environment carries its own agent documentation. To find it:

```bash
python -c "import sktime_cli, pathlib; print(pathlib.Path(sktime_cli.__file__).parent / 'SKILL.md')"
```

## Why the design suits agents

Stateless commands
: Nothing an agent does depends on an earlier call having set up hidden state.
  A retried command produces the same result, and a command in a fresh shell
  behaves the same way.

Explicit artifacts
: Fitted models are files at paths the agent chose or the CLI printed. There
  are no opaque handles to track across turns.

Discovery before use
: `registry search` and `registry describe` let an agent check that an
  estimator exists and that its dependencies are installed before spending a
  call on a run that would fail.

Recoverable failures
: An agent that hits exit code `3` can install the named package and retry,
  rather than reporting a dead end.

## A worked sequence

A typical agent session looks like the following. Each command's output feeds
the next one:

```bash
# 1. Check the environment.
sktime-cli doctor --json

# 2. Find a forecaster that handles the data's quirks.
sktime-cli registry search forecaster \
    -t capability:missing_values=true --installable-only --json

# 3. Confirm the parameters before building a spec.
sktime-cli registry describe NaiveForecaster --json

# 4. Understand the input file.
sktime-cli data inspect data.csv --json

# 5. Backtest before committing to a model.
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data data.csv --fh 1:12 --json

# 6. Fit and forecast.
sktime-cli run fit "NaiveForecaster(sp=12)" \
    --data data.csv --model-out model.zip --json
sktime-cli run predict --model model.zip --fh 1:12 --json
```
