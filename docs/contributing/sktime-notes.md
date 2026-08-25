# Working around upstream sktime

Several parts of `sktime-cli` look more defensive than they need to be. This
page explains why. Each item is a real upstream behavior that the
implementation works around, and each one is worth knowing before you
"simplify" the code that handles it.

## registry.craft raises ModuleNotFoundError

`sktime.registry.craft()` crawls scikit-learn while resolving names, and
scikit-learn's `conftest.py` imports pytest. In an environment without pytest,
`craft` fails with `ModuleNotFoundError: pytest`.

The spec engine therefore resolves sktime names itself against the cached
registry, and falls back to `craft` only for names the registry doesn't know,
which in practice means raw scikit-learn estimators. When the fallback does
trip over the bug, the CLI converts it into a structured error.

## registry.check_tag_is_valid is broken

Tag validation goes against `ESTIMATOR_TAG_REGISTER` directly rather than
through `check_tag_is_valid`.

## registry.ALIAS_DICT is empty

There is no alias support built on `ALIAS_DICT`, because it holds nothing to
build on.

## datatypes.mtype is ambiguous for Series

A bare `datatypes.mtype(obj)` call can't decide what a `pandas.Series` is. The
CLI always passes `as_scitype`, or uses `check_is_scitype` instead.

## The registry crawl is slow

`all_estimators` takes seconds, and gets slower as more optional dependencies
are installed. The result is cached to disk, keyed by the sktime version, the
Python version, and a hash over the installed distributions. For the cache
design, see [Environment and workspace](../reference/environment.md).

## A local sktime directory shadows the import

Running `python -m sktime_cli` from a directory that contains a `sktime/`
folder imports that folder instead of the installed library. The console
script is immune to this, and the repository's `.gitignore` blocks a `sktime/`
directory from ever living inside the checkout. During development, the sktime
dev checkout belongs at `../sktime`.

## Lean environments have no optional dependencies

Most sktime estimators need packages that sktime doesn't install. Every
command degrades to exit code `3` with a runnable `uv pip install` hint rather
than a bare `ModuleNotFoundError`.

## sktime has no csv or parquet ingestion

sktime reads its own `.ts`, `.tsf`, and `.arff` formats and nothing else.
`_io.py` owns csv, parquet, and json, along with the index conventions that
make them round-trip. For those conventions, see [Working with
data](../guide/data.md).
