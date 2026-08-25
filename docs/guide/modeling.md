# Fitting and evaluating models

The `run` command group covers the whole modeling loop: fit an estimator,
save it, predict from it, and backtest it. Estimators are named with spec
strings, which is the one piece of syntax the CLI adds.

## Spec strings

A spec string is a constructor expression written the way you would write it
in Python:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --model-out model.zip
```

```{code-block} text
:caption: Output

model      model.zip
estimator  NaiveForecaster(sp=12)
scitype    forecaster
n_obs      144
cutoff     1960-12
```

Compositions use sktime's own operators, so a spec can build a pipeline or a
multiplexer without any extra syntax:

```bash
# pipeline: deseasonalize, then forecast
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" --data airline
```

```{code-block} text
:caption: Output

model      ~/.cache/sktime-cli/models/TransformedTargetForecaster-20260825T123647Z.zip
estimator  TransformedTargetForecaster(steps=[Deseasonalizer(), NaiveForecaster()])
scitype    forecaster
n_obs      144
cutoff     1960-12
```

Read the `estimator` field back. It shows the object the operator built, so
you can check the composition is the one you meant.

```bash
# multiplexer: switch between components
sktime-cli run fit "NaiveForecaster() | ThetaForecaster()" --data airline
```

```{code-block} text
:caption: Output

estimator  MultiplexForecaster(forecasters=[NaiveForecaster(), ThetaForecaster()])
```

```bash
# union: combine two transformers into one feature set
sktime-cli run fit "(Detrender() + Deseasonalizer()) * NaiveForecaster()" \
    --data airline
```

```{code-block} text
:caption: Output

estimator  TransformedTargetForecaster(steps=[FeatureUnion(transformer_list=[Detrender(),
                                                                        Deseasonalizer()]),
                                             NaiveForecaster()])
```

`+` unions transformers; forecasters don't define it. Ensembles are a class
rather than an operator, and a class name is just as usable in a spec:

```bash
sktime-cli run evaluate \
    "EnsembleForecaster([('ets', AutoETS()), ('naive', NaiveForecaster())])" \
    --data airline --fh 1:12
```

```{code-block} text
:caption: Output

 index  test_MeanAbsoluteP…              fit_time            pred_time  len_train_window     cutoff
 0      0.17817010994850294  0.021048982998763677  0.0081134149986610…                72  "1954-12"
 1       0.1537903457373945  0.008938749000662938  0.0070289449995470…                73  "1955-01"
 2       0.1889113689511723  0.008568956000090111  0.0069272339987946…                74  "1955-02"
 ...
 60     0.14251616711860282  0.008715521998965414  0.0067017609999311…               132  "1959-12"
test_MeanAbsolutePercentageError.mean  0.16345737250822012
test_MeanAbsolutePercentageError.std   0.05469545873725654
```

61 folds, because without `--initial-window` or `--cv` the default splitter
advances one observation at a time. To control that, see [Backtest with run
evaluate](#backtest-with-run-evaluate).

Names are resolved against the cached registry, so anything `registry search`
finds is usable in a spec. Only the modules you actually name get imported. If
an estimator's dependencies are missing, the command exits with code `3` and a
hint naming the install command.

Specs are evaluated in a namespace that holds only the resolved sktime classes
and a small set of safe builtins. Imports, attribute access, and file access
don't work inside a spec. For the details, see
[Design](../contributing/design.md).

### Override parameters

`--set key=value` applies overrides through scikit-learn's `set_params`, so
the `__` convention reaches nested components. The flag is repeatable:

```bash
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" \
    --data airline \
    --set NaiveForecaster__sp=4 \
    --set NaiveForecaster__strategy=mean
```

```{code-block} text
:caption: Output

estimator  TransformedTargetForecaster(steps=[Deseasonalizer(),
                                             NaiveForecaster(sp=4, strategy='mean')])
```

Components are addressed by class name. Getting that wrong is a usage error,
not a silent no-op, and the hint lists every key the composition accepts:

```bash
sktime-cli run fit "Deseasonalizer() * NaiveForecaster()" \
    --data airline \
    --set forecaster__strategy=mean
```

```{code-block} text
:caption: Output

error (usage): invalid --set parameter: 'forecaster'
hint: valid params: steps, Deseasonalizer, NaiveForecaster, Deseasonalizer__model,
Deseasonalizer__sp, NaiveForecaster__sp, NaiveForecaster__strategy, NaiveForecaster__window_length
```

Use `--set` when you want to sweep one parameter without rewriting the spec.

## Fit a model

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --model-out model.zip
```

```{code-block} text
:caption: Output

model      model.zip
estimator  NaiveForecaster(sp=12)
scitype    forecaster
n_obs      144
cutoff     1960-12
```

`cutoff` is the last time index the model saw. Horizons count from there.
Classifiers have no cutoff, so the field is absent for them.

`--data` takes a file path or a dataset name. A path is read as a file and a
local `airline.csv` shadows the built-in `airline` dataset.

The other input options match the ones in [Working with data](data.md):
`--target COL` picks the target from a multi-column file, `--exog PATH` adds
exogenous data, and `--index-col` and `--freq` control indexing.

`run fit` dispatches by scitype. Forecasters are fitted as `fit(y, X, fh)`,
so passing `--fh` at fit time is meaningful for estimators that need the
horizon up front. Panel scitypes, meaning classifiers, regressors, and
clusterers, are fitted as `fit(X, y)`.

If you omit `--model-out`, the model goes to the `models/` directory in the
workspace and the CLI prints the path.

## Predict

```bash
sktime-cli run predict --model model.zip --fh 1:12
```

```{code-block} text
:caption: Output

 index    Number of airline passengers
 1961-01                         417.0
 1961-02                         391.0
 1961-03                         419.0
 1961-04                         461.0
 1961-05                         472.0
 1961-06                         535.0
 1961-07                         622.0
 1961-08                         606.0
 1961-09                         508.0
 1961-10                         461.0
 1961-11                         390.0
 1961-12                         432.0
```

`--fh` accepts `1:12`, `1,2,12`, or `6`, always relative to the end of
training. For panel models, pass the data to predict on with `--data`. For
forecasters, `--data` supplies exogenous values instead.

`--proba` returns class probabilities for classifiers. `--output PATH` writes
the predictions to a file instead of stdout, in the format the suffix names.

### Uncertainty around a forecast

Four flags turn a point forecast into a probabilistic one:

```bash
sktime-cli run predict --model model.zip --fh 1:12 --interval 0.8,0.95
sktime-cli run predict --model model.zip --fh 1:12 --quantiles 0.1,0.9
sktime-cli run predict --model model.zip --fh 1:12 --var
sktime-cli run predict --model model.zip --data airline.csv --residuals
```

The first of those, on the model fitted above:

```{code-block} text
:caption: Output

 time                         variable  coverage  bound               value
 1961-01  Number of airline passengers       0.8  lower  370.45950016906335
 1961-01  Number of airline passengers       0.8  upper  463.54049983093665
 1961-01  Number of airline passengers      0.95  lower   345.8224477706716
 1961-01  Number of airline passengers      0.95  upper   488.1775522293284
 1961-02  Number of airline passengers       0.8  lower  344.45950016906335
 1961-02  Number of airline passengers       0.8  upper  437.54049983093665
 ...
```

Two coverages produce four rows per timestamp, not four columns.

They are mutually exclusive. sktime returns intervals and quantiles with
MultiIndex columns, whose shape changes with the number of levels you ask for.
The CLI flattens them to long form instead, so the columns are fixed:

| flag | columns |
| --- | --- |
| `--interval` | `time`, `variable`, `coverage`, `bound`, `value` |
| `--quantiles` | `time`, `variable`, `quantile`, `value` |
| `--var` | `time`, `variable`, `value` |

The first column is the time index, named `time` when the input had no index
name. For panel input it is the index levels instead.

`--quantiles` swaps the `coverage` and `bound` pair for a single `quantile`
column:

```{code-block} text
:caption: Output

 time                         variable  quantile               value
 1961-01  Number of airline passengers       0.1  370.45950016906335
 1961-01  Number of airline passengers       0.9  463.54049983093665
 1961-02  Number of airline passengers       0.1  344.45950016906335
 1961-02  Number of airline passengers       0.9  437.54049983093665
 ...
```

and `--var` drops to one row per timestamp:

```{code-block} text
:caption: Output

 time                         variable               value
 1961-01  Number of airline passengers  1318.8333333333333
 1961-02  Number of airline passengers  1318.8333333333333
 ...
```

Asking for three coverages instead of one adds rows, never columns, which is
what makes the output safe to parse. Pass `--wide` if you want sktime's native
layout instead, with the column levels joined by `__`.

Not every forecaster can do this. The ones that can carry the
`capability:pred_int` tag, and the others fail with a usage error that names
it:

```bash
sktime-cli registry search forecaster -t capability:pred_int=True --installable-only
```

To do both steps in one process, use `run fit-predict`. It takes the fit
options plus `--output`, and forecasters require `--fh`:

```bash
sktime-cli run fit-predict "NaiveForecaster(sp=12)" \
    --data airline.csv \
    --fh 1:12 \
    --output forecast.csv
```

```{code-block} text
:caption: Output

files  ["forecast.csv"]
n      12
```

When a command writes files, the result is the manifest, not the data. That
keeps the output parsable whatever `--output` points at.

## Transform data

Transformers are the largest family in sktime. `run transform` fits one and
applies it in a single step:

```bash
sktime-cli run transform "Detrender()" --data airline.csv --output detrended.csv
```

```{code-block} text
:caption: Output

files  ["detrended.csv"]
n      144
```

Pass `--model-out` to keep the fitted transformer, then reuse it on new data
with `--model` instead of a spec. That distinction matters: refitting a
transformer on new data would learn new parameters, while reloading applies
the ones learned before.

```bash
sktime-cli run transform "Differencer()" --data train.csv --model-out diff.zip -o out.csv
sktime-cli run transform --model diff.zip --data test.csv -o test_diff.csv
sktime-cli run transform --model diff.zip --data test_diff.csv --inverse
```

`--inverse` calls `inverse_transform`, which needs the
`capability:inverse_transform` tag; transformers without it fail with a usage
error rather than an sktime traceback.

Reconcilers are transformers in sktime's class hierarchy, so hierarchical
reconciliation runs through this command too.

## Detect anomalies, change points, and segments

```bash
sktime-cli run detect "HampelDetector()" --data airline.csv
```

```{code-block} text
:caption: Output

 index  ilocs
 0         67
 1         79
 2         91
 3        103
 4        115
 5        127
kind: points
```

`ilocs` are positions in the series, not timestamps. The trailing `kind` line
says which of the detector's two prediction methods ran.

```bash
sktime-cli run detect "ClusterSegmenter()" --data airline.csv --kind segments
```

```{code-block} text
:caption: Output

 index    ilocs
 1949-01      0
 1949-02      0
 1949-03      0
 ...
```

Segmenters label every observation with the segment it belongs to, so the
result is as long as the input.

`--kind` defaults to `auto`, which reads the detector's `task` tag and picks
`predict_points` for anomaly and change point detectors, `predict_segments`
for segmenters. Detectors that return segments as intervals are flattened to
`start` and `end` columns so the result survives a CSV round trip.

Discover what is available, and what each one does, with the `task` tag:

```bash
sktime-cli registry search detector --with-tags task --installable-only
```

```{code-block} text
:caption: Output

 name                    scitypes      module                   installable  task
 BinarySegmentation      ["detector"]  sktime.detection.bs      true         change_point_detection
 CAPA                    ["detector"]  sktime.detection.capa    true         segmentation
 CircularBinarySegment…  ["detector"]  sktime.detection.circu…  true         segmentation
 ClusterSegmenter        ["detector"]  sktime.detection.clust   true         segmentation
 DetectorPipeline        ["detector"]  sktime.detection.compo…  true         None
 DummyRegularAnomalies   ["detector"]  sktime.detection.dummy…  true         anomaly_detection
 GreedyGaussianSegment…  ["detector"]  sktime.detection.ggs     true         segmentation
 HampelDetector          ["detector"]  sktime.detection.hampel  true         anomaly_detection
 MovingWindow            ["detector"]  sktime.detection.movin…  true         change_point_detection
 ...
```

## Backtest with run evaluate

`run evaluate` scores an estimator over a rolling split. The simple form
derives the splitter from a horizon:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline \
    --fh 1:12 \
    --metric MeanAbsolutePercentageError
```

```{code-block} text
:caption: Output

 index  test_MeanAbsoluteP…              fit_time            pred_time  len_train_window     cutoff
 0      0.15666934262154927  0.00151077800001075…  0.0115759139989677…                72  "1954-12"
 ...
test_MeanAbsolutePercentageError.mean  0.104007700568499
test_MeanAbsolutePercentageError.std   0.036494730005964454
```

Add `--initial-window N` to set how much data the first fold trains on.

For full control, pass a splitter as a spec string with `--cv`:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" \
    --data airline \
    --cv "ExpandingWindowSplitter(initial_window=72, step_length=12, fh=[1,2,3])" \
    --metric MeanAbsolutePercentageError
```

```{code-block} text
:caption: Output

 index  test_MeanAbsoluteP…              fit_time            pred_time  len_train_window     cutoff
 0      0.15666934262154927  0.00151077800001075…  0.0115759139989677…                72  "1954-12"
 1      0.15482026530374263  0.001348194000456715  0.0098441819991421…                84  "1955-12"
 2      0.09589915982651807  0.00131347400019876…  0.0099034260001644…                96  "1956-12"
 3      0.0478543722989734…  0.00130262200036668…  0.0101766749994567…               108  "1957-12"
 4      0.07803512612949999  0.00139050799953110…  0.0099195889997645…               120  "1958-12"
 5      0.09767886451997902  0.00129603200002748…  0.0094878910003899…               132  "1959-12"
test_MeanAbsolutePercentageError.mean  0.10515952178337706
test_MeanAbsolutePercentageError.std   0.04308312575349776
```

Six folds instead of 61, each training on a year more than the last. Read the
per-fold column, not just the mean: fold 3 scores three times better than fold
0, and an average hides that spread.

`--cv` and `--fh` are alternatives, so pass one or the other.

`--metric` is repeatable and takes either a metric name or a spec string, so
you can parameterize a metric the same way you parameterize an estimator. The
default is `MeanAbsolutePercentageError`.

`--strategy` takes `refit`, `update`, or `no-update_params`, and controls what
happens to the model between folds.

The output has one row per fold plus an aggregate block:

```bash
sktime-cli run evaluate "NaiveForecaster(sp=12)" --data airline --fh 1:12 --json \
    | jq '.aggregate'
```

```{code-block} text
:caption: Output

{
  "test_MeanAbsolutePercentageError": {
    "mean": 0.104007700568499,
    "std": 0.036494730005964454
  }
}
```

The aggregate holds a `mean` and `std` for each metric, keyed as
`test_<Metric>`.

### Backtesting a classifier

`run evaluate` also cross-validates classifiers and regressors. Panel folds are
drawn across instances rather than across time, so the splitters that fit are
sklearn's, and `--cv` accepts them by name:

```bash
sktime-cli run evaluate "DummyClassifier()" \
    --data train.ts \
    --cv "KFold(n_splits=5)" \
    --metric accuracy_score
```

```{code-block} text
:caption: Output

 index  test_accuracy_score              fit_time              pred_time
 0                      0.0  0.016481469001519145  0.0055144490015663905
 1                      0.0  0.015861926998695708   0.005583571000897791
 2                      0.0  0.015739984999527223  0.0054841199998918455
 3                      0.0  0.015729697999631753  0.0053390749999380205
 4                      0.0  0.015843791001316276  0.0053214180006762035
test_accuracy_score.mean  0.0
test_accuracy_score.std   0.0
```

There is no `cutoff` or `len_train_window` column, because panel folds are
drawn across instances. The zeros are real: `train.ts` here is the
`basic_motions` training split, which is sorted by class, so unshuffled folds
put every instance of a class in either train or test but never both, and a
classifier that predicts the training prior can never be right. Pass
`KFold(n_splits=5, shuffle=True, random_state=42)` to draw folds that mix the
classes.

Without `--cv` the default is 3-fold cross-validation. `--metric` here takes
the name of an `sklearn.metrics` function, falling back to sktime's registry.
A fold that fails is reported as an error rather than a `NaN` score, so a
metric that needs extra arguments tells you so instead of quietly producing an
empty column.

:::{note}
sktime has no cross-validation utility for clusterers or detectors, so
`run evaluate` does not cover them.
:::

## Inspect a saved model

`model inspect` opens a `.zip` artifact and reports its class, spec, params,
and tags:

```bash
sktime-cli model inspect model.zip
```

```{code-block} text
:caption: Output

class      NaiveForecaster
spec       NaiveForecaster(sp=12)
scitype    forecaster
is_fitted  true
params     {"sp": 12, "strategy": "last", "window_length": null}
tags       {"python_version": null, "python_dependencies": null, "env_marker": null,
           "sktime_version": "1.1.0", "property:randomness": "deterministic",
           ...
           "capability:insample": true, "capability:pred_int": true,
           "capability:missing_values": true, "y_inner_mtype": "pd.Series", ...}
cutoff     1960-12
```

`sktime_version` records the version the artifact was written with. Check it
first when a saved model won't load.

`--fitted` adds the fitted parameters. `--spec` prints only the spec string,
and that output is itself a valid spec for `run fit`:

```bash
sktime-cli model inspect model.zip --spec
```

```{code-block} text
:caption: Output

NaiveForecaster(sp=12)
```

```bash
spec=$(sktime-cli model inspect model.zip --spec)
sktime-cli run fit "$spec" --data airline.csv --model-out refit.zip
```

That round trip is the reproducibility loop: a saved model can always tell you
the command that would rebuild it.

## What to read next

- [Output formats and errors](output.md) for the JSON contract and exit codes.
- [CLI reference](../reference/cli/index.md) for every `run` and `model` option.
- [Roadmap](../roadmap.md) for the workflows that aren't covered yet.
