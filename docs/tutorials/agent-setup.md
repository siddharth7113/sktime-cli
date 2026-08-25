# Set up an agent to drive the CLI

`sktime-cli` is built for AI coding agents to use directly. This tutorial
installs the CLI and the skill file that teaches an agent the command surface,
checks that the agent can see it, and hands it a task.

It takes about five minutes. The result is an agent that can search sktime's
registry, prepare data, and backtest a model on its own.

An agent that has never seen `sktime-cli` guesses. It invents flags, assumes a
session that doesn't exist, and parses human-formatted tables. The skill file
is one Markdown file covering the output contract, the exit codes, the spec
string syntax, and a recipe per task. `sktime-cli` ships it inside the wheel,
so it is versioned with the code it describes.

## Install the CLI

Pick the path that matches how you work.

### As a project dependency

Use this when the analysis lives in a repository, so the CLI, the skill, and
the lockfile stay together:

```bash
uv add sktime-cli
```

### As a standalone tool

Use this for one `sktime-cli` on your PATH, isolated from every project:

```bash
uv tool install sktime-cli
```

Either way, check the install before you point an agent at it:

```bash
sktime-cli doctor
```

```{code-block} text
:caption: Output

 check                            status  detail
 sktime import                    ok      version 1.1.0, 0.51s
 cache dir                        ok      /home/you/.cache/sktime-cli
 registry cache                   ok      registry-1.1.0-py3.14-eb4338f5.json
 optional: pyarrow                ok      installed
 optional: numba                  warn    uv pip install numba
 optional: statsmodels            warn    uv pip install statsmodels
 optional: pmdarima               warn    uv pip install pmdarima
28 result(s)
```

`warn` rows are optional estimator dependencies that aren't installed. An
agent that needs one gets exit code `3` and a hint naming the install command,
so the failure is recoverable. `doctor` exits non-zero only when sktime fails
to import.

## Install the skill

### From a project dependency

[library-skills](https://library-skills.io) finds the skills that a project's
installed packages bundle and links them into the directories agents read:

```bash
uvx library-skills --claude --skill sktime-cli --yes
```

```{code-block} text
:caption: Output

 context
Project root               /home/you/analysis
Target Python environment  .venv
Site-packages              .venv/lib/python3.13/site-packages

 status
 Target             Skill       Status  Path                     Source
 universal          sktime-cli  new     .agents/skills/sktime-…  .venv/lib/python3.13/…
 claude-compatible  sktime-cli  new     .claude/skills/sktime-…  .venv/lib/python3.13/…

 Installed:  sktime-cli (sktime-cli) -> .agents/skills/sktime-cli
 Installed:  sktime-cli (sktime-cli) -> .claude/skills/sktime-cli
```

`.agents/skills/` is the agent-neutral location. `--claude` adds the second
link under `.claude/skills/`, where Claude Code looks. Drop `--skill
sktime-cli` to list every skill found and pick from them.

The links are relative and point into the installed package:

```bash
ls -l .claude/skills/
```

```{code-block} text
:caption: Output

sktime-cli -> ../../.venv/lib/python3.13/site-packages/sktime_cli/.agents/skills/sktime-cli
```

Upgrading `sktime-cli` upgrades the skill with it, so the agent's
documentation can't drift from the CLI's behavior. The links are safe to
commit, and they resolve once anyone installs the project's dependencies.

Re-run the command after changing dependencies.

### From a standalone install

`library-skills` reads a project's environment, so it can't see a CLI
installed with `uv tool install`. Copy the file into the agent's skill
directory. For Claude Code that's `~/.claude/skills` for every project, or
`.claude/skills` for one:

```bash
mkdir -p ~/.claude/skills/sktime-cli
curl -fsSL https://raw.githubusercontent.com/siddharth7113/sktime-cli/main/src/sktime_cli/.agents/skills/sktime-cli/SKILL.md \
  -o ~/.claude/skills/sktime-cli/SKILL.md
```

A copy is a snapshot, not a link, so repeat it after upgrading.

### For any other agent

The skill is a single Markdown file with YAML frontmatter, so any agent that
takes one instructions file can use it. Point that file at the preceding path,
or paste the contents into whatever the agent reads.

## Check that it took

```bash
uvx library-skills list
```

```{code-block} text
:caption: Output

 Skill       Package     Version  Description
 sktime-cli  sktime-cli  0.0.2    Run time series machine learning from the shell with
                                  sktime-cli: discover estimators in sktime's registry,
                                  fetch datasets, inspect and split series files,
                                  fit/predict/transform/detect/evaluate models, score
                                  predictions, and manage saved model artifacts.
```

In Claude Code, `/skills` lists what the session can see. The `description`
field is what the agent matches against, so a request mentioning forecasting,
backtesting, or time series classification pulls the skill in.

## Give it a task

A useful prompt states the goal and the constraint, and leaves the method
open:

> I have `sales.csv`, monthly, one column of revenue. Use sktime-cli to find a
> forecaster that handles missing values, backtest it against a naive
> baseline, and forecast the next 12 months with an 80% interval. Don't write
> any Python.

The agent then works through something like this. Every step is a command you
could have typed:

```bash
# 1. Confirm the tool is healthy before relying on it.
sktime-cli doctor --json

# 2. Find out what the file actually contains.
sktime-cli data inspect sales.csv --json

# 3. Narrow the registry to estimators that fit the data and are installed.
sktime-cli registry search forecaster \
    -t capability:missing_values=true --installable-only --json

# 4. Read the parameters before building a spec string.
sktime-cli registry describe NaiveForecaster --json

# 5. Hold out the last year.
sktime-cli data split sales.csv --fh 1:12 --json

# 6. Score the baseline and the candidate on the same folds.
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data sales_train.csv --fh 1:12 --json
sktime-cli run evaluate "AutoETS(auto=True, sp=12)" \
    --data sales_train.csv --fh 1:12 --json

# 7. Fit the winner and forecast with an interval.
sktime-cli run fit "AutoETS(auto=True, sp=12)" \
    --data sales_train.csv --model-out sales.zip --json
sktime-cli run predict --model sales.zip --fh 1:12 --interval 0.8 --json
```

Two things make that sequence work unsupervised. Every command carries
`--json`, so the agent parses one document instead of scraping a table. And no
command depends on hidden state, so a retry gives the same answer.

## What the agent does when something fails

Step 6 is the interesting case. `AutoETS` needs statsmodels, which isn't
installed by default:

```{code-block} text
:caption: Output on stderr

{
  "error": {
    "code": "missing_dependency",
    "message": "AutoETS requires missing package(s): statsmodels",
    "hint": "uv pip install statsmodels",
    "command": "run evaluate"
  }
}
```

Exit code `3`, a stable `code` to branch on, and a `hint` holding the fix. An
agent that reads the hint installs statsmodels and retries. An agent that sees
only a traceback reports a dead end.

The four exit codes worth knowing:

| code | meaning | what an agent should do |
| --- | --- | --- |
| `3` | missing optional dependency | run the `hint`, retry |
| `4` | not found | re-run discovery, fix the name |
| `5` | invalid data or spec | inspect the file, fix the spec |
| `2` | usage error | re-read the command's options |

## Keep the agent honest

The skill tells an agent how to drive the CLI. It doesn't stop the agent
drawing bad conclusions, so add a few instructions of your own:

Insist on a baseline
: An agent asked for "the best forecaster" returns the most complicated one.
  Ask it to score `NaiveForecaster` on the same folds and report both numbers.

Ask for the commands
: An agent that reports its commands gives you something to re-run and check.
  If it can't show the command, it didn't run one.

Split before exploring
: Say so explicitly. An agent that backtests on data it later scores against
  reports a number that means nothing.

Name the horizon
: An unstated horizon is the most common source of a confidently wrong answer.
  `--fh 1:12` is unambiguous.

## What to read next

- [Using sktime-cli from an agent](../guide/agents.md) for the full contract
  and the design reasoning behind it.
- [Output formats and errors](../guide/output.md) for every format and the
  complete exit code table.
- [Forecast crude oil prices](oil-prices.md) to work the preceding sequence
  through by hand.
