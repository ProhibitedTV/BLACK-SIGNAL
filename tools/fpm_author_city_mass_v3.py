#!/usr/bin/env python3
"""V9 city-mass quality gate for District 12.

V2 preserved donor-authored transforms but accepted clusters whose X/Z footprint was
too thin to read as complete buildings after transplantation. V3 keeps the proven
writer and adds a conservative quality filter so facade slivers, isolated wall stacks,
and implausibly tall/narrow fragments are rejected before cloning.
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

# Intentionally conservative: reject obvious wall/facade slivers without demanding
# that every valid CyberCity modular building have a massive footprint.
MIN_FOREGROUND_SPAN = 80.0
MIN_FOREGROUND_AREA = 30000.0
MIN_FOREGROUND_MAJOR_SPAN = 220.0
MAX_HEIGHT_TO_MAJOR_SPAN = 6.0


def acceptable_foreground_cluster(cluster: city.Cluster) -> bool:
    width = float(cluster.width)
    depth = float(cluster.depth)
    height = max(0.0, float(cluster.max_y) - float(cluster.min_y))
    minor = min(width, depth)
    major = max(width, depth)
    area = width * depth
    if len(cluster.entities) < 4:
        return False
    if minor < MIN_FOREGROUND_SPAN:
        return False
    if major < MIN_FOREGROUND_MAJOR_SPAN:
        return False
    if area < MIN_FOREGROUND_AREA:
        return False
    if height > max(900.0, major * MAX_HEIGHT_TO_MAJOR_SPAN):
        return False
    return True


_ORIGINAL_FOREGROUND = v2._foreground_clusters


def quality_foreground_clusters(parsed: dict) -> list[city.Cluster]:
    clusters = _ORIGINAL_FOREGROUND(parsed)
    filtered = [cluster for cluster in clusters if acceptable_foreground_cluster(cluster)]
    filtered.sort(key=lambda cluster: (-len(cluster.entities), -(cluster.width * cluster.depth)))
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
    report["city_quality_policy"] = "reject-sliver-and-implausible-foreground-clusters-v3"
    report["foreground_quality_thresholds"] = {
        "min_minor_span": MIN_FOREGROUND_SPAN,
        "min_major_span": MIN_FOREGROUND_MAJOR_SPAN,
        "min_footprint_area": MIN_FOREGROUND_AREA,
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
        print("[PASS] V3 city-quality gate rejected narrow facade/wall-stack clusters.")
        return 0
    except (FpmError, OSError, ValueError, KeyError, TypeError, struct.error) as exc:
        print(f"FPM CITY MASS V3 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
