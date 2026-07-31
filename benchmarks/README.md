# sktime-cli adversarial model benchmark

These suites compare how reliably different AI models use `sktime-cli` and
which product gaps they expose. They are provider-neutral: every model receives
the same system prompt, the same installed skill, one fixed task at a time,
and an isolated directory. A complete record retains every visible assistant
message, command, stdout, stderr, exit code, duration, final answer, model
setting, and skill version.

## Benchmark tiers

- The B01-B10 foundation tier in [`prompts.json`](prompts.json) checks command
  literacy and isolated workflows.
- The recommended [`hard/`](hard/README.md) tier contains six end-to-end
  scenarios requiring model selection, leakage control, paired exogenous data,
  artifact reproduction, multi-failure recovery, and hierarchical forecasting.

Use the hard tier for serious model ranking. Use the foundation tier as a smoke
test or diagnostic breakdown; do not compare scores across tiers.

## How to run the hard benchmark

The benchmark is deliberately independent of OpenAI, Anthropic, Google, or any
other model API. Your model adapter is responsible for starting a conversation,
exposing a restricted command tool, and exporting the complete trace into the
shared run format. The benchmark supplies the fixed inputs, setup commands,
scoring key, and validator.

### 1. Prepare the reference environment

From the repository root:

```bash
uv sync --frozen
export PATH="$PWD/.venv/bin:$PATH"
sktime-cli version --json
sktime-cli env --json
sktime-cli registry describe AutoARIMA --no-doc --json
```

For the hard suite, use the default locked development environment: `pytest`
must be present so H02 can resolve `LinearRegression()` inside an estimator
spec, while `pmdarima` must remain absent for the controlled dependency failure.
Disable network access for the model process. Do not install anything after a
run starts.

Optionally warm the registry once before timing any models:

```bash
sktime-cli registry types --json
```

Preflight and cache-warming calls are harness operations. Do not include them
in a model's task trace.

### 2. Create the run record and workspaces

Choose an exact provider/model version and create one run file plus an isolated
directory per task:

```bash
mkdir -p runs/workspaces/acme-model
cp benchmarks/hard/run.template.json runs/acme-model-hard.json
mkdir -p runs/workspaces/acme-model/H01
mkdir -p runs/workspaces/acme-model/H02
mkdir -p runs/workspaces/acme-model/H03
mkdir -p runs/workspaces/acme-model/H04
mkdir -p runs/workspaces/acme-model/H05
mkdir -p runs/workspaces/acme-model/H06
sha256sum skills/sktime-cli/SKILL.md
```

Fill the run template's model version/settings, Python/platform, timestamps,
and real skill checksum. Leave `complete_tool_trace` false until all provider
logs have been audited. Never reuse a task conversation or workspace.

### 3. Prepare one task

The canonical hard tasks are in [`hard/prompts.json`](hard/prompts.json). For a
task such as H04, inspect its call budget, prompt, and harness-only setup:

```bash
jq '.tasks[] | select(.id == "H04") | {max_cli_calls, prompt, setup}' \
  benchmarks/hard/prompts.json
jq -r '.tasks[] | select(.id == "H04") | .setup[] | @sh' \
  benchmarks/hard/prompts.json
```

Run the printed setup commands with the real `sktime-cli` from inside that
task's workspace before launching the model. The repository owns these fixed
commands, but review them before execution. Setup output is fixture provenance,
not model output, so retain it separately and exclude it from `tool_calls`.

H01, H02, H03, and H06 have no setup because data acquisition is part of what
the model is being tested on. H04 and H05 have controlled starting artifacts.

### 4. Construct the model conversation

Start a fresh conversation containing exactly these inputs in order:

1. system message: [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md);
2. system/developer context: the complete
   [`skills/sktime-cli/SKILL.md`](../skills/sktime-cli/SKILL.md);
3. user message:

   ```text
   Maximum CLI calls: <max_cli_calls>

   <prompt>
   ```

Do not supply `scoring.json`, anything under `tasks/`, another model's output,
or prior task messages. The model's shell/tool policy must accept only argv
whose first element is exactly `sktime-cli`. Reject and record Python, `uv`,
shell utilities, network tools, filesystem readers, and all other tools.

Every model command must include `--json`. The benchmark harness and reviewer
may use normal shell/Python utilities; the `sktime-cli`-only restriction applies
to the model under test.

### 5. Capture a complete provider trace

For every visible model message and tool call, retain:

- ordered argv, stdout, stderr, exit code, and duration;
- rejected or non-CLI tool attempts as `kind: "other"`;
- visible assistant messages and final answer;
- input/output token counts when the provider exposes them;
- task timestamps and any infrastructure failure.

Convert the provider output into the task structure defined by
[`run.schema.json`](run.schema.json). Do not omit unsuccessful calls: H03 and
H05 require failures as evidence. A command record looks like:

```json
{
  "kind": "command",
  "argv": ["sktime-cli", "model", "inspect", "production.zip", "--json"],
  "stdout": "{...}\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 914.2
}
```

After H01-H06 are complete, verify the trace against the provider's raw log and
only then set `complete_tool_trace` to true.

### 6. Review and score the run

Keep [`hard/scoring.json`](hard/scoring.json) hidden until the run is sealed.
For every task, add all four `judgments` to the run record. Award 0, 1, or 2
points per criterion and cite a command number, output field, or final-answer
statement in `notes`.

Validate a partially assembled record during development:

```bash
python benchmarks/score.py runs/acme-model-hard.json --allow-partial
```

Score a completed model or compare several models from the same tier:

```bash
python benchmarks/score.py runs/acme-model-hard.json
python benchmarks/score.py \
  runs/model-a-hard.json runs/model-b-hard.json runs/model-c-hard.json
python benchmarks/score.py runs/acme-model-hard.json --json \
  > runs/acme-model-hard-score.json
```

The hard suite is scored out of 60. Prefer two blind reviewers and reconcile
judgment differences greater than one point. The scorer automatically checks
CLI-only discipline, `--json`, call budgets, suite/environment compatibility,
error JSON rates, recovery behavior, tokens, and reported gaps. It refuses to
rank foundation and hard runs together.

The fixed foundation suite is [`prompts.json`](prompts.json). Keep
[`scoring.json`](scoring.json) hidden until a model finishes a task so its
expected facts do not leak into the answer.

Reviewer-facing explanations for every prompt live in the
[`tasks/`](tasks/README.md) directory. These files document intent, fixtures,
reference observations, adversarial failure modes, and expected gap signals;
they must not be included in model context.

## What is measured

| Area | Tasks | Signal |
|---|---|---|
| Registry use | B01-B02 | capability filtering and error recovery |
| Data handling | B03 | load, inspect, temporal split |
| Forecasting | B04-B05 | leakage avoidance, artifacts, controlled CV |
| Other workflows | B06-B07 | panel classification and spec composition |
| Robustness | B08 | missing-dependency recovery without installation |
| Honesty/gaps | B09-B10 | no hallucinated intervals or classifier evaluation |

Each task is worth 10 points. Four binary/partial outcome criteria contribute
8 points. Two protocol points are calculated from the trace: one for using
only `sktime-cli`, and one for using JSON on every call while staying inside
the call budget. Any non-CLI tool call makes that task worth zero. CLI latency
is recorded but not scored because registry cache and hardware affect it.

## Controlled run protocol

1. Create a fresh environment from `uv.lock`; use the console binary from that
   environment. The reference setup is `sktime-cli==0.0.1`, `sktime==1.1.0`,
   no `pmdarima`, and no network. Record `sktime-cli env --json` output in the
   environment metadata.
2. Record the exact model/provider version, temperature, seed (if supported),
   Python/platform, CLI versions, and SHA-256 of
   `skills/sktime-cli/SKILL.md`. Do not label a moving alias such as "latest"
   as a reproducible model version.
3. Start a fresh model conversation and fresh working directory for every
   task. Inject [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md), then the full skill,
   then a user message containing `Maximum CLI calls: <max_cli_calls>` followed
   by that task's `prompt` field. Do not let tasks share context.
4. Before the model starts, run the task's `setup` argv arrays in its working
   directory with the real CLI. Setup calls are fixture preparation and must
   not appear as model tool calls.
5. Enforce a shell/tool allow-list so the model can execute only argv beginning
   with `sktime-cli`. Save the provider's complete tool trace, including any
   rejected or non-shell tool attempt. Do not rely only on text copied by the
   model.
6. Do not retry a model failure. Repeat only documented infrastructure
   failures, and keep the failed attempt. Do not install a dependency during a
   run.
7. Convert the provider trace to [`run.schema.json`](run.schema.json). Start
   from [`run.template.json`](run.template.json), add all ten task records, and
   set `complete_tool_trace` only after checking the provider trace is complete.
8. After the run is sealed, score each criterion 0, 1, or 2 and add a short
   evidence note. Prefer two blind reviewers; reconcile any difference greater
   than one point before comparing models.

A recorded command has this form:

```json
{
  "kind": "command",
  "argv": ["sktime-cli", "registry", "types", "--json"],
  "stdout": "[{...}]\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 812.4
}
```

Record a forbidden tool attempt as `kind: "other"`; never omit it. This is what
makes the "sktime-cli only" rule auditable across model providers.

The surrounding task record also contains `assistant_messages` (all visible
messages before the final response), `final_answer`, and one judgment per
criterion. For example:

```json
{
  "id": "B01",
  "assistant_messages": ["I will search the registry with capability filters."],
  "tool_calls": [],
  "final_answer": "...",
  "judgments": [
    {"criterion_id": "query", "earned": 2, "notes": "call 1 has the required tag filter"}
  ]
}
```

The abbreviated arrays above are illustrative; actual records contain every
call and all four judgments from the scoring key.

## Score and compare

The scorer uses only the Python standard library. It validates task/criterion
IDs, checks call budgets and JSON discipline, applies the non-CLI
disqualification rule, and reports comparable telemetry. If every task has
provider token counts, it also totals input and output tokens for efficiency
comparison.

```bash
python benchmarks/score.py runs/gpt.json
python benchmarks/score.py runs/gpt.json runs/claude.json runs/gemini.json
python benchmarks/score.py runs/gpt.json --json
```

The scorer selects the foundation or hard scoring key from the run's
`suite_id` and refuses to combine different tiers in one ranking.

`successful_call_rate` is descriptive, not a quality score: B02, B08, B09, and
B10 deliberately exercise failures. `json_error_rate` measures whether failed
CLI calls actually honored the documented JSON error contract.

## Record functionality gaps

Use `reported_gaps` in the run record for every observed product limitation:

```json
{
  "task_id": "B09",
  "capability": "prediction intervals",
  "status": "missing",
  "evidence": "model inspect shows capability:pred_int=true, but run predict exposes no interval or coverage option"
}
```

Keep four statuses distinct:

- `missing`: no CLI operation exposes the capability;
- `partial`: the operation exists but cannot complete the requested workflow;
- `bug`: documented behavior exists but fails or violates the output contract;
- `dependency`: the CLI path exists and correctly reports an absent soft dep.

B09 and B10 are known missing capabilities. An interval attempt may also reveal
that Typer's unknown-option error is human-formatted even when `--json` was
passed; record that separately as an output-contract bug. B08 is a dependency
condition, not automatically a missing CLI feature.
