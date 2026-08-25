# Tutorials

Each tutorial is one problem worked start to finish, with every command and
the output it produces. Work through one in a terminal and you end up with a
fitted model and a scored forecast.

The user guide covers one command group at a time. These pages follow a single
problem through, which is where you see how the commands fit together.

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} {octicon}`graph;1.5em;sd-mr-1` Forecast crude oil prices
:link: oil-prices
:link-type: doc

Fetch a real price series, hold out a year, backtest four forecasters against
a baseline, and score the winner on data it never saw.
:::

:::{grid-item-card} {octicon}`pulse;1.5em;sd-mr-1` Classify motion from sensors
:link: motion-classification
:link-type: doc

Six channels of smartwatch data, four activities. Use registry tags to rule
out estimators that can't read it, then fit and predict.
:::

:::{grid-item-card} {octicon}`dependabot;1.5em;sd-mr-1` Set up an agent
:link: agent-setup
:link-type: doc

Install the CLI and its bundled skill file, check the agent sees it, then
hand it a forecasting task.
:::

::::

## Which one first

If you have never run `sktime-cli`, start with the
[Quickstart](../quickstart.md). It is shorter and covers the commands these
pages assume.

After that:

[Forecast crude oil prices](oil-prices.md)
: Read this one if you read only one. It covers the full loop, from a
  downloaded CSV to a scored forecast, and spends most of its time on holding
  data back, checking a baseline, and reading a backtest.

[Classify motion from wearable sensors](motion-classification.md)
: Read this if your data is many short series rather than one long one. It
  runs offline in under a minute, and shows how registry tags answer "will
  this estimator work on my data" before you spend a run finding out.

[Set up an agent to drive the CLI](agent-setup.md)
: Read this if you would rather describe the task than type the commands. It
  is also the quickest way to see the JSON contract in use.

```{toctree}
:hidden:

oil-prices
motion-classification
agent-setup
```
