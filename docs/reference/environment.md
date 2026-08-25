# Environment and workspace

`sktime-cli` keeps everything that survives between commands in one workspace
directory. This page describes where that directory is, what it holds, and
which environment variables change the CLI's behavior.

## Environment variables

`SKTIME_CLI_HOME`
: The workspace directory. Defaults to the platform cache directory, which is
  `~/.cache/sktime-cli` on Linux.

`SKTIME_CLI_FORMAT`
: The default output format, one of `auto`, `human`, `agent`, `json`, or
  `quiet`. A `--format` flag overrides it.

## Workspace layout

```text
$SKTIME_CLI_HOME/
├── registry/     # cached registry crawl, one file per environment
├── downloads/    # ucr, tsf, and fpp3 dataset downloads
└── models/       # default output of run fit
```

The workspace is resolved in this order:

1. The `--cache-dir PATH` flag.
2. The `SKTIME_CLI_HOME` environment variable.
3. The platform cache directory, found with
   [platformdirs](https://pypi.org/project/platformdirs/).

Resolution happens on every call rather than at import time, which is what
lets you point the CLI at a different workspace with an environment variable
in a script or a test.

## Inspect and clear the workspace

`cache info` reports the location and the size of each subdirectory:

```bash
sktime-cli cache info
```

`cache clear` removes the registry cache and the downloads. Saved models are
kept unless you pass `--all`:

```bash
sktime-cli cache clear         # registry cache and downloads
sktime-cli cache clear --all   # also deletes saved models
```

:::{caution}
`cache clear --all` deletes every model in the workspace `models/` directory.
Models you wrote elsewhere with `--model-out` are not affected.
:::

## The registry cache

The registry crawl is the slowest thing the CLI does, so its result is cached
on disk. The cache filename embeds the sktime version, the Python version, and
a hash over the installed distributions.

Because the key is structural rather than time-based, any install, upgrade, or
removal changes the filename, which makes a stale cache unreachable instead of
merely out of date. A corrupt file rebuilds silently, and a read-only cache
directory falls back to a live crawl.

To bypass the cache for one command, pass `--no-cache`.

## Environment reporting

Three commands report on the environment:

`version`
: The versions of `sktime-cli`, sktime, and Python.

`env`
: System information, the versions of sktime's dependencies, and the
  workspace location.

`doctor`
: A health check covering the sktime import, cache writability, registry cache
  state, and optional dependencies with install hints. It exits with `1` only
  when sktime itself fails to import.
