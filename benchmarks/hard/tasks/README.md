# Hard task reviewer catalog

These files document the end-to-end H01-H06 scenarios. They contain expected
results and must never be supplied to benchmarked models.

| ID | Scenario | Detail |
|---|---|---|
| [H01](H01.md) | Forecasting tournament | Three-model CV, selection, deployment |
| [H02](H02.md) | Exogenous pipeline | Paired y/X lifecycle and model comparison |
| [H03](H03.md) | Classifier assessment | Honest boundary when scoring is unavailable |
| [H04](H04.md) | Artifact reproduction | Spec round-trip and nested mutation |
| [H05](H05.md) | Production incident | Dependency recovery plus four missing features |
| [H06](H06.md) | Hierarchical forecast | MultiIndex preservation and CSV flattening |

The machine-readable [`../prompts.json`](../prompts.json) and
[`../scoring.json`](../scoring.json) remain canonical. Change task details and
JSON together, then increment the suite version.
