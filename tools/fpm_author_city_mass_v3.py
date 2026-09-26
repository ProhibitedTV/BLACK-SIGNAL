#!/usr/bin/env python3
"""V9 city-mass quality gate for District 12.

V2 preserves donor-authored transforms. V3 filters only clusters that are clearly
bad from placement data alone. GameGuru MAX modular pieces often share compact
X/Z pivots even when their meshes form a complete building, so pivot-footprint
minimums must not be treated as mesh-size measurements.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import fpm_author_city_mass as city
import fpm_author_city_mass_v2 as v2
from fpm_inspect import FpmError

MIN_ENTITY_COUNT = 4

# Strong-evidence rejection rules. These are intentionally asymmetric: a compact
# donor pivot cloud is allowed, because it may represent a complete modular shell.
# We reject only shapes that are both extremely thin and visibly facade-like, or
# implausibly tall/narrow in the placement data itself.
FACADE_SLIVER_MINOR_MAX = 55.0
FACADE_SLIVER_MAJOR_MIN = 450.0
FACADE_SLIVER_HEIGHT_MIN = 650.0

TALL_NARROW_MINOR_MAX = 130.0
TALL_NARROW_MAJOR_MAX = 320.0
TALL_NARROW_HEIGHT_MIN = 1200.0
MAX_HEIGHT_TO_MAJOR_SPAN = 6.0


def acceptable_foreground_cluster(cluster: city.Cluster) -> bool:
    width = max(0.0, float(cluster.width))
    depth = max(0.0, float(cluster.depth))
    height = max(0.0, float(cluster.max_y) - float(cluster.min_y))
    minor = min(width, depth)
    major = max(width, depth)

    if len(cluster.entities) < MIN_ENTITY_COUNT:
        return False

    # Long, paper-thin placement clouds are strong evidence that we harvested a
    # facade/wall strip instead of a whole authored building assembly.
    if (
        minor <= FACADE_SLIVER_MINOR_MAX
        and major >= FACADE_SLIVER_MAJOR_MIN
        and height >= FACADE_SLIVER_HEIGHT_MIN
    ):
        return False

    # Reject vertical stacks only when all three dimensions agree that the pivot
    # cloud is genuinely narrow. Do not reject ordinary compact modular pivots.
    if (
        minor <= TALL_NARROW_MINOR_MAX
        and major <= TALL_NARROW_MAJOR_MAX
        and height >= TALL_NARROW_HEIGHT_MIN
        and height > max(TALL_NARROW_HEIGHT_MIN, major * MAX_HEIGHT_TO_MAJOR_SPAN)
    ):
        return False

    return True


_ORIGINAL_FOREGROUND = v2._foreground_clusters


def quality_foreground_clusters(parsed: dict) -> list[city.Cluster]:
    clusters = _ORIGINAL_FOREGROUND(parsed)
    filtered = [cluster for cluster in clusters if acceptable_foreground_cluster(cluster)]
    filtered.sort(
        key=lambda cluster: (
            -len(cluster.entities),
            -(cluster.width * cluster.depth),
            -(cluster.max_y - cluster.min_y),
        )
    )

    print(
        "V3 foreground quality gate: "
        f"candidates={len(clusters)}, accepted={len(filtered)}, rejected={len(clusters) - len(filtered)}"
    )
    if clusters and not filtered:
        # This is a diagnostic guard, not a fallback to known-bad geometry. If this
        # ever fires again, the runtime log now contains enough information to tune
        # the evidence rules instead of failing with an opaque 'no assemblies' error.
        samples = sorted(
            clusters,
            key=lambda cluster: (-len(cluster.entities), -(cluster.width * cluster.depth)),
        )[:5]
        for index, cluster in enumerate(samples, 1):
            print(
                "  rejected sample "
                f"{index}: entities={len(cluster.entities)}, "
                f"width={cluster.width:.1f}, depth={cluster.depth:.1f}, "
                f"height={(cluster.max_y - cluster.min_y):.1f}"
            )
    return filtered


def compile_city_mass(
    source_path: Path,
    output_path: Path,
    donor_path: Path,
    streetwall_clones: int,
    skyline_clones: int,
    max_additions: int,
) -> dict:
    original = v2._foreground_clusters
    v2._foreground_clusters = quality_foreground_clusters
    try:
        report = v2.compile_city_mass(
            source_path,
            output_path,
            donor_path,
            streetwall_clones,
            skyline_clones,
            max_additions,
        )
    finally:
        v2._foreground_clusters = original
    report["city_quality_policy"] = "reject-only-proven-slivers-v3.1"
    report["foreground_quality_thresholds"] = {
        "min_entity_count": MIN_ENTITY_COUNT,
        "facade_sliver_minor_max": FACADE_SLIVER_MINOR_MAX,
        "facade_sliver_major_min": FACADE_SLIVER_MAJOR_MIN,
        "facade_sliver_height_min": FACADE_SLIVER_HEIGHT_MIN,
        "tall_narrow_minor_max": TALL_NARROW_MINOR_MAX,
        "tall_narrow_major_max": TALL_NARROW_MAJOR_MAX,
        "tall_narrow_height_min": TALL_NARROW_HEIGHT_MIN,
        "max_height_to_major_span": MAX_HEIGHT_TO_MAJOR_SPAN,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument("--donor-fpm", type=Path, required=True)
    parser.add_argument("--streetwall-clones", type=int, default=14)
    parser.add_argument("--skyline-clones", type=int, default=4)
    parser.add_argument("--max-additions", type=int, default=2400)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compile_city_mass(
            args.source_fpm,
            args.output_fpm,
            args.donor_fpm,
            args.streetwall_clones,
            args.skyline_clones,
            args.max_additions,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        v2.print_report(report)
        print("[PASS] V3 city-quality gate rejected only strongly evidenced facade/sliver clusters.")
        return 0
    except (FpmError, OSError, ValueError, KeyError, TypeError, struct.error) as exc:
        print(f"FPM CITY MASS V3 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
