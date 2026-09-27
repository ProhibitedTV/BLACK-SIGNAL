"""Native-review corrections layered on the group-safe V12 city-polish builder.

Keep the validated append-only grouped-map writer unchanged. This wrapper removes
only V12-owned appended content that failed native visual review; baseline source
records (and therefore MAX v319 editor groups) remain byte/index stable.
"""
import argparse
from pathlib import Path

import fpm_polish_city_v12 as base

_BASE_PLAN = base.plan
REMOVED_APPEND_GROUPS = frozenset({"sheltered-life"})


def plan(parsed, old, measured):
    rows, parcels, changes, protected, heroes = _BASE_PLAN(parsed, old, measured)
    rows = [
        row
        for row in rows
        if not (
            row.get("source_index") is None
            and row.get("group") in REMOVED_APPEND_GROUPS
        )
    ]
    base.assert_grouped_source_prefix(parsed, rows)
    return rows, parcels, changes, protected, heroes


def build(source: Path, output: Path):
    original = base.plan
    try:
        base.plan = plan
        return base.build(source, output)
    finally:
        base.plan = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
