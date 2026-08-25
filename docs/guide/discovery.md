# Finding estimators

sktime ships hundreds of estimators, and which ones you can use depends on
the data you have and the packages you have installed. The `registry` command
group answers both questions from the shell.

## List the object categories

sktime groups objects by scitype, which is its word for the kind of thing an
object is: `forecaster`, `classifier`, `transformer`, `splitter`, and about 20
more. To list them with live object counts, use `registry types`:

```bash
sktime-cli registry types
```

```{code-block} text
:caption: Output

 scitype                     description                                                    count
 aligner                     time series aligner or sequence aligner                        7
 catalogue                   catalogue of datasets, estimators, cv splitters, and metrics.  9
 classifier                  time series classifier                                         77
 clusterer                   time series clusterer                                          10
 dataset                     dataset object                                                 21
 detector                    detector - anomalies, outliers, change points                  28
 forecaster                  time series forecaster                                         153
 metric                      performance metric                                             46
 regressor                   time series regressor                                          30
 splitter                    time series splitter                                           15
 transformer                 time series transformer                                        150
 ...
25 result(s)
```

The counts come from the registry in your environment, so they move with your
sktime version.

Use a scitype from this list as the first argument to `registry search` and
`registry tags`.

## Search the registry

`registry search` takes an optional scitype and filters the registry:

```bash
sktime-cli registry search forecaster
```

```{code-block} text
:caption: Output

 name                               scitypes        module                              installable
 ARARForecaster                     ["forecaster"]  sktime.forecasting.arar._arar_for…  true
 ARCH                               ["forecaster"]  sktime.forecasting.arch._uarch      false
 ARDL                               ["forecaster"]  sktime.forecasting.ardl             true
 ARIMA                              ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 ArpsExponential                    ["forecaster"]  sktime.forecasting.arps_dca         true
 ArpsHarmonic                       ["forecaster"]  sktime.forecasting.arps_dca         true
 ArpsHyperbolic                     ["forecaster"]  sktime.forecasting.arps_dca         true
 AuroraForecaster                   ["forecaster"]  sktime.forecasting.aurora           false
 AutoARIMA                          ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoETS                            ["forecaster"]  sktime.forecasting.ets              true
 ...
153 result(s)
```

Read the `installable` column first: `false` means the estimator exists but
needs packages you don't have.

The first search crawls sktime's registry, which takes a few seconds, and
writes the result to a disk cache. Later searches read the cache. For details
on how the cache is keyed and when it rebuilds, see [Design](../contributing/design.md).

### Filter by capability tag

Tags describe what an estimator can do. Pass `-t KEY=VALUE` to keep only the
objects that carry a tag:

```bash
sktime-cli registry search forecaster -t capability:missing_values=true
```

```{code-block} text
:caption: Output

 name                               scitypes        module                              installable
 ARIMA                              ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoARIMA                          ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoETS                            ["forecaster"]  sktime.forecasting.ets              true
 BaggingForecaster                  ["forecaster"]  sktime.forecasting.compose._baggi…  true
 DirRecTabularRegressionForecaster  ["forecaster"]  sktime.forecasting.compose._reduce  true
 DirRecTimeSeriesRegressionForeca…  ["forecaster"]  sktime.forecasting.compose._reduce  true
 DirectTabularRegressionForecaster  ["forecaster"]  sktime.forecasting.compose._reduce  true
 DirectTimeSeriesRegressionForeca…  ["forecaster"]  sktime.forecasting.compose._reduce  true
 DoubleMLForecaster                 ["forecaster"]  sktime.forecasting.causal._dmlf     true
 DynamicFactor                      ["forecaster"]  sktime.forecasting.dynamic_factor   true
 ...
29 result(s)
```

Repeating `-t` combines the filters with AND. A comma inside a value combines
that value's alternatives with OR:

```bash
sktime-cli registry search forecaster \
    -t capability:missing_values=true \
    -t capability:insample=true
```

```{code-block} text
:caption: Output

 name                               scitypes        module                              installable
 ARIMA                              ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoARIMA                          ["forecaster"]  sktime.forecasting.arima._pmdarima  false
 AutoETS                            ["forecaster"]  sktime.forecasting.ets              true
 BaggingForecaster                  ["forecaster"]  sktime.forecasting.compose._baggi…  true
 DoubleMLForecaster                 ["forecaster"]  sktime.forecasting.causal._dmlf     true
 FallbackForecaster                 ["forecaster"]  sktime.forecasting.compose._fallb…  true
 FhPlexForecaster                   ["forecaster"]  sktime.forecasting.compose._fhplex  true
 ForecastByLevel                    ["forecaster"]  sktime.forecasting.compose._group…  true
 ForecastX                          ["forecaster"]  sktime.forecasting.compose._pipel…  true
 ForecastingPipeline                ["forecaster"]  sktime.forecasting.compose._pipel…  true
 ...
18 result(s)
```

This search keeps forecasters that handle missing values and can also predict
in-sample. Tags are specific to a scitype: filtering on one that no object of
that kind carries is an error, not an empty result, so a typo says so.

To list the tags that apply to a scitype, along with their types and
descriptions, use `registry tags`:

```bash
sktime-cli registry tags forecaster
```

```{code-block} text
:caption: Output

 name                     scitype                  type                     description
 X-y-must-have-same-ind…  ["forecaster",           bool                     do X/y in fit/update
                          "regressor",                                      and X/fh in predict
                          "transformer"]                                    have to be same
                                                                            indices?
 X_inner_mtype            estimator                ('list', 'str')          which machine type(s)
                                                                            is the internal
                                                                            _fit/_predict able to
                                                                            deal with?
 ...
```

The `type` column says what a filter value must look like. Most capability
tags are `bool`, so `-t capability:insample=true` is the common shape.

### Filter by name

`-n` matches a substring of the object name, without regard to case:

```bash
sktime-cli registry search classifier -n rocket
```

```{code-block} text
:caption: Output

 name              scitypes        module                                               installable
 RocketClassifier  ["classifier"]  sktime.classification.kernel_based._rocket_classif…  false
1 result(s)
```

`--exclude NAME` drops objects by exact name, and is repeatable.

### Filter by what you can run

Many estimators need packages that sktime doesn't install. To keep only the
ones whose dependencies are already present, use `--installable-only`:

```bash
sktime-cli registry search classifier --installable-only
```

```{code-block} text
:caption: Output

 name                                scitypes        module                             installable
 BaggingClassifier                   ["classifier"]  sktime.classification.ensemble._…  true
 ClassifierPipeline                  ["classifier"]  sktime.classification.compose._p…  true
 ColumnEnsembleClassifier            ["classifier"]  sktime.classification.compose._c…  true
 ComposableTimeSeriesForestClassif…  ["classifier"]  sktime.classification.ensemble._…  true
 DummyClassifier                     ["classifier"]  sktime.classification.dummy._dum…  true
 ElasticEnsemble                     ["classifier"]  sktime.classification.distance_b…  true
 KNeighborsTimeSeriesClassifier      ["classifier"]  sktime.classification.distance_b…  true
 MatrixProfileClassifier             ["classifier"]  sktime.classification.feature_ba…  true
 ...
20 result(s)
```

20 of sktime's 77 classifiers, in an environment with no optional
classification dependencies. Your count depends on what you have installed.

Without the flag, results carry an `installable` column. A `false` value tells
you an estimator exists but needs more packages, and `registry describe` names
them.

### Shape the output

`--with-tags` adds tags as extra columns, which is useful when you want to
compare candidates on one capability:

```bash
sktime-cli registry search forecaster \
    -t capability:missing_values=true \
    --with-tags "capability:pred_int,capability:insample" \
    --limit 10
```

```{code-block} text
:caption: Output

 name              scitypes        module            installable  capability:pre…  capability:insa…
 ARIMA             ["forecaster"]  sktime.forecast…  false        true             true
 AutoARIMA         ["forecaster"]  sktime.forecast…  false        true             true
 AutoETS           ["forecaster"]  sktime.forecast…  true         true             true
 BaggingForecast…  ["forecaster"]  sktime.forecast…  true         true             true
 DirRecTabularRe…  ["forecaster"]  sktime.forecast…  true         true             false
 DirRecTimeSerie…  ["forecaster"]  sktime.forecast…  true         true             false
 DirectTabularRe…  ["forecaster"]  sktime.forecast…  true         true             false
 DirectTimeSerie…  ["forecaster"]  sktime.forecast…  true         true             false
 DoubleMLForecas…  ["forecaster"]  sktime.forecast…  true         true             true
 DynamicFactor     ["forecaster"]  sktime.forecast…  true         true             false
10 result(s)
```

`--limit N` caps the number of results.

## Describe one estimator

`registry describe` reports the parameters, defaults, tags, dependencies, and
docstring summary for one object:

```bash
sktime-cli registry describe NaiveForecaster
```

```{code-block} text
:caption: Output

name                 NaiveForecaster
module               sktime.forecasting.naive._naive
scitypes             ["forecaster"]
installable          true
python_dependencies  []
params               {"sp": {"default": "1", "required": false}, "strategy": {"default": "'last'",
                     "required": false}, "window_length": {"default": "None", "required": false}}
tags                 {"python_version": null, "python_dependencies": null, "env_marker": null,
                     "sktime_version": "1.1.0", "property:randomness": "deterministic",
                     ...
                     "capability:insample": true, "capability:pred_int": true,
                     "capability:missing_values": true, "y_inner_mtype": "pd.Series", ...}
summary              Forecast based on naive assumptions about past trends continuing.
```

In JSON output, `params` maps each parameter name to its default and whether
it's required, which is what you need to build a spec string:

```bash
sktime-cli registry describe NaiveForecaster --json | jq '.params'
```

```{code-block} text
:caption: Output

{
  "sp": {
    "default": "1",
    "required": false
  },
  "strategy": {
    "default": "'last'",
    "required": false
  },
  "window_length": {
    "default": "None",
    "required": false
  }
}
```

That is enough to write `"NaiveForecaster(sp=12, strategy='last')"` without
opening sktime's API docs.

Two flags change what the command does:

`--test-params`
: Includes the example parameter sets from the estimator's `get_test_params`
  method. These are known-good configurations, so they make good starting
  points.

`--no-doc`
: Skips the docstring. The docstring is the only part that requires importing
  the estimator's module, so this flag makes `describe` faster and lets it
  work when the estimator's dependencies are missing.

When an estimator isn't installable, `describe` adds a `hint` field with the
install command:

```bash
sktime-cli registry describe AutoARIMA --json | jq -r '.hint'
```

```{code-block} text
:caption: Output

uv pip install "pmdarima"
```

## Use what you found

The `name` field from a search is the name you put in a spec string:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --model-out model.zip
```

For how spec strings resolve names and how to compose them, see [Fitting and
evaluating models](modeling.md).
