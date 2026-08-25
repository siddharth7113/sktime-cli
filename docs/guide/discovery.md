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

Use a scitype from this list as the first argument to `registry search` and
`registry tags`.

## Search the registry

`registry search` takes an optional scitype and filters the registry:

```bash
sktime-cli registry search forecaster
```

The first search crawls sktime's registry, which takes a few seconds, and
writes the result to a disk cache. Later searches read the cache. For details
on how the cache is keyed and when it rebuilds, see [Design](../contributing/design.md).

### Filter by capability tag

Tags describe what an estimator can do. Pass `-t KEY=VALUE` to keep only the
objects that carry a tag:

```bash
sktime-cli registry search forecaster -t capability:missing_values=true
```

Repeating `-t` combines the filters with AND. A comma inside a value combines
that value's alternatives with OR:

```bash
sktime-cli registry search forecaster \
    -t capability:missing_values=true \
    -t "scitype:y=univariate,both"
```

This search keeps forecasters that handle missing values and accept either
univariate or both univariate and multivariate targets.

To list the tags that apply to a scitype, along with their types and
descriptions, use `registry tags`:

```bash
sktime-cli registry tags forecaster
```

### Filter by name

`-n` matches a substring of the object name, without regard to case:

```bash
sktime-cli registry search classifier -n rocket
```

`--exclude NAME` drops objects by exact name, and is repeatable.

### Filter by what you can run

Many estimators need packages that sktime doesn't install. To keep only the
ones whose dependencies are already present, use `--installable-only`:

```bash
sktime-cli registry search classifier --installable-only
```

Without the flag, results carry an `installable` column. A `false` value tells
you an estimator exists but needs more packages, and `registry describe` names
them.

### Shape the output

`--with-tags` adds tags as extra columns, which is useful when you want to
compare candidates on one capability:

```bash
sktime-cli registry search forecaster \
    -t capability:missing_values=true \
    --with-tags "capability:pred_int,scitype:y" \
    --limit 20
```

`--limit N` caps the number of results.

## Describe one estimator

`registry describe` reports the parameters, defaults, tags, dependencies, and
docstring summary for one object:

```bash
sktime-cli registry describe NaiveForecaster
```

In JSON output, `params` maps each parameter name to its default and whether
it's required, which is what you need to build a spec string:

```bash
sktime-cli registry describe NaiveForecaster --json | jq '.params'
```

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

## Use what you found

The `name` field from a search is the name you put in a spec string:

```bash
sktime-cli run fit "NaiveForecaster(sp=12)" --data airline --model-out model.zip
```

For how spec strings resolve names and how to compose them, see [Fitting and
evaluating models](modeling.md).
