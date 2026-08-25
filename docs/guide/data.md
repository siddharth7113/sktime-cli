# Working with data

sktime reads its own `.ts`, `.tsf`, and `.arff` formats, but it has no csv or
parquet ingestion. `sktime-cli` adds that layer, with conventions that are
documented rather than guessed. This page covers where data comes from, how
files are read, and how to prepare them for a run.

## Load a built-in or remote dataset

`datasets list` shows what's available:

```bash
sktime-cli datasets list --source builtin
```

```{code-block} text
:caption: Output

 name                        source   task        offline  installable
 acsf1                       builtin  classifier  true     true
 airline                     builtin  forecaster  true     true
 arrow_head                  builtin  classifier  true     true
 basic_motions               builtin  classifier  true     true
 gun_point                   builtin  classifier  true     true
 hierarchical_sales_toydata  builtin  forecaster  true     true
 ...
 m5_forecasting_accuracy     builtin  forecaster  false    true
 ...
21 result(s)
```

Check `offline` before running without a network: `false` means the dataset
downloads on first use.

```bash
sktime-cli datasets list --task classifier -n arrow
```

```{code-block} text
:caption: Output

 name           source   task        offline  installable
 arrow_head     builtin  classifier  true     true
 ucr:ArrowHead  ucr      classifier  false    true
2 result(s)
```

`--source` takes `builtin`, `ucr`, `tsf`, or `fpp3`. `--task` takes sktime's
scitype names, `forecaster`, `classifier`, or `regressor`, so it reads the same
way as `registry search`. `-n` matches a substring of the name.

`datasets describe` reports the tags and shape of a built-in dataset, or a
source note for a remote one. It never downloads:

```bash
sktime-cli datasets describe airline
```

```{code-block} text
:caption: Output

name                airline
source              builtin
task                forecaster
installable         true
n_splits            0
task_type           ["forecaster"]
is_univariate       true
is_equally_spaced   true
has_nans            false
has_exogenous       false
n_instances         1
n_timepoints        144
frequency           M
n_dimensions        1
is_one_series       true
shape               [144]
index_type          PeriodIndex
```

`datasets load` fetches a dataset and writes it to disk:

```bash
sktime-cli datasets load airline --output airline.csv
```

```{code-block} text
:caption: Output

dataset  airline
source   builtin
task     forecaster
shape    [144]
files    ["airline.csv"]
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

The built-in names are the `name` tags sktime's own dataset objects declare,
not a list maintained here, so a dataset added upstream is available with no
change to the CLI. That also means the spelling is sktime's: `gun_point`
rather than `gunpoint`, `hierarchical_sales_toydata` rather than
`hierarchical_sales`.

Because those objects carry their shape and frequency as tags, `datasets
describe` can answer without reading the data at all:

```bash
sktime-cli datasets describe airline --no-load
```

```{code-block} text
:caption: Output

name                airline
source              builtin
task                forecaster
installable         true
n_splits            0
task_type           ["forecaster"]
is_univariate       true
is_equally_spaced   true
has_nans            false
has_exogenous       false
n_instances         1
n_timepoints        144
frequency           M
n_dimensions        1
is_one_series       true
```

The same record without `shape` and `index_type`, the two fields that require
loading the data.

That reports the task, frequency, length, dimensionality, whether the series
is univariate and equally spaced, whether it has exogenous columns, and how
many splits it defines. Drop `--no-load` to add the loaded shape and, for
classification datasets, the class labels.

Remote downloads land inside the workspace directory, so `sktime-cli cache
clear` reclaims the space. For where that directory is, see [Environment and
workspace](../reference/environment.md).

## Inspect a file

When you have a file and want to know what sktime makes of it, use `data
inspect`:

```bash
sktime-cli data inspect airline.csv
```

```{code-block} text
:caption: Output

path      airline.csv
scitype   Series
mtype     pd.Series
shape     [144]
metadata  {"dtypekind_dfip": [2], "feature_kind": [2], "feature_names": ["Number of airline
          passengers"], "has_nans": false, "is_empty": false, "is_equally_spaced": true,
          "is_univariate": true, "n_features": 1}
index     {"type": "PeriodIndex", "dtype": "period[M]", "start": "1949-01", "end": "1960-12"}
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
```

```{code-block} text
:caption: Output

input   airline.csv
files   ["airline.parquet"]
mtype
format
```

```bash
sktime-cli data convert airline.csv --output airline.json --to json
```

```{code-block} text
:caption: Output

input   airline.csv
files   ["airline.json"]
mtype
format  json
```

```bash
sktime-cli data convert panel.ts --output panel.csv --to-mtype pd-multiindex
```

```{code-block} text
:caption: Output

input   panel.ts
files   ["panel.csv"]
mtype   pd-multiindex
format
```

The `mtype` and `format` fields report only what you asked to change. A blank
means the conversion left that alone.

`--to` names the output format when the output suffix doesn't already say it.
`--to-mtype` converts the in-memory representation before writing. Writing to
`.npy` accepts only data already converted to a numpy mtype with `--to-mtype`,
for example `--to-mtype numpy3D`.

## Split a series for backtesting

`data split` cuts a series temporally and writes a train file and a test
file:

```bash
sktime-cli data split airline.csv --test-size 12
```

```{code-block} text
:caption: Output

train    airline_train.csv
test     airline_test.csv
n_train  132
n_test   12
files    ["airline_train.csv", "airline_test.csv"]
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

### Cross-validation folds

A single train/test cut is enough for a quick check, but backtesting wants
several. `--cv` takes any splitter from the registry and writes one file pair
per fold:

```bash
sktime-cli data split airline.csv \
    --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])"
```

```{code-block} text
:caption: Output

splitter  ExpandingWindowSplitter(fh=[1, 2, 3], initial_window=72, step_length=12)
n_folds   6
folds     [{"fold": 0, "n_train": 72, "n_test": 3, "train": "airline_fold0_train.csv", "test":
          "airline_fold0_test.csv"}, {"fold": 1, "n_train": 84, "n_test": 3, "train":
          "airline_fold1_train.csv", "test": "airline_fold1_test.csv"}, ...]
files     ["airline_fold0_train.csv", "airline_fold0_test.csv", "airline_fold1_train.csv",
          "airline_fold1_test.csv", ...]
```

`n_train` grows by `step_length` each fold while `n_test` stays at the length
of `fh`. That is what "expanding window" means.

The files are named `<stem>_fold<N>_train<suffix>` and
`<stem>_fold<N>_test<suffix>`, and the command prints a manifest with the fold
count and each fold's sizes and paths. `--cv` replaces the sizing options
rather than combining with them.

Use this when you want the folds on disk, to run something other than
`run evaluate` over them. If you only want scores, `run evaluate --cv` does
the same split in memory. Discover splitters with
`sktime-cli registry search splitter`.

## Horizon syntax

`--fh` accepts three forms, and always means a horizon relative to the end of
the training data:

- `1:12` is an inclusive range, so steps 1 through 12.
- `1,2,12` is an explicit list.
- `6` is a single step.

## What to read next

- [Fitting and evaluating models](modeling.md) to use these files in a run.
- [CLI reference](../reference/cli/index.md) for every option on `datasets` and
  `data`.
