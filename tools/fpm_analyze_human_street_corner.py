#!/usr/bin/env python3
"""Extract the human-authored District 12 street-corner composition from a captured FPM.

This is intentionally read-only.  It treats the user's manually edited street corner as
art-direction evidence rather than trying to guess which assets "look urban".  The analyzer:

* finds the junction with the densest set of human-signature street props;
* reports exact world and junction-local transforms for those props;
* reports nearby street-scene entities so unanticipated hand-placed assets are not missed;
* keeps road/building geometry out of the street-scene inventory.

The resulting JSON is used to calibrate the deterministic citywide dressing pass.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import fpm_analyze_manual_reference as manual
import fpm_author_road_network_v2 as roads
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

HUMAN_SIGNATURE_ROLES = {
    "bench": "cs_bench.fpe",
    "trash_can": "cs_trash_can.fpe",
    "stop_light": "cs_stop_light.fpe",
    "broad_tree": "broad tree.fpe",
}

TRACKED_ROLES = {
    **HUMAN_SIGNATURE_ROLES,
    "planter": "cs_planter_01.fpe",
    "sidewalk_guard": "cs_sidewalk_guard.fpe",
    "bollard_stop": "cs_street_crosswalk_metal_blocker_post.fpe",
    "sidewalk_light": "cs_sidewalk_light.fpe",
    "utility_pole": "cs_street_electrical_pole_01.fpe",
    "street_lamp": "cs_street_lamp.fpe",
    "joshua_tree": "joshua tree - set a.fpe",
    "bottle_can_cluster": "cs_bottle_can_cluster_01.fpe",
    "newspaper_01": "cs_newspaper_01.fpe",
    "newspaper_02": "cs_newspaper_02.fpe",
}

# Radius is deliberately wider than a single sidewalk corner so the report shows the
# complete authored composition and its relationship to the adjacent building frontage.
CORNER_RADIUS = 1450.0


def _world(entity: dict[str, Any]) -> dict[str, float]:
    return {
        "x": round(float(entity["position"]["x"]), 3),
        "y": round(float(entity["position"]["y"]), 3),
        "z": round(float(entity["position"]["z"]), 3),
        "yaw": round(float(entity["rotation_euler"]["y"]), 3),
    }


def _distance_to(entity: dict[str, Any], owner: dict[str, Any]) -> float:
    return manual.distance_xz(entity, owner)


def _role_for(entity: dict[str, Any]) -> str | None:
    base = fabric.basename(entity.get("asset"))
    for role, wanted in TRACKED_ROLES.items():
        if base == wanted:
            return role
    return None


def _looks_like_street_scene(entity: dict[str, Any]) -> bool:
    asset = (entity.get("asset") or "").replace("/", "\\").lower()
    base = fabric.basename(asset)
    if roads.road_kind(asset) is not None:
        return False
    # Exclude the known structural city kit and road semantic decals/corners.
    structural_tokens = (
        "\\background buildings\\",
        "\\buildings\\",
        "\\store fronts\\",
        "\\streets and sidewalks\\streets\\cs_street_",
        "\\streets and sidewalks\\street decals\\",
        "\\streets and sidewalks\\sidewalks\\",
    )
    if any(token in asset for token in structural_tokens):
        # Stop lights are in Street Misc rather than the Streets folder and are retained.
        return False
    if base in {
        "player start.fpe",
        "start with ghost.fpe",
    }:
        return False
    return any(
        token in asset
        for token in (
            "\\misc\\",
            "\\trees\\",
            "\\flora\\",
            "planter",
            "bench",
            "trash",
            "debris",
            "newspaper",
        )
    )


def _junctions(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        e
        for e in entities
        if roads.road_kind(e.get("asset")) in {"fourway", "tee", "curve"}
    ]


def _anchor_junction(
    entities: list[dict[str, Any]], junctions: list[dict[str, Any]]
) -> dict[str, Any]:
    signatures = [
        e
        for e in entities
        if fabric.basename(e.get("asset")) in set(HUMAN_SIGNATURE_ROLES.values())
    ]
    if not signatures:
        raise FpmError("No human-signature bench/trash/stop-light/broad-tree entities found.")
    if not junctions:
        raise FpmError("No junctions found for human-corner analysis.")

    scored: list[tuple[int, float, int, dict[str, Any]]] = []
    for junction in junctions:
        distances = sorted(_distance_to(e, junction) for e in signatures)
        near = [d for d in distances if d <= CORNER_RADIUS]
        # Favor the junction containing the most explicit human-signature props, then
        # the tightest cluster, then stable record order.
        tightness = sum(near) / len(near) if near else 1e9
        scored.append((-len(near), tightness, int(junction["record_index"]), junction))
    scored.sort(key=lambda row: row[:3])
    if -scored[0][0] == 0:
        raise FpmError("Human-signature props are not near a recognized junction.")
    return scored[0][3]


def _row(entity: dict[str, Any], anchor: dict[str, Any]) -> dict[str, Any]:
    local = manual.local_transform(anchor, entity)
    return {
        "record_index": int(entity["record_index"]),
        "role": _role_for(entity),
        "asset": entity.get("asset"),
        "basename": fabric.basename(entity.get("asset")),
        "world": _world(entity),
        "anchor_local": {k: round(float(v), 3) for k, v in local.items()},
        "signature": list(manual.signature(local)),
    }


def analyze(path: Path) -> dict[str, Any]:
    with FpmArchive(path) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        parsed = parse_map_ele(archive.read("map.ele"), ent["entries"])

    entities = parsed["entities"]
    junctions = _junctions(entities)
    anchor = _anchor_junction(entities, junctions)

    tracked: list[dict[str, Any]] = []
    nearby_scene: list[dict[str, Any]] = []
    for entity in entities:
        distance = _distance_to(entity, anchor)
        if distance > CORNER_RADIUS:
            continue
        if _role_for(entity) is not None:
            tracked.append(_row(entity, anchor))
        elif _looks_like_street_scene(entity):
            nearby_scene.append(_row(entity, anchor))

    tracked.sort(key=lambda r: (r["role"] or "", r["record_index"]))
    nearby_scene.sort(key=lambda r: (r["basename"], r["record_index"]))

    counts = Counter(r["role"] for r in tracked)
    signature_counts: dict[str, Counter[tuple[Any, ...]]] = defaultdict(Counter)
    for row in tracked:
        signature_counts[row["role"]][tuple(row["signature"])] += 1

    return {
        "policy": "human-authored-street-corner-reference-v10.5",
        "fpm": str(path.resolve()),
        "entity_count": int(parsed["entity_count"]),
        "anchor_junction": {
            "record_index": int(anchor["record_index"]),
            "kind": roads.road_kind(anchor.get("asset")),
            "asset": anchor.get("asset"),
            "world": _world(anchor),
        },
        "radius": CORNER_RADIUS,
        "tracked_counts": dict(sorted(counts.items())),
        "tracked_signatures": {
            role: [
                {"signature": list(sig), "count": count}
                for sig, count in counter.most_common()
            ]
            for role, counter in sorted(signature_counts.items())
        },
        "tracked": tracked,
        "nearby_unclassified_street_scene": nearby_scene,
    }


def print_report(report: dict[str, Any]) -> None:
    anchor = report["anchor_junction"]
    print("BLACK SIGNAL - human-authored street-corner reference")
    print(f"FPM: {report['fpm']}")
    print(
        f"Anchor: {anchor['kind']}#{anchor['record_index']} "
        f"at ({anchor['world']['x']:.1f},{anchor['world']['z']:.1f}) "
        f"yaw={anchor['world']['yaw']:.1f}"
    )
    print("Tracked human/street-life roles:")
    for role, count in report["tracked_counts"].items():
        print(f"  {role:24s} {count}")
    print("\nExact anchor-local placements:")
    for row in report["tracked"]:
        print(
            f"  {row['role'] or 'scene':24s} #{row['record_index']:4d} "
            f"{row['basename']:<42s} local={tuple(row['signature'])}"
        )
    if report["nearby_unclassified_street_scene"]:
        print("\nOther nearby street-scene assets:")
        for row in report["nearby_unclassified_street_scene"]:
            print(
                f"  #{row['record_index']:4d} {row['basename']:<42s} "
                f"local={tuple(row['signature'])}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fpm", type=Path)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.fpm)
        if args.report_json:
            args.report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"HUMAN STREET CORNER ANALYSIS ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
