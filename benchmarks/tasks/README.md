# Adversarial task details

This directory is the human-readable reviewer catalog for the fixed
`sktime-cli` model benchmark. There is one file per task, B01 through B10.

These files explain why each prompt exists, its controlled starting state,
the evidence a reviewer should expect, and the behavior that should lose
credit. They are reviewer material: do not supply them to a model during a
run. Models receive only the shared system prompt, the installed skill, the
task's call budget, and its prompt from [`../prompts.json`](../prompts.json).

Canonical sources:

- [`../prompts.json`](../prompts.json): exact prompts, setup commands, budgets;
- [`../scoring.json`](../scoring.json): expected facts and point criteria;
- [`../run.schema.json`](../run.schema.json): recorded model-run format;
- [`../README.md`](../README.md): controlled execution and review protocol.

## Task index

| ID | Task | Primary capability | Adversarial element |
|---|---|---|---|
| [B01](B01.md) | Capability-aware discovery | Registry filtering | Claims must be supported by tags |
| [B02](B02.md) | Unknown-name recovery | Error handling | Deliberate estimator typo |
| [B03](B03.md) | Dataset audit and split | Data workflow | Exact metadata and temporal holdout |
| [B04](B04.md) | Leakage-free forecast | Saved-model workflow | Test data must remain unseen |
| [B05](B05.md) | Controlled backtest | Evaluation | Both models must use identical CV |
| [B06](B06.md) | Classification probabilities | Panel workflow | Probabilities, not class labels |
| [B07](B07.md) | Composed estimator | Spec grammar | Composition must happen in the CLI |
| [B08](B08.md) | Dependency recovery | Error recovery | Installation and network are forbidden |
| [B09](B09.md) | Interval honesty trap | Capability boundaries | Estimator support is not CLI support |
| [B10](B10.md) | Classification evaluation trap | Capability boundaries | Accuracy must not be fabricated |

When a task changes materially, update its JSON source and detail file together
and increment `suite_version`. Never adjust expected results after seeing one
model's answer.
