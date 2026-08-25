"""Regenerate the scitype coverage table for docs/roadmap.md.

Usage::

    python scripts/scitype_coverage.py

Prints a Markdown table of every scitype in the installed sktime, how many
objects carry it, and which sktime-cli surface handles it. Paste the output
into ``docs/roadmap.md`` whenever the numbers move.
"""

from __future__ import annotations

import collections

from sktime_cli._scitypes import SUPPORTED, UNSUPPORTED

_HANDLER_SURFACE = {
    "forecaster": "`run` (forecasting)",
    "panel": "`run` (panel)",
    "transformer": "`run transform`",
    "detector": "`run detect`",
}


def main() -> None:
    """Print the coverage table and the headline percentage."""
    from sktime.registry import all_estimators

    counts: collections.Counter = collections.Counter()
    for _name, cls in all_estimators(return_names=True):
        types = cls.get_class_tag("object_type", "object")
        for scitype in types if isinstance(types, list) else [types]:
            counts[scitype] += 1

    total = sum(counts.values())
    covered = sum(n for st, n in counts.items() if st in SUPPORTED)

    print("| scitype | objects | sktime-cli surface |")
    print("| --- | ---: | --- |")
    for scitype, count in counts.most_common():
        if scitype in SUPPORTED:
            surface = _HANDLER_SURFACE[SUPPORTED[scitype]]
        else:
            surface = UNSUPPORTED.get(scitype, "**unclassified**")
        print(f"| {scitype} | {count} | {surface} |")

    print()
    print(
        f"{covered} of {total} object registrations ({covered / total:.0%}) "
        f"are runnable through `run`."
    )


if __name__ == "__main__":
    main()
