#!/usr/bin/env python3
"""Add a deterministic Cyberpunk Streets surface-detail pass to District 12.

Road-system v4 establishes the important structural contract first: one coherent
full-width road family, properly oriented center markings, crosswalks, lamps and
intersection bollards. This v5 pass adds the smaller details that make a large city
road network read as authored rather than freshly tiled asphalt.

The pass uses only real Cyberpunk Streets Booster Pack assets confirmed on the
BLACK SIGNAL workstation:
- asphalt/wear decals 01-09;
- directional arrow decals and SLOW/ONLY indicators;
- CS_Street_Manhole_Cover utility covers.

Placements are deterministic and road-aware. Every straight module receives one
subtle asphalt/wear treatment, intersection approaches receive lane indicators,
manholes recur on a controlled cadence, and junction centers receive restrained
wear/utility detail. Nothing is randomly scattered and road geometry is never
changed by this pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fpm_author_road_network_v2 as legacy
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


SURFACE_ASSETS: dict[str, dict[str, str]] = {
    **{
        f"road_wear_{i:02d}": {
            "basename": f"CS_Street_Decal_{i:02d}.fpe",
            "path": rf"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Decal_{i:02d}.fpe",
            "category": "decal",
        }
        for i in range(1, 10)
    },
    "road_arrow_left": {
        "basename": "CS_Street_Left_Turn_Arrow_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Left_Turn_Arrow_Decal.fpe",
        "category": "decal",
    },
    "road_arrow_right": {
        "basename": "CS_Street_Right_Turn_Arrow_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Right_Turn_Arrow_Decal.fpe",
        "category": "decal",
    },
    "road_arrow_straight": {
        "basename": "CS_Street_Straight_Arrow_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Straight_Arrow_Decal.fpe",
        "category": "decal",
    },
    "road_arrow_straight_left": {
        "basename": "CS_Street_Straight_Left_Arrow_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Straight_Left_Arrow_Decal.fpe",
        "category": "decal",
    },
    "road_arrow_straight_right": {
        "basename": "CS_Street_Straight_Right_Arrow_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Straight_Right_Arrow_Decal.fpe",
        "category": "decal",
    },
    "road_slow": {
        "basename": "CS_Street_Slow_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Slow_Decal.fpe",
        "category": "decal",
    },
    "road_only": {
        "basename": "CS_Street_Only_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Only_Decal.fpe",
        "category": "decal",
    },
    "manhole_cover": {
        "basename": "CS_Street_Manhole_Cover.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Manhole_Cover.fpe",
        "category": "prop",
    },
}

WEAR_ROLES = tuple(f"road_wear_{i:02d}" for i in range(1, 10))
ARROW_ROLES = (
    "road_arrow_left",
    "road_arrow_right",
    "road_arrow_straight",
    "road_arrow_straight_left",
    "road_arrow_straight_right",
)
OWNED_BASENAMES = frozenset(
    fabric.basename(spec["basename"]) for spec in SURFACE_ASSETS.values()
)

# The road-decal meshes use the same quarter-turn visual axis convention as the
# center-line asset corrected in v4. Wear decals are non-directional; arrow/text
# decals need this correction so the glyphs point along the road rather than across it.
DECAL_AXIS_CORRECTION = 90.0
ROAD_SURFACE_Y = 1.15
MANHOLE_Y = 0.65
APPROACH_SEARCH_RADIUS = 650.0


@dataclass(frozen=True)
class PlannedSurfaceDetail:
    role: str
    road_kind: str
    x: float
    y: float
    z: float
    ry: float
    road_record_index: int
    note: str


def _stable_seed(entity: dict[str, Any]) -> int:
    p = entity["position"]
    xi = int(round(float(p["x"]) / 25.0))
    zi = int(round(float(p["z"]) / 25.0))
    kind = legacy.road_kind(entity.get("asset")) or "unknown"
    salt = {
        "straight4": 0x2D,
        "fourway": 0x59,
        "tee": 0x83,
        "curve": 0xA7,
    }.get(kind, 0x11)
    value = ((xi * 73856093) ^ (zi * 19349663) ^ (salt * 83492791)) & 0x7FFFFFFF
    return value


def _road_local_offset(
    road: dict[str, Any], target: dict[str, Any]
) -> tuple[float, float]:
    rp = road["position"]
    tp = target["position"]
    dx = float(tp["x"]) - float(rp["x"])
    dz = float(tp["z"]) - float(rp["z"])
    yaw = float(road["rotation_euler"]["y"])
    return fabric.rotate_local(dx, dz, -yaw)


def _nearest_junction(
    road: dict[str, Any], junctions: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float, float]:
    best: tuple[float, dict[str, Any], float, float] | None = None
    for junction in junctions:
        local_x, local_z = _road_local_offset(road, junction)
        distance = math.hypot(local_x, local_z)
        if distance > APPROACH_SEARCH_RADIUS:
            continue
        candidate = (distance, junction, local_x, local_z)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:
        return None, 0.0, 0.0
    return best[1], best[2], best[3]


def _world_placement(
    role: str,
    road: dict[str, Any],
    local_x: float,
    local_z: float,
    y_offset: float,
    *,
    yaw_offset: float = 0.0,
    road_kind: str | None = None,
    note: str = "",
) -> PlannedSurfaceDetail:
    rp = road["position"]
    yaw = float(road["rotation_euler"]["y"])
    ox, oz = fabric.rotate_local(local_x, local_z, yaw)
    return PlannedSurfaceDetail(
        role=role,
        road_kind=road_kind or (legacy.road_kind(road.get("asset")) or "unknown"),
        x=float(rp["x"]) + ox,
        y=float(rp["y"]) + y_offset,
        z=float(rp["z"]) + oz,
        ry=(yaw + yaw_offset) % 360.0,
        road_record_index=int(road["record_index"]),
        note=note,
    )


def _approach_arrow_role(junction_kind: str, seed: int) -> str:
    if junction_kind == "fourway":
        return (
            "road_arrow_straight_left",
            "road_arrow_straight",
            "road_arrow_straight_right",
        )[seed % 3]
    if junction_kind == "tee":
        return ("road_arrow_left", "road_arrow_right", "road_arrow_straight")[seed % 3]
    return "road_arrow_straight"


def plan_surface_details(parsed: dict[str, Any]) -> list[PlannedSurfaceDetail]:
    roads = [
        e
        for e in parsed["entities"]
        if legacy.road_kind(e.get("asset")) in ("straight4", "fourway", "tee", "curve")
    ]
    straights = sorted(
        [e for e in roads if legacy.road_kind(e.get("asset")) == "straight4"],
        key=lambda e: (
            round(float(e["position"]["x"]), 3),
            round(float(e["position"]["z"]), 3),
            int(e["record_index"]),
        ),
    )
    junctions = [e for e in roads if legacy.road_kind(e.get("asset")) != "straight4"]
    placements: list[PlannedSurfaceDetail] = []

    for road in straights:
        seed = _stable_seed(road)
        wear_role = WEAR_ROLES[seed % len(WEAR_ROLES)]
        wear_lane = -62.0 if (seed & 1) else 62.0
        wear_z = (-72.0, 0.0, 72.0)[(seed >> 2) % 3]
        placements.append(
            _world_placement(
                wear_role,
                road,
                wear_lane,
                wear_z,
                ROAD_SURFACE_Y,
                yaw_offset=float((seed >> 4) % 4) * 90.0,
                note="deterministic asphalt wear / patch variation",
            )
        )

        # Utility covers recur often enough to make the street believable without
        # turning every module into a repeated prop stamp. Alternate lane side and
        # longitudinal offset to break visible tiling while remaining deterministic.
        if seed % 3 == 0:
            cover_x = -96.0 if ((seed >> 5) & 1) else 96.0
            cover_z = -78.0 if ((seed >> 6) & 1) else 78.0
            placements.append(
                _world_placement(
                    "manhole_cover",
                    road,
                    cover_x,
                    cover_z,
                    MANHOLE_Y,
                    yaw_offset=float((seed >> 7) % 4) * 90.0,
                    note="periodic utility/sewer cover in traffic lane",
                )
            )

        junction, _jx, jz = _nearest_junction(road, junctions)
        if junction is not None and abs(jz) > 120.0:
            direction = 1.0 if jz > 0.0 else -1.0
            junction_kind = legacy.road_kind(junction.get("asset")) or "curve"
            # Right-hand traffic: the lane approaching the junction changes side
            # when travel direction reverses.
            lane_x = 94.0 * direction
            arrow_role = _approach_arrow_role(junction_kind, seed)
            arrow_yaw = DECAL_AXIS_CORRECTION + (0.0 if direction > 0.0 else 180.0)
            placements.append(
                _world_placement(
                    arrow_role,
                    road,
                    lane_x,
                    112.0 * direction,
                    ROAD_SURFACE_Y + 0.12,
                    yaw_offset=arrow_yaw,
                    note=f"lane indicator approaching {junction_kind} junction",
                )
            )

            # Sparse regulatory text sits behind the arrow, never on every approach.
            if seed % 4 == 0:
                placements.append(
                    _world_placement(
                        "road_slow",
                        road,
                        lane_x,
                        -18.0 * direction,
                        ROAD_SURFACE_Y + 0.16,
                        yaw_offset=arrow_yaw,
                        note="SLOW indicator behind intersection approach arrow",
                    )
                )
            elif seed % 7 == 0:
                placements.append(
                    _world_placement(
                        "road_only",
                        road,
                        lane_x,
                        -18.0 * direction,
                        ROAD_SURFACE_Y + 0.16,
                        yaw_offset=arrow_yaw,
                        note="ONLY indicator behind intersection approach arrow",
                    )
                )

    # Junction surfaces should not look untouched while every straight segment is
    # weathered. Keep this restrained so crosswalks and v4 bollards stay readable.
    for junction in sorted(
        junctions,
        key=lambda e: (
            round(float(e["position"]["x"]), 3),
            round(float(e["position"]["z"]), 3),
            int(e["record_index"]),
        ),
    ):
        seed = _stable_seed(junction)
        wear_role = WEAR_ROLES[(seed + 3) % len(WEAR_ROLES)]
        placements.append(
            _world_placement(
                wear_role,
                junction,
                0.0,
                0.0,
                ROAD_SURFACE_Y,
                yaw_offset=float((seed >> 3) % 4) * 90.0,
                note="junction asphalt wear / patch variation",
            )
        )
        if seed % 2 == 0:
            cover_x = -74.0 if (seed & 4) else 74.0
            cover_z = 68.0 if (seed & 8) else -68.0
            placements.append(
                _world_placement(
                    "manhole_cover",
                    junction,
                    cover_x,
                    cover_z,
                    MANHOLE_Y,
                    yaw_offset=float((seed >> 5) % 4) * 90.0,
                    note="junction utility/sewer cover",
                )
            )

    return placements


def _safe_static_record(
    parsed: dict[str, Any], ele_data: bytes, wanted_basenames: tuple[str, ...]
) -> tuple[dict[str, Any], bytes] | None:
    wanted = {name.lower() for name in wanted_basenames}
    for entity in parsed["entities"]:
        if fabric.basename(entity.get("asset")) not in wanted:
            continue
        safe, _reason = fabric.safe_template_entity(entity, False)
        if not safe:
            continue
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        return entity, ele_data[start:end]
    return None


def _exact_template(
    role: str,
    parsed: dict[str, Any],
    ele_data: bytes,
    source_path: Path,
    source_kind: str,
) -> fabric.Template | None:
    wanted = SURFACE_ASSETS[role]["basename"].lower()
    for entity in parsed["entities"]:
        if fabric.basename(entity.get("asset")) != wanted:
            continue
        safe, _reason = fabric.safe_template_entity(entity, False)
        if not safe:
            continue
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        return fabric.Template(
            role=role,
            asset_path=entity["asset"],
            parsed=entity,
            raw_record=ele_data[start:end],
            source_fpm=str(source_path),
            source_kind=source_kind,
        )
    return None


def _carrier_template(
    role: str,
    source_path: Path,
    parsed: dict[str, Any],
    ele_data: bytes,
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> fabric.Template:
    category = SURFACE_ASSETS[role]["category"]
    if category == "decal":
        preferred = (
            "CS_Street_Double_Center_Line.fpe",
            "CS_Street_Crosswalk_Decal.fpe",
            "CS_Street_Decal_01.fpe",
        )
    else:
        preferred = (
            "CS_Street_Crosswalk_Metal_Blocker_Post.fpe",
            "CS_Street_Lamp.fpe",
            "CS_Street_Manhole_Cover.fpe",
        )

    carrier = _safe_static_record(donor_parsed, donor_ele, preferred)
    carrier_source = donor_path
    carrier_kind = f"generic-static-{category}-bank-extension"
    if carrier is None:
        carrier = _safe_static_record(parsed, ele_data, preferred)
        carrier_source = source_path
    if carrier is None:
        raise FpmError(
            f"No safe static {category} record is available to import {SURFACE_ASSETS[role]['basename']}."
        )

    entity, raw_record = carrier
    return fabric.Template(
        role=role,
        asset_path=SURFACE_ASSETS[role]["path"],
        parsed=entity,
        raw_record=raw_record,
        source_fpm=str(carrier_source),
        source_kind=carrier_kind,
    )


def build_templates(
    source_path: Path,
    parsed: dict[str, Any],
    ele_data: bytes,
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> dict[str, fabric.Template]:
    templates: dict[str, fabric.Template] = {}
    for role in SURFACE_ASSETS:
        template = _exact_template(role, parsed, ele_data, source_path, "target-exact")
        if template is None:
            template = _exact_template(role, donor_parsed, donor_ele, donor_path, "cybercity-exact")
        if template is None:
            template = _carrier_template(
                role,
                source_path,
                parsed,
                ele_data,
                donor_path,
                donor_parsed,
                donor_ele,
            )
        templates[role] = template
    return templates


def _strip_owned_surface_detail(entity: dict[str, Any]) -> bool:
    return fabric.basename(entity.get("asset")) in OWNED_BASENAMES


def compile_surface_details(
    source_path: Path,
    output_path: Path,
    donor_path: Path,
    max_additions: int,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    donor_path = donor_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source FPM.")

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        if ent["encoding"] != "crlf":
            raise FpmError("Road-surface writer requires CRLF map.ent encoding.")
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}

        # Keep the same strict road grammar contract as v4. This dressing pass must
        # never become a path for reintroducing mixed road sizes.
        import fpm_author_road_details_v4 as v4

        road_counts = v4.validate_uniform_grammar(parsed)

        with FpmArchive(donor_path) as donor:
            dent = parse_map_ent(donor.read("map.ent"))
            donor_ele = donor.read("map.ele")
            donor_parsed = parse_map_ele(donor_ele, dent["entries"])
            verify_raw_ele_roundtrip(donor_ele, donor_parsed)
            if donor_parsed["version"] != parsed["version"]:
                raise FpmError(
                    "CyberCity donor ELE version does not match the road-system target "
                    f"({donor_parsed['version']} != {parsed['version']})."
                )

            templates = build_templates(
                source_path,
                parsed,
                ele_data,
                donor_path,
                donor_parsed,
                donor_ele,
            )

        plan = plan_surface_details(parsed)
        if len(plan) > max_additions:
            raise FpmError(
                f"Road surface plan adds {len(plan)} entities, above --max-additions={max_additions}."
            )

        bank_paths = [entry["path"] for entry in ent["entries"]]
        bank_lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
        role_bank: dict[str, int] = {}
        for role, template in templates.items():
            key = fabric.norm(template.asset_path)
            if key not in bank_lookup:
                bank_paths.append(template.asset_path)
                bank_lookup[key] = len(bank_paths)
            role_bank[role] = bank_lookup[key]

        kept_records: list[bytes] = []
        removed_existing = 0
        for entity in parsed["entities"]:
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            if _strip_owned_surface_detail(entity):
                removed_existing += 1
                continue
            kept_records.append(ele_data[start:end])

        new_records: list[bytes] = []
        placement_rows: list[dict[str, Any]] = []
        role_counts: dict[str, int] = {}
        seen: set[tuple[str, int, int, int]] = set()
        for item in plan:
            dedupe = (
                item.role,
                int(round(item.x * 10.0)),
                int(round(item.z * 10.0)),
                int(round(item.ry * 10.0)),
            )
            if dedupe in seen:
                continue
            seen.add(dedupe)
            template = templates[item.role]
            placement = fabric.Placement(
                role=item.role,
                x=item.x,
                y=item.y,
                z=item.z,
                ry=item.ry,
                note=item.note,
            )
            new_records.append(_patched_patch_record(template, role_bank[item.role], placement))
            role_counts[item.role] = role_counts.get(item.role, 0) + 1
            placement_rows.append(
                {
                    "role": item.role,
                    "asset": SURFACE_ASSETS[item.role]["basename"],
                    "road_kind": item.road_kind,
                    "x": item.x,
                    "y": item.y,
                    "z": item.z,
                    "ry": item.ry,
                    "road_record_index": item.road_record_index,
                    "note": item.note,
                }
            )

        new_count = len(kept_records) + len(new_records)
        new_ele = bytearray(ele_data[:8])
        struct.pack_into("<i", new_ele, 4, new_count)
        for record in kept_records:
            new_ele += record
        for record in new_records:
            new_ele += record

        new_ent = fabric.serialize_map_ent(bank_paths)
        members = fabric.archive_members_with_replacements(
            source, {"map.ent": new_ent, "map.ele": bytes(new_ele)}
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_zipcrypto_archive(output_path, members)

    with FpmArchive(output_path) as generated:
        gent = parse_map_ent(generated.read("map.ent"))
        gele = generated.read("map.ele")
        gparsed = parse_map_ele(gele, gent["entries"])
        generated_manifest = {
            row["name"]: row["sha256"] for row in generated.member_manifest()
        }

    if (
        int(gparsed["entity_count"]) != new_count
        or not gparsed["fully_traversed"]
        or int(gparsed["trailing_bytes"]) != 0
    ):
        raise FpmError("Generated road-surface FPM failed exact ELE verification.")

    changed = sorted(
        name
        for name, sha in generated_manifest.items()
        if source_manifest.get(name) != sha
    )
    allowed_changed = {
        name
        for name in generated_manifest
        if name.replace("\\", "/").lower() in {"map.ent", "map.ele"}
    }
    if set(changed) - allowed_changed:
        raise FpmError(
            "Road-surface compiler changed unrelated FPM members: "
            + ", ".join(sorted(set(changed) - allowed_changed))
        )

    template_sources = {
        role: {
            "asset": SURFACE_ASSETS[role]["basename"],
            "source_kind": template.source_kind,
            "source_fpm": template.source_fpm,
        }
        for role, template in templates.items()
        if role_counts.get(role, 0) > 0
    }

    return {
        "source_fpm": str(source_path),
        "donor_fpm": str(donor_path),
        "output_fpm": str(output_path),
        "road_counts": road_counts,
        "removed_existing_surface_detail": removed_existing,
        "added_surface_entities": len(new_records),
        "role_counts": role_counts,
        "template_sources": template_sources,
        "new_entity_count": int(gparsed["entity_count"]),
        "changed_decrypted_members": changed,
        "placements": placement_rows,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 road surface detail v5")
    print(f"Source: {report['source_fpm']}")
    print(f"Donor:  {report['donor_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"Removed previous v5 surface detail: {report['removed_existing_surface_detail']}")
    print(f"Added surface/detail entities: {report['added_surface_entities']}")
    print("Detail counts:")
    for role, count in sorted(report["role_counts"].items()):
        print(f"  {role:28s} {count}")
    print("[PASS] Every Straight 4X module receives deterministic asphalt wear detail.")
    print("[PASS] Junction approaches receive road-aligned lane arrows and sparse SLOW/ONLY text.")
    print("[PASS] Utility/manhole covers use a controlled cadence instead of random scatter.")
    print("[PASS] v4 center lines, crosswalks, lamps and bollards are preserved.")
    print("[PASS] Main roads remain the uniform full-width road grammar.")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print(f"SHA-256: {report['sha256']}")


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
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM ROAD SURFACE V5 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
