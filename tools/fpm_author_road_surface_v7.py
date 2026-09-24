#!/usr/bin/env python3
"""Author road-surface detail with role-aware donor attachment.

v6 replays real CyberCity road-local transforms, but it attaches every donor decal to
the geometrically nearest recognized road of any kind. That is too permissive for
junction-approach arrows and regulatory text: a marking authored on a Straight 4X
approach can be closer to the intersection pivot and get catalogued as intersection
detail, where it is later unusable or misleading.

v7 keeps the v6 writer and exact donor-local transforms while enforcing semantic
ownership:

* arrow and SLOW/ONLY approach markings may attach only to Straight 4X roads;
* wear and utility covers may attach to any supported full-width road module;
* approach detection considers only real traffic junctions (4-way and T), not curves;
* nearest-road ties are deterministic by donor record index;
* the existing donor-distance guard and safe-template checks remain mandatory.
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_network_v2 as legacy
import fpm_author_road_surface_v6 as v6
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmError


TRAFFIC_JUNCTION_KINDS = frozenset(("fourway", "tee"))


def compatible_road_kinds(role: str) -> frozenset[str]:
    """Return road kinds that are semantically allowed to own a surface role."""
    if role in v6.ARROW_ROLES or role in v6.TEXT_ROLES:
        return frozenset(("straight4",))
    if role in v6.WEAR_ROLES or role == "manhole_cover":
        return frozenset(v6.ALLOWED_ROAD_KINDS)
    return frozenset()


def nearest_compatible_road(
    detail: dict[str, Any],
    roads: list[dict[str, Any]],
    role: str,
) -> tuple[dict[str, Any] | None, float]:
    allowed = compatible_road_kinds(role)
    if not allowed:
        return None, float("inf")

    dp = detail["position"]
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for road in roads:
        if legacy.road_kind(road.get("asset")) not in allowed:
            continue
        rp = road["position"]
        dx = float(dp["x"]) - float(rp["x"])
        dz = float(dp["z"]) - float(rp["z"])
        distance2 = dx * dx + dz * dz
        ranked.append((distance2, int(road["record_index"]), road))

    if not ranked:
        return None, float("inf")
    distance2, _record_index, road = min(ranked, key=lambda row: (row[0], row[1]))
    return road, math.sqrt(distance2)


def harvest_surface_members(
    donor_parsed: dict[str, Any], donor_ele: bytes
) -> tuple[list[v6.SurfaceMember], list[dict[str, Any]]]:
    roads = [
        entity
        for entity in donor_parsed["entities"]
        if legacy.road_kind(entity.get("asset")) in v6.ALLOWED_ROAD_KINDS
    ]
    if not roads:
        raise FpmError("CyberCity donor contains no recognized full-width road modules.")

    members: list[v6.SurfaceMember] = []
    rejected: list[dict[str, Any]] = []
    for detail in donor_parsed["entities"]:
        role = v6._surface_role(detail)
        if role is None:
            continue

        safe, reason = fabric.safe_template_entity(detail, False)
        if not safe:
            rejected.append(
                {
                    "detail_record_index": int(detail["record_index"]),
                    "role": role,
                    "reason": f"unsafe donor record: {reason}",
                }
            )
            continue

        road, distance = nearest_compatible_road(detail, roads, role)
        if road is None:
            rejected.append(
                {
                    "detail_record_index": int(detail["record_index"]),
                    "role": role,
                    "reason": "no semantically compatible donor road",
                }
            )
            continue
        if distance > v6.MAX_DONOR_ATTACH_DISTANCE:
            rejected.append(
                {
                    "detail_record_index": int(detail["record_index"]),
                    "role": role,
                    "reason": (
                        "not attached to a compatible road exemplar "
                        f"(nearest={distance:.2f})"
                    ),
                }
            )
            continue

        members.append(v6._capture_member(role, road, detail, donor_ele))

    members.sort(
        key=lambda member: (
            member.road_kind,
            member.role,
            member.donor_road_record_index,
            round(member.local_x, 3),
            round(member.local_z, 3),
            member.donor_detail_record_index,
        )
    )
    if not members:
        raise FpmError("CyberCity contains no safe role-compatible road-surface exemplars.")
    return members, rejected


def nearest_traffic_junction(
    road: dict[str, Any], junctions: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float]:
    """Find only a real 4-way/T junction; curves are not marking destinations."""
    filtered = [
        junction
        for junction in junctions
        if legacy.road_kind(junction.get("asset")) in TRAFFIC_JUNCTION_KINDS
    ]
    return v6._nearest_junction(road, filtered)


def compile_surface_details(
    source_path: Path,
    output_path: Path,
    donor_path: Path,
    max_additions: int,
) -> dict[str, Any]:
    original_harvest = v6.harvest_surface_members
    original_nearest_junction = v6._nearest_junction
    v6.harvest_surface_members = harvest_surface_members

    # Avoid recursion: nearest_traffic_junction calls the original v6 helper.
    def _junction_adapter(
        road: dict[str, Any], junctions: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, float]:
        filtered = [
            junction
            for junction in junctions
            if legacy.road_kind(junction.get("asset")) in TRAFFIC_JUNCTION_KINDS
        ]
        return original_nearest_junction(road, filtered)

    v6._nearest_junction = _junction_adapter
    try:
        report = v6.compile_surface_details(
            source_path,
            output_path,
            donor_path,
            max_additions,
        )
    finally:
        v6.harvest_surface_members = original_harvest
        v6._nearest_junction = original_nearest_junction

    report["surface_attachment_policy"] = "role-aware-nearest-compatible-road"
    report["approach_junction_kinds"] = sorted(TRAFFIC_JUNCTION_KINDS)
    return report


def print_report(report: dict[str, Any]) -> None:
    v6.print_report(report)
    print("[PASS] Arrow/text markings attach only to authored Straight 4X approaches.")
    print("[PASS] Curve modules are never treated as traffic-junction marking targets.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument("--donor-fpm", type=Path, required=True)
    parser.add_argument("--max-additions", type=int, default=1800)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)

    try:
        report = compile_surface_details(
            args.source_fpm,
            args.output_fpm,
            args.donor_fpm,
            args.max_additions,
        )
        if args.report_json:
            import json

            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM ROAD SURFACE V7 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
