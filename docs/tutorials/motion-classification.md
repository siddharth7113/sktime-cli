# Classify motion from wearable sensors

The oil price tutorial forecast one series forward in time. This one does the
other common job: given many short series, label each one.

The data is `basic_motions`, which ships with sktime. People wore a smartwatch
while playing badminton, running, standing, or walking, and the watch recorded
six channels of accelerometer and gyroscope data. Eighty recordings, four
activities, and the task is to name the activity.

Everything runs offline, in under a minute.

## Look at the dataset before loading it

sktime's dataset objects carry their shape as metadata, so you can check what
you have without loading it:

```bash
sktime-cli datasets describe basic_motions
```

```{code-block} text
:caption: Output

name               basic_motions
source             builtin
task               classifier
installable        true
n_splits           1
task_type          ["classifier"]
is_univariate      false
n_instances        80
n_instances_train  40
n_instances_test   40
n_classes          4
reserved_params    ["return_mtype"]
X_shape            [80, 6]
classes            ["badminton", "running", "standing", "walking"]
```

Two fields shape everything that follows:

- `is_univariate` is false and `X_shape` ends in 6, so each recording has six
  channels. Many sktime classifiers handle only one, so that rules most of
  them out.
- `n_splits` is 1, so the dataset defines its own train and test split.

## Load the predefined split

```bash
sktime-cli datasets load basic_motions --split train -o motions_train.ts
sktime-cli datasets load basic_motions --split test -o motions_test.ts
```

```{code-block} text
:caption: Output

dataset      basic_motions
source       builtin
task         classifier
n_instances  40
classes      ["badminton", "running", "standing", "walking"]
files        ["motions_train.ts"]
```

Panel data writes as `.ts`, sktime's own format, which holds the nested series
and the class labels in one file. `data inspect` reads it back:

```bash
sktime-cli data inspect motions_train.ts
```

```{code-block} text
:caption: Output

path      motions_train.ts
scitype   Panel
mtype     nested_univ
shape     [40, 6]
metadata  {"dtypekind_dfip": [2, 2, 2, 2, 2, 2], "feature_kind": [2, 2, 2, 2, 2, 2],
          "feature_names": ["dim_0", "dim_1", "dim_2", "dim_3", "dim_4", "dim_5"], "has_nans":
          false, "is_empty": false, "is_equal_length": true, "is_equally_spaced": true,
          "is_one_panel": true, "is_one_series": false, "is_univariate": false, "n_features": 6,
          "n_instances": 40, "n_panels": 1}
index     {"type": "RangeIndex", "dtype": "int64", "start": "0", "end": "39"}
labels    {"n": 40, "classes": ["badminton", "running", "standing", "walking"]}
```

The scitype is `Panel`, not `Series`. That word routes the rest of the
workflow: `run fit` calls `fit(X, y)` instead of `fit(y, X, fh)`, `run
predict` wants data rather than a horizon, and `run evaluate` splits across
recordings rather than across time.

## Let the registry rule out the wrong estimators

Reaching for a well-known classifier and finding out it can't read your data
is the slow route:

```bash
sktime-cli run evaluate "TimeSeriesForestClassifier(n_estimators=50)" \
    --data motions_train.ts \
    --cv "KFold(n_splits=5, shuffle=True, random_state=42)" \
    --metric accuracy_score
```

```{code-block} text
:caption: Output

error (sktime_error): ValueError: Data seen by TimeSeriesForestClassifier instance has multivariate
series, but this TimeSeriesForestClassifier instance cannot handle multivariate series. Calls with
multivariate series may result in error or unreliable results.
```

Each capability that could stop a run is a tag in sktime's registry, and
`registry search` filters on tags. Ask for classifiers that take multivariate
input and whose dependencies you have:

```bash
sktime-cli registry search classifier \
    -t capability:multivariate=true \
    --installable-only
```

```{code-block} text
:caption: Output

 name                               scitypes        module                              installable
 BaggingClassifier                  ["classifier"]  sktime.classification.ensemble._b…  true
 ColumnEnsembleClassifier           ["classifier"]  sktime.classification.compose._co…  true
 DummyClassifier                    ["classifier"]  sktime.classification.dummy._dummy  true
 KNeighborsTimeSeriesClassifier     ["classifier"]  sktime.classification.distance_ba…  true
 MultiplexClassifier                ["classifier"]  sktime.classification.compose._mu…  true
 ProbabilityThresholdEarlyClassif…  ["classifier"]  sktime.classification.early_class…  true
 RandomIntervalClassifier           ["classifier"]  sktime.classification.feature_bas…  true
 SklearnClassifierPipeline          ["classifier"]  sktime.classification.compose._pi…  true
 SummaryClassifier                  ["classifier"]  sktime.classification.feature_bas…  true
 TSCGridSearchCV                    ["classifier"]  sktime.classification.model_selec…  true
 TimeSeriesSVC                      ["classifier"]  sktime.classification.kernel_base…  true
 WeightedEnsembleClassifier         ["classifier"]  sktime.classification.ensemble._w…  true
12 result(s)
```

`TimeSeriesForestClassifier` is not on that list. That is the answer you
wanted before the run, not after it.

`--installable-only` matters too. Drop it and the list grows to include
estimators such as `RocketClassifier` that need packages you might not have.
Your list will differ from this one, because it reflects your environment.

## Compare three classifiers

Pick a floor, a strong classic, and a cheap feature-based method:

```bash
for spec in \
    "DummyClassifier()" \
    "KNeighborsTimeSeriesClassifier(n_neighbors=3)" \
    "SummaryClassifier(random_state=42)"
do
    score=$(sktime-cli run evaluate "$spec" \
        --data motions_train.ts \
        --cv "KFold(n_splits=5, shuffle=True, random_state=42)" \
        --metric accuracy_score \
        --json | jq -r '.aggregate.test_accuracy_score.mean')
    printf '%-45s %s\n' "$spec" "$score"
done
```

```{code-block} text
:caption: Output

DummyClassifier()                             0.1
KNeighborsTimeSeriesClassifier(n_neighbors=3) 0.925
SummaryClassifier(random_state=42)            1.0
```

Panel folds are drawn across recordings, not across time, so `--cv` takes
sklearn's splitters by name. `--metric` names a function in `sklearn.metrics`,
falling back to sktime's registry, which is why `accuracy_score` works and a
forecasting metric would not.

The dummy scoring 0.1 instead of the 0.25 you would expect from four equal
classes is not a bug. It predicts the most frequent class in each training
fold. The full dataset is balanced, so a class over-represented in a fold's
training half is under-represented in its test half. Below chance is the
normal result on a small balanced dataset.

`SummaryClassifier` is the surprise. It ignores the shape of each series and
reduces every channel to seven statistics: mean, standard deviation, min, max,
and three quartiles. That gives 42 numbers per recording, which go to a random
forest. It costs far less than the distance-based nearest neighbour method,
and here it scores higher:

```bash
sktime-cli run evaluate "SummaryClassifier(random_state=42)" \
    --data motions_train.ts \
    --cv "KFold(n_splits=5, shuffle=True, random_state=42)" \
    --metric accuracy_score
```

```{code-block} text
:caption: Output

 index  test_accuracy_score             fit_time             pred_time
 0                      1.0  0.22661223000068276  0.043316264998793486
 1                      1.0  0.23104047699962393   0.04487344200060761
 2                      1.0  0.23069391599892697   0.04524112800027069
 3                      1.0    0.232652168999266  0.045247990999996546
 4                      1.0  0.23136428100042394   0.04504177800117759
test_accuracy_score.mean  1.0
test_accuracy_score.std   0.0
```

:::{caution}
Treat a perfect score as a warning. `basic_motions` contrasts four activities
that differ widely in how much the watch moves, so separating them takes
little work. Read this as a demonstration of the workflow, not as evidence
about any classifier.
:::

## Fit and predict

```bash
sktime-cli run fit "SummaryClassifier(random_state=42)" \
    --data motions_train.ts \
    --model-out motion.zip
```

```{code-block} text
:caption: Output

model      motion.zip
estimator  SummaryClassifier(random_state=42)
scitype    classifier
n_obs      40
```

There is no `cutoff` field, because a classifier has no notion of where the
training data ended in time. Prediction takes recordings, not a horizon:

```bash
sktime-cli run predict --model motion.zip --data motions_test.ts
```

```{code-block} text
:caption: Output

 index  prediction
 0        standing
 1        standing
 2        standing
 3        standing
 4        standing
 5        standing
 6        standing
 7        standing
 8        standing
```

The test file is ordered by class, so the first rows are all one activity.

## Ask for probabilities instead

A single label hides how sure the model is. For anything that feeds a
decision, ask for the distribution:

```bash
sktime-cli run predict --model motion.zip --data motions_test.ts --proba
```

```{code-block} text
:caption: Output

 index  badminton  running  standing  walking
 0           0.11    0.015      0.65    0.225
 1            0.0      0.0     0.975    0.025
 2          0.015     0.01     0.815     0.16
 3            0.0      0.0      0.99     0.01
 4            0.0      0.0      0.98     0.02
 5            0.0      0.0     0.985    0.015
 6            0.0      0.0      0.99     0.01
```

One column per class, in the order `datasets describe` reported. Recording 0
is the row to look at: the model calls it standing at 0.65, but puts 0.225 on
walking. The rest are near-certain. Route row 0 to a human.

Only classifiers tagged `capability:predict_proba` can do this, and the tag is
searchable like any other:

```bash
sktime-cli registry search classifier \
    -t capability:predict_proba=true \
    -t capability:multivariate=true \
    --installable-only
```

## A note on scoring held-out predictions

`metrics score` covers sktime's forecasting metrics, so it will not take
`accuracy_score`:

```bash
sktime-cli metrics score --true motions_test.ts --pred preds.csv --metric accuracy_score
```

```{code-block} text
:caption: Output

error (not_found): unknown metric: accuracy_score
hint: accuracy_score is an sklearn metric, for classifiers and regressors; score those
with: sktime-cli run evaluate --metric accuracy_score
```

For classifiers, score with `run evaluate`. It holds the labels and the
predictions in one process, so it can apply any metric from `sklearn.metrics`.
Use `run predict` when you want the labels as an artifact, and `run evaluate`
when you want a number.

## What to read next

- [Forecast crude oil prices](oil-prices.md) for the same loop applied to a
  single series over time.
- [Finding estimators](../guide/discovery.md) for the full set of tag filters.
- [Working with data](../guide/data.md) for long-format panels and the `.ts`
  format.
