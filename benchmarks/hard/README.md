# Hard end-to-end benchmark tier

This is the primary suite for comparing capable AI agents. Unlike the B01-B10
foundation tier, every H task requires a multi-stage workflow, an evidence-based
decision, persisted artifacts, and explicit handling of CLI boundaries.

| Task | Workflow | Maximum calls | Central difficulty |
|---|---|---:|---|
| H01 | Forecast tournament to deployment | 11 | Leakage-free selection across three candidates |
| H02 | Exogenous forecasting | 11 | Keep y/X aligned through split, CV, fit, predict |
| H03 | Classification assessment | 12 | Deliver artifacts but refuse unsupported scoring |
| H04 | Artifact reproduction | 10 | Recover spec, reproduce, apply nested mutation |
| H05 | Production incident | 9 | Recover around five simultaneous constraints/gaps |
| H06 | Hierarchical forecasting | 9 | Preserve hierarchy and audit CSV serialization |

The exact model inputs are [`prompts.json`](prompts.json); the hidden reviewer
key is [`scoring.json`](scoring.json). Detailed reviewer notes are under
[`tasks/`](tasks/README.md). Run records use [`run.template.json`](run.template.json)
and the shared [`../run.schema.json`](../run.schema.json).

Use the same isolation, skill injection, tool allow-list, and recording protocol
as the [main benchmark guide](../README.md). Start a fresh conversation and
workspace for every H task. Setup argv arrays are harness-only and do not count
against the model's call budget. H02 also requires the locked development
environment with `pytest` present so sktime can resolve the sklearn
`LinearRegression()` name inside the CLI spec; `pmdarima` remains absent.

The shared scorer detects this suite from `suite_id`:

```bash
python benchmarks/score.py runs/model-hard.json
python benchmarks/score.py runs/model-a-hard.json runs/model-b-hard.json
```

The hard suite is scored out of 60. Do not combine its ranking table with the
foundation suite, which has a different task count and difficulty.
