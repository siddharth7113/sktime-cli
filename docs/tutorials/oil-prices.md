# Forecast crude oil prices

Forecast the monthly spot price of Brent crude oil, from a public CSV to a
scored forecast. You need `sktime-cli` and `curl`, and nothing else.

The tutorial spends most of its time on three habits: hold data back, check a
baseline, and score on data the model never saw.

To install the CLI, see [Installation](../installation.md).

:::{note}
The price series gains an observation each month, so your numbers will differ
from the ones here. The commands don't.
:::

## Get the data

The Federal Reserve Bank of St. Louis publishes the Europe Brent spot price as
a CSV. No API key, no sign-up:

```bash
curl -fsSL "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MCOILBRENTEU" \
    -o brent.csv
```

The file has two columns, a date and a price in dollars per barrel:

```{code-block} text
:caption: Output

observation_date,MCOILBRENTEU
1987-05-01,18.58
1987-06-01,18.86
1987-07-01,19.86
```

That layout is what the CLI expects: the first column becomes the time index,
and one remaining column becomes a series. Check it rather than assume it:

```bash
sktime-cli data inspect brent.csv
```

```{code-block} text
:caption: Output

path      brent.csv
scitype   Series
mtype     pd.Series
shape     [471]
metadata  {"dtypekind_dfip": [2], "feature_kind": [2], "feature_names":
          ["MCOILBRENTEU"], "has_nans": false, "is_empty": false,
          "is_equally_spaced": true, "is_univariate": true, "n_features": 1}
index     {"type": "PeriodIndex", "dtype": "period[M]", "start": "1987-05",
          "end": "2026-07"}
```

Four fields decide what you can do next:

- `scitype` is `Series`, so this is a forecasting problem, not a panel one.
- The index is a monthly `PeriodIndex`, so a seasonal period of 12 makes sense.
- `is_equally_spaced` is true and `has_nans` is false, so you don't need a
  forecaster that tolerates gaps.
- `shape` is 471 months, which is enough history to backtest on.

## Hold out the last year

Split before you look at anything else. `data split` writes a train file and a
test file. `--fh` sizes the test set from the horizon you plan to forecast:

```bash
sktime-cli data split brent.csv --fh 1:12
```

```{code-block} text
:caption: Output

train    brent_train.csv
test     brent_test.csv
n_train  459
n_test   12
files    ["brent_train.csv", "brent_test.csv"]
```

Everything until the last section uses `brent_train.csv`. The test file stays
closed.

## Set a baseline

Oil prices are close to a random walk, so "next month looks like this month"
is a strong competitor. Measure it first, before you have a favorite:

```bash
sktime-cli run evaluate "NaiveForecaster(strategy='last')" \
    --data brent_train.csv \
    --cv "ExpandingWindowSplitter(initial_window=300, step_length=12, fh=12)" \
    --metric MeanAbsolutePercentageError
```

```{code-block} text
:caption: Output

 index  test_MeanAbsoluteP…             fit_time             pred_time  len_train_window     cutoff
 0      0.10490548024480402  0.0016792719998193…  0.005353196000214666               300  "2012-04"
 1      0.05275666330419643  0.0013541490006900…  0.004777389000082621               312  "2013-04"
 2       0.4499385493014259  0.0013885500011383…  0.004395657000713982               324  "2014-04"
 3      0.38346783279240987  0.0013217449995863…  0.004243712999596028               336  "2015-04"
 4      0.15450258294538946  0.0013592340001196…  0.004331717000241042               348  "2016-04"
 5      0.14120212492565024  0.0013560449988290…  0.004144161999647622               360  "2017-04"
 6      0.09495297774577831  0.0012900900001113…  0.00425132700001995…               372  "2018-04"
 7       0.4535388442303947  0.0013222739999037…  0.004326820999267511               384  "2019-04"
 8       0.5984977354514109  0.0013398060000326…  0.004129684000872658               396  "2020-04"
 9      0.20683635324040464  0.0012781950008502…  0.004120182000406203               408  "2021-04"
 10     0.17972487742765564  0.0013039099994784…  0.004241398000885965               420  "2022-04"
 11     0.0615204489817037…  0.0012789510001312…  0.004190697000012733               432  "2023-04"
 12     0.17369898175718956  0.00130630899911921  0.00423050599965790…               444  "2024-04"
test_MeanAbsolutePercentageError.mean  0.235041804026801
test_MeanAbsolutePercentageError.std   0.1757983802978333
```

The splitter spec is a constructor expression, the same syntax used for
estimators. `initial_window=300` trains the first fold on 300 months,
`step_length=12` advances a year at a time, and `fh=12` scores every step from
1 to 12 months ahead. That gives 13 folds spanning 2012 to 2024.

Read the per-fold column, not just the mean. Fold 8 cuts off in April 2020:
its 60% error is the pandemic price collapse. Fold 2 covers the 2014 crash.
The mean of 0.235 averages a few calm years with a few violent ones, which is
what the standard deviation of 0.176 says.

## Try a real forecaster

`ThetaForecaster` deseasonalizes, fits a trend, and costs almost nothing to
run. Ask for it and you might get this:

```bash
sktime-cli run evaluate "ThetaForecaster(sp=12)" \
    --data brent_train.csv --fh 1:12
```

```{code-block} text
:caption: Output

error (missing_dependency): ThetaForecaster requires missing package(s): statsmodels
hint: uv pip install statsmodels
```

sktime keeps most estimator dependencies optional. The command exits with code
`3`, and `hint` carries the fix. If you installed the CLI as a standalone
tool, add the package to that tool's environment:

```bash
uv tool install sktime-cli --with statsmodels
```

Inside a virtual environment, run the hint as printed. The command then
works:

```bash
sktime-cli run evaluate "ThetaForecaster(sp=12)" \
    --data brent_train.csv \
    --cv "ExpandingWindowSplitter(initial_window=300, step_length=12, fh=12)" \
    --metric MeanAbsolutePercentageError \
    --json | jq '.aggregate'
```

```{code-block} text
:caption: Output

{
  "test_MeanAbsolutePercentageError": {
    "mean": 0.23481862505360113,
    "std": 0.17839685065301314
  }
}
```

To check what an estimator needs before running it, read the registry:

```bash
sktime-cli registry describe ThetaForecaster --json | jq '.python_dependencies'
```

```{code-block} text
:caption: Output

[
  "statsmodels"
]
```

## Compare the candidates

Comparing models is a shell loop, not a framework. Each run is a separate
process reading the same file:

```bash
for spec in \
    "NaiveForecaster(strategy='last')" \
    "NaiveForecaster(strategy='drift', window_length=12)" \
    "ThetaForecaster(sp=12)" \
    "AutoETS(auto=True, sp=12)"
do
    score=$(sktime-cli run evaluate "$spec" \
        --data brent_train.csv \
        --cv "ExpandingWindowSplitter(initial_window=300, step_length=12, fh=12)" \
        --metric MeanAbsolutePercentageError \
        --json | jq -r '.aggregate.test_MeanAbsolutePercentageError.mean')
    printf '%-52s %s\n' "$spec" "$score"
done
```

```{code-block} text
:caption: Output

NaiveForecaster(strategy='last')                     0.235041804026801
NaiveForecaster(strategy='drift', window_length=12)  0.33855892322987025
ThetaForecaster(sp=12)                               0.23481862505360113
AutoETS(auto=True, sp=12)                            0.24178849294338323
```

Nothing here beats the baseline by a margin worth believing. Theta wins by
0.0002 MAPE, which is noise across 13 folds. Drift is clearly worse:
extrapolating last year's slope fails on a series that reverses without
warning.

This is the normal outcome for oil prices, and the reason to backtest first.
Skip this step and you deploy AutoETS on the assumption that a more
sophisticated model must be better.

Theta is still a reasonable pick, because it gives you prediction intervals
that widen with the horizon. Take it, knowing its point forecast is worth
about what the baseline's is.

## Fit the final model

Fit the estimator once on the whole training set and save the artifact:

```bash
sktime-cli run fit "ThetaForecaster(sp=12)" \
    --data brent_train.csv \
    --model-out brent-theta.zip
```

```{code-block} text
:caption: Output

model      brent-theta.zip
estimator  ThetaForecaster(sp=12)
scitype    forecaster
n_obs      459
cutoff     2025-07
```

`cutoff` is the last month the model saw. Horizons count from there, so check
this field when a forecast lands on dates you didn't expect.

## Forecast

```bash
sktime-cli run predict --model brent-theta.zip --fh 1:12
```

```{code-block} text
:caption: Output

 index         MCOILBRENTEU
 2025-08  71.65372574666111
 2025-09  72.23931545630349
 2025-10  71.94843401978481
 2025-11  69.50550158630554
 2025-12    67.585802040735
 2026-01  68.26310602046797
 2026-02  68.39472955176619
 2026-03  69.09909328523034
 2026-04  70.26185960533242
 2026-05  71.55945984385845
 2026-06  71.51186625774726
 2026-07  72.24197276391246
```

Point forecasts hide how little anyone knows about oil a year out. Ask for an
interval:

```bash
sktime-cli run predict --model brent-theta.zip --fh 1:12 --interval 0.8
```

```{code-block} text
:caption: Output

 time         variable  coverage  bound               value
 2025-08  MCOILBRENTEU       0.8  lower   62.61673623946808
 2025-08  MCOILBRENTEU       0.8  upper   80.69071525385414
 2025-09  MCOILBRENTEU       0.8  lower  61.171308932036915
 2025-09  MCOILBRENTEU       0.8  upper   83.30732198057007
 2025-10  MCOILBRENTEU       0.8  lower   59.16820094329916
 2025-10  MCOILBRENTEU       0.8  upper   84.72866709627047
 2025-11  MCOILBRENTEU       0.8  lower   55.21676663329488
 2025-11  MCOILBRENTEU       0.8  upper    83.7942365393162
 2025-12  MCOILBRENTEU       0.8  lower   51.93327714455678
 2025-12  MCOILBRENTEU       0.8  upper   83.23832693691323
```

By December the 80% interval spans \$52 to \$83. Quote that, not the point
forecast.

The output is long form, one row per bound, so a second coverage adds rows
rather than columns. For the other probabilistic outputs, see [Fitting and
evaluating models](../guide/modeling.md#uncertainty-around-a-forecast).

## Score against the held-out year

Now open the test file. Write the forecast to disk and score the two:

```bash
sktime-cli run predict --model brent-theta.zip --fh 1:12 -o brent_forecast.csv

sktime-cli metrics score \
    --true brent_test.csv \
    --pred brent_forecast.csv \
    --train brent_train.csv \
    --metric MeanAbsolutePercentageError \
    --metric MeanAbsoluteError \
    --metric MeanAbsoluteScaledError
```

```{code-block} text
:caption: Output

MeanAbsolutePercentageError  0.15220702519937554
MeanAbsoluteError            14.366408630200903
MeanAbsoluteScaledError      4.24816649189211
```

Three metrics, three things to learn:

- MAPE of 0.152 means the forecast was off by 15% on average. That beats the
  23.5% the backtest predicted, because the last year was a calm one.
- MAE puts the same error in dollars: about \$14 a barrel.
- MASE needs `--train`, because it compares against a naive forecast on the
  training series.

MASE above 1 is the finding to keep. A one-step naive forecast would have done
better than this model did over twelve months, which matches the backtest.

## What you built

Five files, every step reproducible from the shell:

```{code-block} text

brent.csv            the raw series from FRED
brent_train.csv      459 months, everything before the held-out year
brent_test.csv       12 months, opened once at the end
brent-theta.zip      the fitted model, cutoff 2025-07
brent_forecast.csv   12 point forecasts
```

The artifact carries its own recipe, so you can recover the command that made
it:

```bash
sktime-cli model inspect brent-theta.zip --spec
```

```{code-block} text
:caption: Output

ThetaForecaster(sp=12)
```

## What to change next

Add exogenous data
: Oil prices move with the dollar and with inventories. Fetch a second FRED
  series and pass it with `--exog`. Find forecasters that accept it with
  `registry search forecaster -t capability:exogenous=true`.

Sweep a parameter
: `--set` overrides a parameter without rewriting the spec, so a sweep over
  `sp` is another shell loop.

Let the model choose itself
: `ForecastingGridSearchCV` is an estimator like any other. Put it in a spec
  string, and `run evaluate` backtests the selection procedure rather than
  just the winner.

Run it on a schedule
: No command holds state, so the sequence drops into a Makefile or a CI job
  unchanged.

## What to read next

- [Classify motion from wearable sensors](motion-classification.md) for the
  same loop applied to panel data.
- [Fitting and evaluating models](../guide/modeling.md) for pipelines,
  ensembles, and the rest of `run`.
- [Working with data](../guide/data.md) for the file and index conventions
  behind `data inspect`.
