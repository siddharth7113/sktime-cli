# Contributing

Thanks for wanting to help. This page covers the development setup, the
checks that have to pass, and how a release is cut.

## Set up a development environment

The project uses [uv](https://docs.astral.sh/uv/) for environments and
[hatchling](https://hatch.pypa.io/latest/) for builds:

```bash
git clone https://github.com/siddharth7113/sktime-cli
cd sktime-cli
uv sync
```

`uv sync` resolves sktime from PyPI. To test the CLI against unreleased
sktime instead, install your own checkout over the synced environment:

```bash
uv pip install -e ../sktime          # a local sktime clone
uv pip install "sktime @ git+https://github.com/sktime/sktime.git@main"
```

Both override sktime in place, and the next `uv sync` puts the PyPI version
back. Keep the override out of `pyproject.toml`: a `[tool.uv.sources]` entry
there is committed, so it would reach everyone who clones the repository.

Install the pre-commit hooks once:

```bash
uv run pre-commit install
```

## Run the checks

Tests run the CLI in-process through Typer's `CliRunner`:

```bash
uv run pytest
uv run pytest -n auto        # in parallel
```

Tests that download data are marked `network` and are excluded by default
through `addopts = "-m 'not network'"` in `pyproject.toml`. To include them:

```bash
uv run pytest -m network
```

A session-scoped fixture points `SKTIME_CLI_HOME` at a temporary directory, so
the suite never touches your real cache.

Linting and formatting go through ruff, wired up in pre-commit:

```bash
uv run pre-commit run --all-files
```

Both the test suite and pre-commit run in CI on every push and pull request,
across Python 3.10 to 3.14.

CI also pins the sktime axis, because a Python matrix alone cannot catch an
sktime release changing behaviour underneath the CLI. Two blocking jobs test
against the declared floor and the newest release. Two further jobs are
advisory (`continue-on-error`): one installs sktime from `main`, and one runs
the suite with `-W error::FutureWarning`, so an upstream deprecation shows up
while there is still time to act on it rather than when it is removed.

## Build the documentation

The docs are Sphinx with MyST Markdown. To build them locally:

```bash
uv sync --extra docs
uv run sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser.

Read the Docs builds with `fail_on_warning: true`, so a warning locally is a
failed build there. Before you push a docs change, build it once and read the
warnings.

The CLI reference is generated from the live Typer application by a small
extension at `docs/_ext/typer_cli.py`. Don't hand-edit command documentation:
change the `help` text in `src/sktime_cli/commands/` and the reference follows.

## Regenerate the terminal captures

The terminal captures in the README and the docs are SVGs rendered from real
CLI runs. The hero capture carries a CSS animation that replays the session.
After changing CLI output, regenerate them:

```bash
uv run python docs/assets/generate.py
```

## Conventions

Derive, don't duplicate
: Configuration comes from `pyproject.toml` and `importlib.metadata` wherever
  it can. The optional-dependency list that `doctor` reports on is computed
  from package metadata rather than maintained by hand, and the docs read the
  version the same way.

Keep imports lazy
: `typer` is the only third-party module imported at module level. Every
  sktime, pandas, numpy, rich, and platformdirs import is function-local, so
  `sktime-cli --help` doesn't pay for sktime's import time. A new module-level
  import of a heavy package is a regression.

Error codes are append-only
: The codes in `_errors.py` are part of the published contract. Add codes,
  don't rename or reuse them.

Every failure gets a hint
: Where the CLI can know the fix, the error's `hint` field states it. The test
  suite treats a missing hint on those paths as a bug.

Commands hold no domain logic
: Modules under `commands/` define the option surface and orchestrate. The
  logic belongs in the private modules they call. For the module map, see
  [Architecture](architecture.md).

## Where to read next

- [Architecture](architecture.md) for the repository layout and the path a
  command takes from argv to output.
- [Design](design.md) for the decisions behind the state model, the output
  contract, the error model, and the spec engine.
- [Working around upstream sktime](sktime-notes.md) before you simplify code
  that looks unnecessarily defensive.

## Releasing

Releases are automated. Pushing a `v*` tag runs the test matrix, builds the
sdist and wheel, smoke-tests the wheel, and publishes to PyPI through trusted
publishing. The build job checks that the tag matches the version in
`pyproject.toml`, so bump the version in the same commit that you tag.

```{toctree}
:hidden:

architecture
design
sktime-notes
```
