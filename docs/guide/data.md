# Working with data

sktime reads its own `.ts`, `.tsf`, and `.arff` formats, but it has no csv or
parquet ingestion. `sktime-cli` adds that layer, with conventions that are
documented rather than guessed. This page covers where data comes from, how
files are read, and how to prepare them for a run.

## Load a built-in or remote dataset

`datasets list` shows what's available:

```bash
sktime-cli datasets list --source builtin
sktime-cli datasets list --task classification -n arrow
```

`--source` takes `builtin`, `ucr`, `tsf`, `fpp3`, or `objects`. `--task`
takes `forecasting`, `classification`, or `regression`. `-n` matches a
substring of the name.

`datasets describe` reports the shape and classes of a built-in dataset, or a
source note for a remote one. It never downloads:

```bash
sktime-cli datasets describe airline
```

`datasets load` fetches a dataset and writes it to disk:

```bash
sktime-cli datasets load airline --output airline.csv
```

The command prints a manifest of exactly which files it wrote. Panel datasets
write as `.ts`. MultiIndex forecasting data writes as long-format csv. When a
dataset has exogenous data, `X` lands next to `y` as `<stem>_X<suffix>`.

### Dataset names

Dataset IDs are namespaced. A bare name resolves against the built-in
datasets first, then case-insensitively across the remote sources:

```bash
sktime-cli datasets load airline           # built in, works offline
sktime-cli datasets load ucr:ArrowHead     # downloads from the UCR archive
sktime-cli datasets load tsf:m1_yearly_dataset
sktime-cli datasets load fpp3:aus_arrivals
```

An explicit prefix pins the source. An unknown name produces suggestions, and
an ambiguous bare name lists the namespaced candidates instead of picking one.

Remote downloads land inside the workspace directory, so `sktime-cli cache
clear` reclaims the space. For where that directory is, see [Environment and
workspace](../reference/environment.md).

## Inspect a file

When you have a file and want to know what sktime makes of it, use `data
inspect`:

```bash
sktime-cli data inspect airline.csv
```

The command routes the file through sktime's `check_is_scitype` and reports
the scitype, the mtype, the shape, the index details, and metadata such as
whether values are missing. When an agent is handed an unfamiliar file, this
is the designed first move.

## How files are read

The following conventions apply to every command that takes a data file,
including `data inspect`, `data convert`, `data split`, and the `run`
commands.

Time index
: The first column is the time index. Use `--index-col NAME` to name a
  different column, or `--index-col none` to disable indexing. A
  datetime-looking index becomes a pandas `PeriodIndex`, using `--freq` if you
  pass one and an inferred frequency otherwise. An integer index is used as
  it is.

Series versus frame
: After indexing, a single remaining column is squeezed to a `Series`. Files
  with more columns stay a `DataFrame`, and the `run` commands take `--target
  COL` to pick the target from one.

Long-format panels
: Pass `--long` with `--id-col` and `--time-col` to read long-format panel
  data. The result is sktime's `pd-multiindex` mtype.

JSON
: JSON uses the pandas split orient, `{"index", "columns", "data"}`, in both
  directions. It's the one JSON shape that round-trips an index without loss.

sktime formats
: `.ts`, `.tsf`, and `.arff` are handed to sktime's own readers.

parquet
: parquet needs the `parquet` extra. Without it, the command exits with code
  `3` and a hint naming the install command.

To override format detection, pass `--input-format
csv|parquet|json|ts|tsf|arff`.

## Convert between formats

`data convert` changes the file format, the sktime mtype, or both:

```bash
sktime-cli data convert airline.csv --output airline.parquet
sktime-cli data convert airline.csv --output airline.json --to json
sktime-cli data convert panel.ts --output panel.csv --to-mtype pd-multiindex
```

`--to` names the output format when the output suffix doesn't already say it.
`--to-mtype` converts the in-memory representation before writing. Writing to
`.npy` produces a numpy array and accepts no other suffix.

## Split a series for backtesting

`data split` cuts a series temporally and writes a train file and a test
file:

```bash
sktime-cli data split airline.csv --test-size 12
```

Size the test set in one of three ways, and pass only one of them:

- `--test-size N` holds out the last `N` observations.
- `--test-size 0.2` holds out the last 20 percent.
- `--fh 1:12` derives the test set from a forecasting horizon.

`--train-size` caps the training set, which is useful when you want a fixed
window rather than everything before the split. `--exog PATH` splits an
exogenous file at the same point.

By default the outputs are named after the input, as `<stem>_train<suffix>`
and `<stem>_test<suffix>`. Use `--train-out` and `--test-out` to choose your
own paths.

## Horizon syntax

`--fh` accepts three forms, and always means a horizon relative to the end of
the training data:

- `1:12` is an inclusive range, so steps 1 through 12.
- `1,2,12` is an explicit list.
- `6` is a single step.

## What to read next

- [Fitting and evaluating models](modeling.md) to use these files in a run.
- [CLI reference](../reference/cli.md) for every option on `datasets` and
  `data`.
