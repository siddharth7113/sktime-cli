# Installation

`sktime-cli` runs on Python 3.10 to 3.14 and installs sktime as a dependency.

## Install the CLI

To install `sktime-cli` as a standalone tool with its own isolated
environment, use [uv](https://docs.astral.sh/uv/):

```bash
uv tool install sktime-cli
```

To install it into the active environment instead, use pip:

```bash
pip install sktime-cli
```

Both commands provide one executable, `sktime-cli`. There is no short
`sktime` alias, which keeps the command from colliding with the library.

## Check the installation

`doctor` reports whether sktime imports, whether the cache directory is
writable, and which optional dependencies are available:

```bash
sktime-cli doctor
```

The output is similar to the following:

:::{div} .terminal-capture
```{image} assets/doctor.svg
:alt: Output of sktime-cli doctor, listing sktime version, cache state, and optional dependencies
:align: center
```
:::

`doctor` exits with `0` even when optional dependencies are missing. It exits
with `1` only when sktime itself fails to import.

## Optional dependencies

sktime ships most of its estimators with optional dependencies, and the CLI
adds one extra of its own. Nothing is installed by default.

`parquet`
: Adds [pyarrow](https://arrow.apache.org/docs/python/) so that `data
  convert`, `data inspect`, and `datasets load` can read and write parquet
  files.

  ```bash
  uv tool install "sktime-cli[parquet]"
  ```

Estimator dependencies
: Estimators such as `AutoARIMA` and `Prophet` need packages that sktime
  doesn't install. When a command needs one, it exits with code `3` and a hint
  that names the install command. To see what an estimator needs before you
  run it, use `registry describe NAME`, or filter searches down to what you
  can already run with `registry search --installable-only`.

## Install from source

To work on the CLI, clone the repository and sync the development
environment:

```bash
git clone https://github.com/siddharth7113/sktime-cli
cd sktime-cli
uv sync
```

The `[tool.uv.sources]` table in `pyproject.toml` points sktime at a sibling
checkout at `../sktime`, so `uv sync` expects to find one. If you don't have
a local sktime clone, resolve sktime from PyPI instead:

```bash
uv sync --no-sources
```

For the full development workflow, see [Contributing](contributing/index.md).
