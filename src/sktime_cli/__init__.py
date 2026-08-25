"""sktime-cli: command-line interface for sktime, for AI agents and humans."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sktime-cli")
except PackageNotFoundError:  # running from a source tree with no install
    __version__ = "0.0.0+unknown"
