# User guide

These pages cover the CLI task by task. Each one is self-contained, so you can
read the one that matches what you're doing.

Every command is shown with the output it produces. Long listings are cut,
marked with `...`, and the result count at the end of the block is the real
one. Counts that depend on your sktime version or your installed packages
differ in your terminal.

[Finding estimators](discovery.md)
: Search sktime's registry by scitype, name, and capability tag, and read an
  estimator's parameters, tags, and dependencies before you use it.

[Working with data](data.md)
: Load built-in and remote datasets, inspect an unfamiliar file, convert
  between formats, and split a series for backtesting. Includes the index and
  format conventions the CLI applies.

[Fitting and evaluating models](modeling.md)
: Spec strings, pipelines and ensembles, parameter overrides, saved model
  artifacts, and backtesting with `run evaluate`.

[Scoring, checking, and catalogues](scoring.md)
: Score predictions against observations, validate an object against sktime's
  API contract, and browse the benchmark catalogues sktime ships.

[Output formats and errors](output.md)
: The five output formats, the stdout and stderr split, the structured error
  record, and the exit code table.

[Using sktime-cli from an agent](agents.md)
: The JSON contract an agent should follow, and the skill file that teaches
  an agent to use the CLI.

```{toctree}
:hidden:

discovery
data
modeling
scoring
output
agents
```
