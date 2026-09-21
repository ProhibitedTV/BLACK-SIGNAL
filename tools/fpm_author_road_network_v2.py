#!/usr/bin/env python3
"""Rebuild District 12 from a clean Cyber City road foundation.

This compiler removes the stock Streets and Sidewalks placements from the donor
FPM, then authors a deterministic connected road network before any buildings or
street furniture are added back.

Road geometry used:
- CS_Street_4_Way_2
- CS_Street_T-Intersect_3
- CS_Street_Curve_1
- CS_Street_Straight_4X
- CS_Street_Straight_2X
- CS_Street_Straight
- CS_Street_Straight_Quarter

Exact same-version placed records are preferred. If the small straight pieces
are not present in CyberCity.fpm, the tool searches sibling FPMs and finally
uses a static road record as a bank-extension carrier while pointing bankindex
at the correct installed DLC FPE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, FrozenSet

import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

DIRS = ("N", "E", "S", "W")

ROAD_SPECS: dict[str, dict[str, Any]] = {
    "fourway": {
        "basename": "CS_Street_4_Way_2.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_4_Way_2.fpe",
        "canonical": frozenset(("N", "E", "S", "W")),
    },
    "tee": {
        "basename": "CS_Street_T-Intersect_3.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_T-Intersect_3.fpe",
        # Fallback only. Exact placed T records normally let us infer this.
        "canonical": frozenset(("E", "W", "S")),
    },
    "curve": {
        "basename": "CS_Street_Curve_1.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Curve_1.fpe",
        # Fallback only. Relaxed neighbor inference is preferred for the donor.
        "canonical": frozenset(("E", "S")),
    },
    "straight4": {
        "basename": "CS_Street_Straight_4X.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight_4X.fpe",
        "canonical": frozenset(("N", "S")),
    },
    "straight2": {
        "basename": "CS_Street_Straight_2X.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight_2X.fpe",
        "canonical": frozenset(("N", "S")),
    },
    "straight1": {
        "basename": "CS_Street_Straight.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight.fpe",
        "canonical": frozenset(("N", "S")),
    },
    "quarter": {
        "basename": "CS_Street_Straight_Quarter.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight_Quarter.fpe",
        "canonical": frozenset(("N", "S")),
    },
}

EXPECTED_DEGREE = {
    "fourway": 4,
    "tee": 3,
    "curve": 2,
    "straight4": 2,
    "straight2": 2,
    "straight1": 2,
    "quarter": 2,
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
    asset_path: str
    entity: dict[str, Any]
    raw_record: bytes
    source_fpm: str
    source_kind: str
    canonical_mask: FrozenSet[str]


def norm_asset(value: str | None) -> str:
    p = (value or "").replace("/", "\\").lower().lstrip("\\")
    if p.startswith("entitybank\\"):
        p = p[len("entitybank\\") :]
    return p


def basename(value: str | None) -> str:
    return norm_asset(value).rsplit("\\", 1)[-1]


def same_asset(value: str | None, wanted: str) -> bool:
    return basename(value) == wanted.lower()


def rotate_mask(mask: FrozenSet[str], steps: int) -> FrozenSet[str]:
    out: set[str] = set()
    for d in mask:
        out.add(DIRS[(DIRS.index(d) + steps) % 4])
    return frozenset(out)


def nearest_quarter_turn(yaw: float) -> int:
    return int(round((yaw % 360.0) / 90.0)) % 4


def road_kind(value: str | None) -> str | None:
    name = basename(value)
    for kind, spec in ROAD_SPECS.items():
        if name == spec["basename"].lower():
            return kind
    return None


def cloneable(entity: dict[str, Any]) -> bool:
    if int(entity.get("record_index", 0)) == 1:
        return False
    if int(entity.get("v319_group_count", 0) or 0) != 0:
        return False
    return int(entity.get("staticflag", 0)) in (0, 1)


def directional_neighbor_mask(
    entity: dict[str, Any], roads: list[dict[str, Any]], expected: int
) -> FrozenSet[str] | None:
    """Infer road exits without requiring road centers to be perfectly collinear.

    The old compiler used a +/-75-unit perpendicular tolerance, which fails on
    Curve_1 because the neighboring straight centers are offset around the arc.
    This scores nearby road centers by direction sector instead.
    """
    p = entity["position"]
    x = float(p["x"])
    z = float(p["z"])
    best: dict[str, float] = {}
    for other in roads:
        if int(other["record_index"]) == int(entity["record_index"]):
            continue
        q = other["position"]
        dx = float(q["x"]) - x
        dz = float(q["z"]) - z
        dist = math.hypot(dx, dz)
        if dist < 80.0 or dist > 1450.0:
            continue
        candidates = {
            "E": dx / dist,
            "W": -dx / dist,
            "N": dz / dist,
            "S": -dz / dist,
        }
        direction, alignment = max(candidates.items(), key=lambda item: item[1])
        if alignment < 0.62:
            continue
        score = dist * (1.0 + (1.0 - alignment) * 2.0)
        if direction not in best or score < best[direction]:
            best[direction] = score

    if expected == 4 and len(best) >= 4:
        return frozenset(DIRS)
    if expected == 3 and len(best) >= 3:
        choices = []
        for missing in DIRS:
            mask = frozenset(d for d in DIRS if d != missing)
            if all(d in best for d in mask):
                choices.append((sum(best[d] for d in mask), mask))
        if choices:
            return min(choices, key=lambda row: row[0])[1]
    if expected == 2 and len(best) >= 2:
        # Curves need adjacent exits; straights need opposite exits. The caller
        # validates shape using the road kind.
        pairs: list[tuple[float, FrozenSet[str]]] = []
        for i, a in enumerate(DIRS):
            for b in DIRS[i + 1 :]:
                if a in best and b in best:
                    pairs.append((best[a] + best[b], frozenset((a, b))))
        if pairs:
            return min(pairs, key=lambda row: row[0])[1]
    return None


def mask_shape_ok(kind: str, mask: FrozenSet[str] | None) -> bool:
    if mask is None or len(mask) != EXPECTED_DEGREE[kind]:
        return False
    if kind == "curve":
        return mask not in (frozenset(("N", "S")), frozenset(("E", "W")))
    if kind.startswith("straight") or kind == "quarter":
        return mask in (frozenset(("N", "S")), frozenset(("E", "W")))
    return True


def canonical_from_placed(kind: str, entity: dict[str, Any], roads: list[dict[str, Any]]) -> FrozenSet[str]:
    inferred = directional_neighbor_mask(entity, roads, EXPECTED_DEGREE[kind])
    if mask_shape_ok(kind, inferred):
        steps = nearest_quarter_turn(float(entity["rotation_euler"]["y"]))
        return rotate_mask(inferred, -steps)
    return ROAD_SPECS[kind]["canonical"]


def exact_template_from_archive(
    kind: str,
    archive_path: Path,
    target_version: int | None = None,
) -> tuple[RoadTemplate | None, int | None]:
    try:
        with FpmArchive(archive_path) as archive:
            ent = parse_map_ent(archive.read("map.ent"))
            ele_data = archive.read("map.ele")
            parsed = parse_map_ele(ele_data, ent["entries"])
            if target_version is not None and int(parsed["version"]) != int(target_version):
                return None, int(parsed["version"])
            roads = [e for e in parsed["entities"] if road_kind(e.get("asset")) is not None]
            candidates = [
                e
                for e in roads
                if road_kind(e.get("asset")) == kind and cloneable(e)
            ]
            if not candidates:
                return None, int(parsed["version"])
            # Prefer the placed record whose neighborhood provides a believable
            # topology mask, then the earliest record for deterministic output.
            ranked = []
            for entity in candidates:
                inferred = directional_neighbor_mask(entity, roads, EXPECTED_DEGREE[kind])
                shape = 1 if mask_shape_ok(kind, inferred) else 0
                ranked.append(((shape, -int(entity["record_index"])), entity))
            ranked.sort(key=lambda row: row[0], reverse=True)
            entity = ranked[0][1]
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            return (
                RoadTemplate(
                    kind=kind,
                    asset_path=str(entity.get("asset") or ROAD_SPECS[kind]["path"]),
                    entity=entity,
                    raw_record=ele_data[start:end],
                    source_fpm=str(archive_path),
                    source_kind="exact-placed-record",
                    canonical_mask=canonical_from_placed(kind, entity, roads),
                ),
                int(parsed["version"]),
            )
    except Exception:
        return None, None


def find_templates(
    source_path: Path,
    parsed: dict[str, Any],
    ent: dict[str, Any],
    ele_data: bytes,
) -> tuple[dict[str, RoadTemplate], list[str]]:
    target_version = int(parsed["version"])
    roads = [e for e in parsed["entities"] if road_kind(e.get("asset")) is not None]
    templates: dict[str, RoadTemplate] = {}
    generic_imports: list[str] = []

    for kind in ROAD_SPECS:
        candidates = [e for e in roads if road_kind(e.get("asset")) == kind and cloneable(e)]
        if candidates:
            ranked = []
            for entity in candidates:
                inferred = directional_neighbor_mask(entity, roads, EXPECTED_DEGREE[kind])
                ranked.append(((1 if mask_shape_ok(kind, inferred) else 0, -int(entity["record_index"])), entity))
            ranked.sort(key=lambda row: row[0], reverse=True)
            entity = ranked[0][1]
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            templates[kind] = RoadTemplate(
                kind,
                str(entity.get("asset") or ROAD_SPECS[kind]["path"]),
                entity,
                ele_data[start:end],
                str(source_path),
                "target",
                canonical_from_placed(kind, entity, roads),
            )

    missing = [kind for kind in ROAD_SPECS if kind not in templates]
    if missing:
        donor_paths = fabric.candidate_fpm_paths([source_path.parent], {source_path})
        for donor in donor_paths:
            if not missing:
                break
            for kind in list(missing):
                template, version = exact_template_from_archive(kind, donor, target_version)
                if template is not None and version == target_version:
                    template.source_kind = "same-version-donor"
                    templates[kind] = template
                    missing.remove(kind)

    # Straight and Quarter exist in the installed Cyber City Streets pack but
    # are not necessarily placed in CyberCity.fpm. They are ordinary static road
    # meshes, so use an exact Straight_4X target record as the conservative bank
    # extension carrier if no same-version donor places them.
    if missing:
        carrier = templates.get("straight4")
        if carrier is None:
            raise FpmError("No exact Straight_4X road record is available for static road imports.")
        for kind in list(missing):
            if kind not in ("straight1", "quarter", "straight2"):
                continue
            templates[kind] = RoadTemplate(
                kind,
                ROAD_SPECS[kind]["path"],
                carrier.entity,
                carrier.raw_record,
                carrier.source_fpm,
                "generic-static-road-bank-extension",
                ROAD_SPECS[kind]["canonical"],
            )
            generic_imports.append(kind)
            missing.remove(kind)

    if missing:
        raise FpmError("Could not source required road modules: " + ", ".join(missing))
    return templates, generic_imports


def node_kind_mask(ix: int, iz: int, size: int) -> tuple[str, FrozenSet[str]]:
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
    return "fourway", frozenset(DIRS)


def middle_pattern(ix: int, iz: int, axis: str) -> int:
    salt = 0 if axis == "H" else 3
    return (ix * 7 + iz * 11 + salt) % 4


def span_modules(start: float, pattern: int) -> list[tuple[float, str]]:
    # The middle 400-unit run from 700..1100 is expressed several ways so every
    # installed straight road length participates in the finished network.
    out: list[tuple[float, str]] = [(start + 500.0, "straight4")]
    if pattern == 0:
        out.append((start + 900.0, "straight4"))
    elif pattern == 1:
        out.extend(((start + 800.0, "straight2"), (start + 1000.0, "straight2")))
    elif pattern == 2:
        out.extend(
            (
                (start + 800.0, "straight2"),
                (start + 950.0, "straight1"),
                (start + 1012.5, "quarter"),
                (start + 1037.5, "quarter"),
                (start + 1062.5, "quarter"),
                (start + 1087.5, "quarter"),
            )
        )
    else:
        out.extend(
            (
                (start + 750.0, "straight1"),
                (start + 850.0, "straight1"),
                (start + 950.0, "straight1"),
                (start + 1050.0, "straight1"),
            )
        )
    out.append((start + 1300.0, "straight4"))
    return out


def plan_network(grid_size: int, spacing: float = 1800.0) -> list[PlannedRoad]:
    if grid_size < 5 or grid_size % 2 == 0:
        raise ValueError("grid_size must be an odd integer >= 5")
    half = grid_size // 2
    coords = [(i - half) * spacing for i in range(grid_size)]
    plan: list[PlannedRoad] = []

    for iz, z in enumerate(coords):
        for ix, x in enumerate(coords):
            kind, mask = node_kind_mask(ix, iz, grid_size)
            plan.append(PlannedRoad(kind, x, z, mask, f"node-{ix}-{iz}"))

    for iz, z in enumerate(coords):
        for ix in range(grid_size - 1):
            for x, kind in span_modules(coords[ix], middle_pattern(ix, iz, "H")):
                plan.append(PlannedRoad(kind, x, z, frozenset(("E", "W")), f"h-{ix}-{iz}"))

    for ix, x in enumerate(coords):
        for iz in range(grid_size - 1):
            for z, kind in span_modules(coords[iz], middle_pattern(ix, iz, "V")):
                plan.append(PlannedRoad(kind, x, z, frozenset(("N", "S")), f"v-{ix}-{iz}"))
    return plan


def yaw_for_mask(template: RoadTemplate, wanted: FrozenSet[str]) -> float:
    for steps in range(4):
        if rotate_mask(template.canonical_mask, steps) == wanted:
            return float(steps * 90)
    raise FpmError(
        f"Cannot orient {template.kind}: canonical={sorted(template.canonical_mask)} wanted={sorted(wanted)}"
    )


def choose_origin(existing_roads: list[dict[str, Any]]) -> tuple[float, float, float]:
    if not existing_roads:
        raise FpmError("CyberCity donor has no road entities to establish the city plane.")
    mx = statistics.median(float(e["position"]["x"]) for e in existing_roads)
    mz = statistics.median(float(e["position"]["z"]) for e in existing_roads)
    junctions = [e for e in existing_roads if road_kind(e.get("asset")) == "fourway"]
    candidates = junctions or existing_roads
    anchor = min(
        candidates,
        key=lambda e: (float(e["position"]["x"]) - mx) ** 2 + (float(e["position"]["z"]) - mz) ** 2,
    )
    ground_y = statistics.median(float(e["position"]["y"]) for e in existing_roads)
    return float(anchor["position"]["x"]), ground_y, float(anchor["position"]["z"])


def strip_for_road_foundation(entity: dict[str, Any]) -> bool:
    p = norm_asset(entity.get("asset"))
    if p.startswith("cyberpunk streets booster pack\\streets and sidewalks\\"):
        return True
    # Clear stale curb furniture from previous/stock street dressing so the new
    # road foundation can be judged without floating lamps, rails or planters.
    if p.startswith("cyberpunk streets booster pack\\misc\\sidewalk misc\\"):
        return True
    return False


def compile_network(source_path: Path, output_path: Path, grid_size: int, max_additions: int) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source FPM.")

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        if ent["encoding"] != "crlf":
            raise FpmError("Road writer requires CRLF map.ent encoding.")
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}

        existing_roads = [e for e in parsed["entities"] if road_kind(e.get("asset")) is not None]
        templates, generic_imports = find_templates(source_path, parsed, ent, ele_data)
        ox, oy, oz = choose_origin(existing_roads)
        plan = plan_network(grid_size)
        if len(plan) > max_additions:
            raise FpmError(f"Road plan adds {len(plan)} road records, above --max-additions={max_additions}.")

        bank_paths = [entry["path"] for entry in ent["entries"]]
        lookup = {norm_asset(path): i + 1 for i, path in enumerate(bank_paths)}
        bank_index: dict[str, int] = {}
        for kind, template in templates.items():
            path = template.asset_path
            if template.source_kind == "generic-static-road-bank-extension":
                path = ROAD_SPECS[kind]["path"]
            key = norm_asset(path)
            if key not in lookup:
                bank_paths.append(path)
                lookup[key] = len(bank_paths)
            bank_index[kind] = lookup[key]

        # Keep everything except old street-system and curb-dressing placements.
        kept_records: list[bytes] = []
        removed = 0
        for entity in parsed["entities"]:
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            if strip_for_road_foundation(entity):
                removed += 1
                continue
            kept_records.append(ele_data[start:end])

        new_records: list[bytes] = []
        placements: list[dict[str, Any]] = []
        used_counts = {kind: 0 for kind in ROAD_SPECS}
        for item in plan:
            template = templates[item.kind]
            yaw = yaw_for_mask(template, item.mask)
            placement = fabric.Placement(
                role=f"road_{item.kind}",
                x=ox + item.x,
                y=oy,
                z=oz + item.z,
                ry=yaw,
                note=item.note,
            )
            carrier = fabric.Template(
                role=placement.role,
                asset_path=template.asset_path,
                parsed=template.entity,
                raw_record=template.raw_record,
                source_fpm=template.source_fpm,
                source_kind=template.source_kind,
            )
            new_records.append(_patched_patch_record(carrier, bank_index[item.kind], placement))
            used_counts[item.kind] += 1
            placements.append(
                {
                    "kind": item.kind,
                    "asset": ROAD_SPECS[item.kind]["basename"],
                    "x": placement.x,
                    "y": placement.y,
                    "z": placement.z,
                    "yaw": yaw,
                    "connections": sorted(item.mask),
                    "note": item.note,
                }
            )

        missing_use = [kind for kind, count in used_counts.items() if count == 0]
        if missing_use:
            raise FpmError("Generated network did not use road modules: " + ", ".join(missing_use))

        new_count = len(kept_records) + len(new_records)
        new_ele = bytearray(ele_data[:8])
        struct.pack_into("<i", new_ele, 4, new_count)
        for record in kept_records:
            new_ele += record
        for record in new_records:
            new_ele += record
        new_ent = fabric.serialize_map_ent(bank_paths)
        members = fabric.archive_members_with_replacements(
            source,
            {"map.ent": new_ent, "map.ele": bytes(new_ele)},
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_zipcrypto_archive(output_path, members)

    with FpmArchive(output_path) as generated:
        gent = parse_map_ent(generated.read("map.ent"))
        gele = generated.read("map.ele")
        gparsed = parse_map_ele(gele, gent["entries"])
        generated_manifest = {row["name"]: row["sha256"] for row in generated.member_manifest()}

    if int(gparsed["entity_count"]) != new_count or not gparsed["fully_traversed"] or int(gparsed["trailing_bytes"]) != 0:
        raise FpmError("Generated road FPM failed exact ELE traversal/count verification.")
    changed = sorted(name for name, sha in generated_manifest.items() if source_manifest.get(name) != sha)
    allowed = {
        name
        for name in generated_manifest
        if name.replace("\\", "/").lower() in {"map.ent", "map.ele"}
    }
    if set(changed) - allowed:
        raise FpmError("Road compiler changed unrelated FPM members: " + ", ".join(sorted(set(changed) - allowed)))

    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "grid_size": grid_size,
        "node_spacing": 1800.0,
        "origin": {"x": ox, "y": oy, "z": oz},
        "ele_version": int(parsed["version"]),
        "old_entity_count": int(parsed["entity_count"]),
        "removed_old_street_entities": removed,
        "new_entity_count": int(gparsed["entity_count"]),
        "added_road_entities": len(new_records),
        "old_bank_count": int(ent["count"]),
        "new_bank_count": int(gent["count"]),
        "generic_static_imports": generic_imports,
        "used_counts": used_counts,
        "template_sources": {
            kind: {
                "asset": ROAD_SPECS[kind]["basename"],
                "source_kind": t.source_kind,
                "source_fpm": t.source_fpm,
                "canonical_connections_at_yaw0": sorted(t.canonical_mask),
            }
            for kind, t in templates.items()
        },
        "changed_decrypted_members": changed,
        "placements": placements,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 road foundation v2")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"Grid: {report['grid_size']} x {report['grid_size']} nodes @ {report['node_spacing']:.0f} units")
    o = report["origin"]
    print(f"Origin: ({o['x']:.1f}, {o['y']:.1f}, {o['z']:.1f})")
    print(f"Removed old street/dressing entities: {report['removed_old_street_entities']}")
    print(f"Added road entities: {report['added_road_entities']}")
    print(f"Entities: {report['old_entity_count']} -> {report['new_entity_count']}")
    print(f"Entity bank: {report['old_bank_count']} -> {report['new_bank_count']}")
    print("Road modules used:")
    for kind in ("fourway", "tee", "curve", "straight4", "straight2", "straight1", "quarter"):
        print(f"  {kind:10s} {report['used_counts'][kind]}")
    if report["generic_static_imports"]:
        print("Static installed-DLC bank extensions: " + ", ".join(report["generic_static_imports"]))
    print("[PASS] All seven road-surface module types are used.")
    print("[PASS] Old stock street-system placements were removed before rebuilding.")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print("[PASS] Only map.ent/map.ele changed.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_fpm", type=Path)
    p.add_argument("output_fpm", type=Path)
    p.add_argument("--grid-size", type=int, default=7)
    p.add_argument("--max-additions", type=int, default=1800)
    p.add_argument("--report-json", type=Path)
    args = p.parse_args(argv)
    try:
        report = compile_network(args.source_fpm, args.output_fpm, args.grid_size, args.max_additions)
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM ROAD NETWORK V2 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
