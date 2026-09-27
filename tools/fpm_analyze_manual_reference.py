#!/usr/bin/env python3
"""Analyze a manually corrected District 12 FPM for road-detail transform clues.

The semantic authoring pass is deterministic, so a manual GameGuru edit should show
up as a rare transform relative to the repeated generated patterns. This tool reads
the canonical Git-LFS FPM, attaches road-detail assets to the nearest compatible road
module, converts each placement into owner-local coordinates, and reports deviations
from the current v9.1 authored constants.

It is intentionally read-only. The report is evidence for tuning the generator; it
never rewrites the manually corrected reference map.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import fpm_author_road_network_v2 as roads
import fpm_author_road_surface_v5 as surface
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


def norm_angle(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def rotate_local(dx: float, dz: float, yaw_deg: float) -> tuple[float, float]:
    angle = math.radians(yaw_deg)
    c = math.cos(angle)
    s = math.sin(angle)
    return (dx * c - dz * s, dx * s + dz * c)


def distance_xz(a: dict[str, Any], b: dict[str, Any]) -> float:
    ap = a["position"]
    bp = b["position"]
    return math.hypot(float(ap["x"]) - float(bp["x"]), float(ap["z"]) - float(bp["z"]))


def nearest(entity: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return min(candidates, key=lambda row: (distance_xz(entity, row), int(row["record_index"])))


def local_transform(owner: dict[str, Any], entity: dict[str, Any]) -> dict[str, float]:
    op = owner["position"]
    ep = entity["position"]
    yaw = float(owner["rotation_euler"]["y"])
    dx = float(ep["x"]) - float(op["x"])
    dz = float(ep["z"]) - float(op["z"])
    lx, lz = rotate_local(dx, dz, -yaw)
    return {
        "local_x": lx,
        "local_y": float(ep["y"]) - float(op["y"]),
        "local_z": lz,
        "yaw_delta": norm_angle(float(entity["rotation_euler"]["y"]) - yaw),
        "distance": math.hypot(dx, dz),
    }


def close(value: float, expected: float, tolerance: float) -> bool:
    return abs(float(value) - float(expected)) <= tolerance


def angle_close(value: float, expected: float, tolerance: float = 1.0) -> bool:
    return abs(norm_angle(float(value) - float(expected))) <= tolerance


def matches_expected(role: str, t: dict[str, float]) -> bool:
    x = t["local_x"]
    z = t["local_z"]
    yaw = t["yaw_delta"]
    if role == "road_center_yellow":
        return close(x, 0.0, 3.0) and any(close(z, e, 3.0) for e in (-110.0, 110.0)) and angle_close(yaw, 90.0)
    if role == "crosswalk":
        expected = (
            (0.0, 200.0, 0.0),
            (0.0, -200.0, 180.0),
            (200.0, 0.0, 90.0),
            (-200.0, 0.0, -90.0),
        )
        return any(close(x, ex, 3.0) and close(z, ez, 3.0) and angle_close(yaw, ey) for ex, ez, ey in expected)
    if role == surface.ARROW_ROLES[2]:  # road_arrow_straight
        expected = ((94.0, 120.0, 90.0), (-94.0, -120.0, -90.0))
        return any(close(x, ex, 3.0) and close(z, ez, 3.0) and angle_close(yaw, ey) for ex, ez, ey in expected)
    if role == "street_lamp":
        expected = ((390.0, 0.0, 0.0), (-390.0, 0.0, 180.0))
        return any(close(x, ex, 5.0) and close(z, ez, 5.0) and angle_close(yaw, ey) for ex, ez, ey in expected)
    return True


def signature(t: dict[str, float]) -> tuple[float, float, float, float]:
    return (
        round(t["local_x"], 1),
        round(t["local_y"], 1),
        round(t["local_z"], 1),
        round(norm_angle(t["yaw_delta"]), 1),
    )


def analyze(path: Path) -> dict[str, Any]:
    with FpmArchive(path) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        parsed = parse_map_ele(archive.read("map.ele"), ent["entries"])

    entities = parsed["entities"]
    recognized_roads = [e for e in entities if roads.road_kind(e.get("asset")) is not None]
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for road in recognized_roads:
        by_kind[roads.road_kind(road.get("asset"))].append(road)

    role_assets = {
        "road_center_yellow": fabric.basename(fabric.ASSETS["road_center_yellow"]["basename"]),
        "crosswalk": fabric.basename(fabric.ASSETS["crosswalk"]["basename"]),
        "street_lamp": fabric.basename(fabric.ASSETS["street_lamp"]["basename"]),
        "road_arrow_straight": fabric.basename(surface.SURFACE_ASSETS["road_arrow_straight"]["basename"]),
        "sidewalk_corner": "cs_sidewalk_corner1.fpe",
        "sidewalk_corner_dropcurb": "cs_sidewalk_corner1_dropcurb.fpe",
    }
    owner_kinds = {
        "road_center_yellow": ("straight4",),
        "road_arrow_straight": ("straight4",),
        "street_lamp": ("straight4",),
        "crosswalk": ("fourway",),
        "sidewalk_corner": ("fourway", "tee", "curve"),
        "sidewalk_corner_dropcurb": ("fourway", "tee", "curve"),
    }

    details_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    basename_to_role = {asset: role for role, asset in role_assets.items()}
    for entity in entities:
        role = basename_to_role.get(fabric.basename(entity.get("asset")))
        if role:
            details_by_role[role].append(entity)

    report_roles: dict[str, Any] = {}
    all_deviations: list[dict[str, Any]] = []
    for role, detail_entities in sorted(details_by_role.items()):
        candidates: list[dict[str, Any]] = []
        for kind in owner_kinds[role]:
            candidates.extend(by_kind.get(kind, []))

        rows: list[dict[str, Any]] = []
        counts: Counter[tuple[float, float, float, float]] = Counter()
        for entity in detail_entities:
            owner = nearest(entity, candidates)
            if owner is None:
                continue
            t = local_transform(owner, entity)
            sig = signature(t)
            counts[sig] += 1
            owner_kind = roads.road_kind(owner.get("asset"))
            row = {
                "role": role,
                "entity_record": int(entity["record_index"]),
                "asset": entity.get("asset"),
                "world": {
                    "x": float(entity["position"]["x"]),
                    "y": float(entity["position"]["y"]),
                    "z": float(entity["position"]["z"]),
                    "yaw": float(entity["rotation_euler"]["y"]),
                },
                "owner_record": int(owner["record_index"]),
                "owner_kind": owner_kind,
                "owner_world": {
                    "x": float(owner["position"]["x"]),
                    "y": float(owner["position"]["y"]),
                    "z": float(owner["position"]["z"]),
                    "yaw": float(owner["rotation_euler"]["y"]),
                },
                "local": {k: round(v, 3) for k, v in t.items()},
                "signature": list(sig),
                "matches_v9_1": matches_expected(role, t),
            }
            rows.append(row)
            if role in {"road_center_yellow", "crosswalk", "road_arrow_straight", "street_lamp"} and not row["matches_v9_1"]:
                all_deviations.append(row)

        report_roles[role] = {
            "count": len(rows),
            "signatures": [
                {"signature": list(sig), "count": count}
                for sig, count in counts.most_common()
            ],
            "rows": rows,
        }

    return {
        "fpm": str(path.resolve()),
        "entity_count": int(parsed["entity_count"]),
        "road_counts": {kind: len(rows) for kind, rows in sorted(by_kind.items())},
        "roles": report_roles,
        "v9_1_deviation_count": len(all_deviations),
        "v9_1_deviations": sorted(
            all_deviations,
            key=lambda row: (row["role"], row["owner_record"], row["entity_record"]),
        ),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - manual District 12 transform reference")
    print(f"FPM: {report['fpm']}")
    print(f"Entities: {report['entity_count']}")
    print("Road counts:")
    for kind, count in report["road_counts"].items():
        print(f"  {kind:12s} {count}")
    print("\nObserved local transform signatures:")
    for role, data in report["roles"].items():
        print(f"  {role} ({data['count']} entities)")
        for item in data["signatures"][:12]:
            print(f"    {item['count']:4d} x {tuple(item['signature'])}")
    print(f"\nV9.1 semantic deviations: {report['v9_1_deviation_count']}")
    for row in report["v9_1_deviations"]:
        print(
            "  DEV "
            f"role={row['role']} entity=#{row['entity_record']} "
            f"owner={row['owner_kind']}#{row['owner_record']} "
            f"local={tuple(row['signature'])} "
            f"world=({row['world']['x']:.1f},{row['world']['y']:.1f},{row['world']['z']:.1f}) "
            f"yaw={row['world']['yaw']:.1f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fpm", type=Path)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.fpm)
        if args.report_json:
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"MANUAL REFERENCE ANALYSIS ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
