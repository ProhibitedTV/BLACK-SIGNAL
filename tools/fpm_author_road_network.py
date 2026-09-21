#!/usr/bin/env python3
"""Author a large, coherent Cyber City road network into District 12.

The network is deliberately built before buildings or street dressing.  It uses
only exact road records already authored by GameGuru MAX in CyberCity.fpm and
preserves every non-map.ele archive member byte-for-byte.

Layout grammar:
- an outer ring whose four corners use CS_Street_Curve_1;
- T intersections around the ring where interior streets meet it;
- a regular interior grid of CS_Street_4_Way_2 intersections;
- CS_Street_Straight_4X pieces between nodes;
- selected 4X spans are replaced by paired CS_Street_Straight_2X pieces so the
  finished network uses every road module available in the exemplar.

The source record's local orientation is not guessed.  We infer each road
asset's connection mask from the existing CyberCity road graph and rotate that
exact record to the desired N/E/S/W mask.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, FrozenSet

import fpm_author_street_fabric as base
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


DIRS = ("N", "E", "S", "W")
EXPECTED_DEGREE = {
    "fourway": 4,
    "tee": 3,
    "curve": 2,
    "straight4": 2,
    "straight2": 2,
}


@dataclass(frozen=True)
class PlannedRoad:
    kind: str
    x: float
    z: float
    mask: FrozenSet[str]
    note: str


@dataclass
class RoadTemplate:
    kind: str
    entity: dict[str, Any]
    raw_record: bytes
    mask: FrozenSet[str]


def norm_asset(value: str | None) -> str:
    p = (value or "").replace("/", "\\").lower().lstrip("\\")
    if p.startswith("entitybank\\"):
        p = p[len("entitybank\\") :]
    return p


def road_kind(value: str | None) -> str | None:
    p = norm_asset(value)
    prefix = "cyberpunk streets booster pack\\streets and sidewalks\\streets\\"
    if not p.startswith(prefix):
        return None
    name = p.rsplit("\\", 1)[-1]
    if name == "cs_street_4_way_2.fpe":
        return "fourway"
    if name == "cs_street_t-intersect_3.fpe":
        return "tee"
    if name == "cs_street_curve_1.fpe":
        return "curve"
    if name == "cs_street_straight_4x.fpe":
        return "straight4"
    if name == "cs_street_straight_2x.fpe":
        return "straight2"
    return None


def rotate_mask(mask: FrozenSet[str], steps: int) -> FrozenSet[str]:
    out: set[str] = set()
    for d in mask:
        out.add(DIRS[(DIRS.index(d) + steps) % 4])
    return frozenset(out)


def node_mask(ix: int, iz: int, size: int) -> tuple[str, FrozenSet[str]]:
    last = size - 1
    if ix == 0 and iz == 0:
        return "curve", frozenset(("E", "N"))
    if ix == last and iz == 0:
        return "curve", frozenset(("W", "N"))
    if ix == 0 and iz == last:
        return "curve", frozenset(("E", "S"))
    if ix == last and iz == last:
        return "curve", frozenset(("W", "S"))
    if ix == 0:
        return "tee", frozenset(("N", "S", "E"))
    if ix == last:
        return "tee", frozenset(("N", "S", "W"))
    if iz == 0:
        return "tee", frozenset(("E", "W", "N"))
    if iz == last:
        return "tee", frozenset(("E", "W", "S"))
    return "fourway", frozenset(("N", "E", "S", "W"))


def _use_short_pair(ix: int, iz: int, axis: str) -> bool:
    # Deterministic service-street rhythm.  Keep the central cross on 4X pieces
    # and introduce 2X pairs elsewhere without changing total segment length.
    salt = 0 if axis == "H" else 2
    return (ix * 3 + iz * 5 + salt) % 4 == 0


def plan_relative_network(grid_size: int, node_spacing: float = 1800.0) -> list[PlannedRoad]:
    if grid_size < 5 or grid_size % 2 == 0:
        raise ValueError("grid_size must be an odd integer >= 5")
    half = grid_size // 2
    coords = [(i - half) * node_spacing for i in range(grid_size)]
    plan: list[PlannedRoad] = []

    # Nodes: curves on the four corners, T junctions on the outer ring, and
    # four-way intersections everywhere inside the city grid.
    for iz, z in enumerate(coords):
        for ix, x in enumerate(coords):
            kind, mask = node_mask(ix, iz, grid_size)
            plan.append(PlannedRoad(kind, x, z, mask, f"node-{ix}-{iz}"))

    # Every node-to-node span is 1800 units, matching CyberCity's authored
    # grammar: 500 from a junction center to the first 4X center, then 400-unit
    # modules, then 500 into the next junction.  A 400-unit middle module can be
    # replaced exactly by two 200-unit 2X pieces centered at 800/1000.
    for iz, z in enumerate(coords):
        for ix in range(grid_size - 1):
            x0 = coords[ix]
            if _use_short_pair(ix, iz, "H"):
                offsets = ((500.0, "straight4"), (800.0, "straight2"), (1000.0, "straight2"), (1300.0, "straight4"))
            else:
                offsets = ((500.0, "straight4"), (900.0, "straight4"), (1300.0, "straight4"))
            for off, kind in offsets:
                plan.append(PlannedRoad(kind, x0 + off, z, frozenset(("E", "W")), f"h-{ix}-{iz}"))

    for ix, x in enumerate(coords):
        for iz in range(grid_size - 1):
            z0 = coords[iz]
            if _use_short_pair(ix, iz, "V"):
                offsets = ((500.0, "straight4"), (800.0, "straight2"), (1000.0, "straight2"), (1300.0, "straight4"))
            else:
                offsets = ((500.0, "straight4"), (900.0, "straight4"), (1300.0, "straight4"))
            for off, kind in offsets:
                plan.append(PlannedRoad(kind, x, z0 + off, frozenset(("N", "S")), f"v-{ix}-{iz}"))

    return plan


def _cardinal_mask(entity: dict[str, Any], roads: list[dict[str, Any]]) -> FrozenSet[str]:
    p = entity["position"]
    x = float(p["x"])
    z = float(p["z"])
    best: dict[str, float] = {}
    for other in roads:
        if other["record_index"] == entity["record_index"]:
            continue
        q = other["position"]
        dx = float(q["x"]) - x
        dz = float(q["z"]) - z
        adx = abs(dx)
        adz = abs(dz)
        direction: str | None = None
        distance = 0.0
        if adx <= 75.0 and 120.0 <= adz <= 620.0:
            direction = "N" if dz > 0 else "S"
            distance = adz
        elif adz <= 75.0 and 120.0 <= adx <= 620.0:
            direction = "E" if dx > 0 else "W"
            distance = adx
        if direction is not None and (direction not in best or distance < best[direction]):
            best[direction] = distance
    return frozenset(best)


def _cloneable_road(entity: dict[str, Any]) -> bool:
    if int(entity.get("record_index", 0)) == 1:
        return False
    if int(entity.get("v319_group_count", 0) or 0) != 0:
        return False
    return int(entity.get("staticflag", 0)) in (0, 1)


def choose_templates(parsed: dict[str, Any], ele_data: bytes) -> tuple[dict[str, RoadTemplate], list[dict[str, Any]]]:
    roads = [e for e in parsed["entities"] if road_kind(e.get("asset")) is not None]
    if not roads:
        raise FpmError("CyberCity contains no recognized Cyber City road records.")

    templates: dict[str, RoadTemplate] = {}
    for kind, expected in EXPECTED_DEGREE.items():
        candidates: list[tuple[tuple[int, int, int], dict[str, Any], FrozenSet[str]]] = []
        for e in roads:
            if road_kind(e.get("asset")) != kind or not _cloneable_road(e):
                continue
            mask = _cardinal_mask(e, roads)
            exact = 1 if len(mask) == expected else 0
            # Prefer a source with the expected topology, then the most visible
            # neighbors, then the earliest authored record for determinism.
            score = (exact, len(mask), -int(e["record_index"]))
            candidates.append((score, e, mask))
        if not candidates:
            raise FpmError(f"CyberCity has no cloneable placed record for road kind '{kind}'.")
        candidates.sort(key=lambda item: item[0], reverse=True)
        _score, entity, mask = candidates[0]
        if len(mask) != expected:
            raise FpmError(
                f"Could not infer a complete {kind} orientation from CyberCity "
                f"(best connection mask={sorted(mask)}, expected degree={expected})."
            )
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        templates[kind] = RoadTemplate(kind, entity, ele_data[start:end], mask)
    return templates, roads


def yaw_for_mask(template: RoadTemplate, wanted: FrozenSet[str]) -> float:
    source_yaw = float(template.entity["rotation_euler"]["y"])
    for steps in range(4):
        if rotate_mask(template.mask, steps) == wanted:
            return (source_yaw + steps * 90.0) % 360.0
    raise FpmError(
        f"Cannot rotate {template.kind} mask {sorted(template.mask)} into {sorted(wanted)}."
    )


def choose_origin(roads: list[dict[str, Any]]) -> tuple[float, float, float]:
    mx = statistics.median(float(e["position"]["x"]) for e in roads)
    mz = statistics.median(float(e["position"]["z"]) for e in roads)
    fourways = [e for e in roads if road_kind(e.get("asset")) == "fourway"]
    candidates = fourways or roads
    anchor = min(
        candidates,
        key=lambda e: (float(e["position"]["x"]) - mx) ** 2 + (float(e["position"]["z"]) - mz) ** 2,
    )
    return (
        float(anchor["position"]["x"]),
        float(anchor["position"]["y"]),
        float(anchor["position"]["z"]),
    )


def occupied_key(x: float, z: float) -> tuple[int, int]:
    return (int(round(x / 10.0)), int(round(z / 10.0)))


def compile_road_network(source_path: Path, output_path: Path, grid_size: int, max_additions: int) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source FPM.")

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}

        templates, existing_roads = choose_templates(parsed, ele_data)
        ox, oy, oz = choose_origin(existing_roads)
        road_y_median = statistics.median(float(e["position"]["y"]) for e in existing_roads)
        relative = plan_relative_network(grid_size)

        occupied = {occupied_key(float(e["position"]["x"]), float(e["position"]["z"])) for e in existing_roads}
        new_records: list[bytes] = []
        placements: list[dict[str, Any]] = []
        used_counts = {kind: 0 for kind in EXPECTED_DEGREE}
        skipped_existing = 0

        for planned in relative:
            x = ox + planned.x
            z = oz + planned.z
            key = occupied_key(x, z)
            if key in occupied:
                skipped_existing += 1
                continue
            template = templates[planned.kind]
            source_y = float(template.entity["position"]["y"])
            y = oy + (source_y - road_y_median)
            yaw = yaw_for_mask(template, planned.mask)
            clone_template = base.Template(
                role=f"road_{planned.kind}",
                asset_path=str(template.entity.get("asset") or ""),
                parsed=template.entity,
                raw_record=template.raw_record,
                source_fpm=str(source_path),
                source_kind="exact-cybercity-road-record",
            )
            placement = base.Placement(
                role=f"road_{planned.kind}",
                x=x,
                y=y,
                z=z,
                ry=yaw,
                note=planned.note,
            )
            new_records.append(
                _patched_patch_record(clone_template, int(template.entity["bankindex"]), placement)
            )
            occupied.add(key)
            used_counts[planned.kind] += 1
            placements.append(
                {
                    "kind": planned.kind,
                    "asset": template.entity.get("asset"),
                    "x": x,
                    "y": y,
                    "z": z,
                    "yaw": yaw,
                    "connections": sorted(planned.mask),
                    "note": planned.note,
                }
            )

        missing_use = [kind for kind, count in used_counts.items() if count == 0]
        if missing_use:
            raise FpmError("Generated road network failed to use road kinds: " + ", ".join(missing_use))
        if len(new_records) > max_additions:
            raise FpmError(
                f"Road plan adds {len(new_records)} entities, above --max-additions={max_additions}."
            )

        new_ele = bytearray(ele_data)
        struct.pack_into("<i", new_ele, 4, int(parsed["entity_count"]) + len(new_records))
        for record in new_records:
            new_ele += record
        members = base.archive_members_with_replacements(source, {"map.ele": bytes(new_ele)})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_zipcrypto_archive(output_path, members)

    with FpmArchive(output_path) as generated:
        gent = parse_map_ent(generated.read("map.ent"))
        gele = generated.read("map.ele")
        gparsed = parse_map_ele(gele, gent["entries"])
        generated_manifest = {row["name"]: row["sha256"] for row in generated.member_manifest()}

    expected_count = int(parsed["entity_count"]) + len(new_records)
    if int(gparsed["entity_count"]) != expected_count or not gparsed["fully_traversed"] or gparsed["trailing_bytes"] != 0:
        raise FpmError("Generated road-network FPM failed exact ELE traversal/count verification.")
    changed = sorted(name for name, sha in generated_manifest.items() if source_manifest.get(name) != sha)
    allowed = {name for name in generated_manifest if name.replace("\\", "/").lower() == "map.ele"}
    if set(changed) - allowed:
        raise FpmError("Generated road network changed unrelated FPM members: " + ", ".join(sorted(set(changed) - allowed)))

    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "grid_size": grid_size,
        "node_spacing": 1800.0,
        "origin": {"x": ox, "y": oy, "z": oz},
        "ele_version": parsed["version"],
        "old_entity_count": parsed["entity_count"],
        "new_entity_count": gparsed["entity_count"],
        "added_entities": len(new_records),
        "skipped_existing_road_centers": skipped_existing,
        "used_counts": used_counts,
        "template_masks": {
            kind: {
                "record_index": t.entity["record_index"],
                "asset": t.entity.get("asset"),
                "source_yaw": t.entity["rotation_euler"]["y"],
                "connections": sorted(t.mask),
            }
            for kind, t in templates.items()
        },
        "changed_decrypted_members": changed,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "placements": placements,
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 road network compiler")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"Grid: {report['grid_size']} x {report['grid_size']} nodes @ {report['node_spacing']:.0f} units")
    o = report["origin"]
    print(f"Origin: ({o['x']:.1f}, {o['y']:.1f}, {o['z']:.1f})")
    print(f"Entities: {report['old_entity_count']} -> {report['new_entity_count']} (+{report['added_entities']})")
    print(f"Existing road centers reused: {report['skipped_existing_road_centers']}")
    print("Road modules added:")
    for kind in ("fourway", "tee", "curve", "straight4", "straight2"):
        print(f"  {kind:10s} {report['used_counts'][kind]}")
    print("[PASS] Every Cyber City road module type is present in the generated network.")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print("[PASS] map.ent and every non-map.ele FPM payload are unchanged.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_fpm", type=Path)
    p.add_argument("output_fpm", type=Path)
    p.add_argument("--grid-size", type=int, default=7)
    p.add_argument("--max-additions", type=int, default=1200)
    p.add_argument("--report-json", type=Path)
    args = p.parse_args(argv)
    try:
        report = compile_road_network(args.source_fpm, args.output_fpm, args.grid_size, args.max_additions)
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM ROAD NETWORK ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
