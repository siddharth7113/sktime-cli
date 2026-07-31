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
