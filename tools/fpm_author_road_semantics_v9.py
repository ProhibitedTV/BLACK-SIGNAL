#!/usr/bin/env python3
"""Re-author District 12 road markings and lighting from road semantics.

V7 proved the road graph but still replayed donor-local decoration in ways that could
look wrong in the generated grid. V9 deliberately strips those inherited road-detail
roles and rebuilds only the semantics we can prove from the target road graph:

* one centered double-yellow treatment per Straight 4X module;
* four deterministic crosswalks on 4-way junctions only;
* straight-ahead lane arrows only on aligned Straight 4X approaches to 4-way junctions;
* deterministic street lamps with paired real GameGuru MAX light markers;
* no turn arrows, SLOW/ONLY text, donor wear decals, or T-junction markings until
  the generator has enough lane/exit semantics to place them correctly.

The road meshes themselves are never moved or replaced by this pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as legacy
import fpm_author_road_surface_v5 as v5
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

SEMANTIC_POLICY = "target-road-graph-semantic-dressing-v9"
ROAD_SURFACE_Y = 2.0
LAMP_EDGE_X = 325.0
LAMP_LIGHT_Y = 280.0
CROSSWALK_EDGE = 260.0
ARROW_LANE_X = 94.0
ARROW_LOCAL_Z = 120.0
APPROACH_SEARCH_RADIUS = 650.0
APPROACH_AXIS_TOLERANCE = 100.0

FABRIC_ROLES = (
    "road_center_yellow",
    "crosswalk",
    "street_lamp",
    "street_dynamic_light",
)
ARROW_ROLE = "road_arrow_straight"
STRIP_BASENAMES = frozenset(set(v4.PROFILE_DETAIL_BASENAMES) | set(v5.OWNED_BASENAMES))


def _local_offset(road: dict[str, Any], target: dict[str, Any]) -> tuple[float, float]:
    rp = road["position"]
    tp = target["position"]
    dx = float(tp["x"]) - float(rp["x"])
    dz = float(tp["z"]) - float(rp["z"])
    yaw = float(road["rotation_euler"]["y"])
    return fabric.rotate_local(dx, dz, -yaw)


def _nearest_fourway(
    road: dict[str, Any], junctions: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float]:
    ranked: list[tuple[float, int, float, dict[str, Any]]] = []
    for junction in junctions:
        local_x, local_z = _local_offset(road, junction)
        distance = math.hypot(local_x, local_z)
        if distance > APPROACH_SEARCH_RADIUS:
            continue
        # A true approach must lie on the longitudinal road axis. This prevents a
        # nearby but perpendicular/diagonal road from receiving an arrow for the
        # wrong intersection.
        if abs(local_x) > APPROACH_AXIS_TOLERANCE:
            continue
        ranked.append((distance, int(junction["record_index"]), local_z, junction))
    if not ranked:
        return None, 0.0
    _distance, _idx, local_z, junction = min(ranked, key=lambda row: (row[0], row[1]))
    return junction, local_z


def _placement(
    role: str,
    road: dict[str, Any],
    local_x: float,
    local_z: float,
    y_offset: float,
    yaw_offset: float,
    note: str,
) -> fabric.Placement:
    p = road["position"]
    yaw = float(road["rotation_euler"]["y"])
    ox, oz = fabric.rotate_local(local_x, local_z, yaw)
    return fabric.Placement(
        role=role,
        x=float(p["x"]) + ox,
        y=float(p["y"]) + y_offset,
        z=float(p["z"]) + oz,
        ry=(yaw + yaw_offset) % 360.0,
        note=note,
    )


def plan_semantic_dressing(parsed: dict[str, Any]) -> list[fabric.Placement]:
    roads = [
        entity
        for entity in parsed["entities"]
        if legacy.road_kind(entity.get("asset")) in v4.ALLOWED_ROAD_KINDS
    ]
    straights = sorted(
        [entity for entity in roads if legacy.road_kind(entity.get("asset")) == "straight4"],
        key=lambda e: (
            round(float(e["position"]["x"]), 3),
            round(float(e["position"]["z"]), 3),
            int(e["record_index"]),
        ),
    )
    fourways = [entity for entity in roads if legacy.road_kind(entity.get("asset")) == "fourway"]
    out: list[fabric.Placement] = []

    for ordinal, road in enumerate(straights):
        out.append(
            _placement(
                "road_center_yellow",
                road,
                0.0,
                0.0,
                ROAD_SURFACE_Y,
                90.0,
                f"v9 centered corridor marking for Straight 4X #{road['record_index']}",
            )
        )

        # One lamp on every other road module, with the curb side alternating by
        # lamp index. Using sorted-module ordinal rather than coordinate parity is
        # deliberate: the 1800/500/900/1300 grid cadence otherwise made every
        # candidate share the same parity and could accidentally produce no lamps.
        if ordinal % 2 == 0:
            lamp_ordinal = ordinal // 2
            side = -1.0 if lamp_ordinal % 2 else 1.0
            lamp = _placement(
                "street_lamp",
                road,
                side * LAMP_EDGE_X,
                0.0,
                0.0,
                180.0 if side < 0.0 else 0.0,
                f"v9 curb lamp beside Straight 4X #{road['record_index']}",
            )
            out.append(lamp)
            out.append(
                fabric.Placement(
                    role="street_dynamic_light",
                    x=lamp.x,
                    y=lamp.y + LAMP_LIGHT_Y,
                    z=lamp.z,
                    ry=None,
                    note=f"v9 light marker paired with lamp beside Straight 4X #{road['record_index']}",
                )
            )

        junction, local_z = _nearest_fourway(road, fourways)
        if junction is not None and abs(local_z) > 120.0:
            # local_z points from this road module toward the junction. The lane
            # offset flips with travel direction so the arrow remains on the
            # right-hand approach lane instead of crossing the center line.
            direction = 1.0 if local_z > 0.0 else -1.0
            out.append(
                _placement(
                    ARROW_ROLE,
                    road,
                    ARROW_LANE_X * direction,
                    ARROW_LOCAL_Z * direction,
                    ROAD_SURFACE_Y + 0.15,
                    90.0 + (0.0 if direction > 0.0 else 180.0),
                    f"v9 straight-ahead approach arrow to 4-way #{junction['record_index']}",
                )
            )

    for junction in sorted(fourways, key=lambda e: int(e["record_index"])):
        # Exactly four crosswalks, one at each edge of the 4-way module. T junctions
        # intentionally receive none until the missing branch can be proven reliably.
        for yaw_offset, lx, lz in (
            (0.0, 0.0, CROSSWALK_EDGE),
            (180.0, 0.0, -CROSSWALK_EDGE),
            (90.0, CROSSWALK_EDGE, 0.0),
            (270.0, -CROSSWALK_EDGE, 0.0),
        ):
            out.append(
                _placement(
                    "crosswalk",
                    junction,
                    lx,
                    lz,
                    ROAD_SURFACE_Y,
                    yaw_offset,
                    f"v9 four-way crosswalk at junction #{junction['record_index']}",
                )
            )

    return out


def _fabric_template(
    role: str,
    source_path: Path,
    parsed: dict[str, Any],
    ele_data: bytes,
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> fabric.Template:
    template = fabric.source_template_from_parsed(role, parsed, ele_data, source_path, "target-exact")
    if template is None:
        template = fabric.source_template_from_parsed(role, donor_parsed, donor_ele, donor_path, "cybercity-exact")
    if template is None:
        raise FpmError(f"V9 requires an exact same-version template for {role}.")
    return template


def _arrow_template(
    source_path: Path,
    parsed: dict[str, Any],
    ele_data: bytes,
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> fabric.Template:
    template = v5._exact_template(ARROW_ROLE, parsed, ele_data, source_path, "target-exact")
    if template is None:
        template = v5._exact_template(ARROW_ROLE, donor_parsed, donor_ele, donor_path, "cybercity-exact")
    if template is None:
        template = v5._carrier_template(
            ARROW_ROLE,
            source_path,
            parsed,
            ele_data,
            donor_path,
            donor_parsed,
            donor_ele,
        )
    return template


def compile_semantic_dressing(
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
            raise FpmError("V9 semantic writer requires CRLF map.ent encoding.")
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}
        road_counts = v4.validate_uniform_grammar(parsed)

        with FpmArchive(donor_path) as donor:
            dent = parse_map_ent(donor.read("map.ent"))
            donor_ele = donor.read("map.ele")
            donor_parsed = parse_map_ele(donor_ele, dent["entries"])
            verify_raw_ele_roundtrip(donor_ele, donor_parsed)
            if int(donor_parsed["version"]) != int(parsed["version"]):
                raise FpmError("CyberCity donor ELE version does not match target.")

            templates = {
                role: _fabric_template(
                    role, source_path, parsed, ele_data, donor_path, donor_parsed, donor_ele
                )
                for role in FABRIC_ROLES
            }
            templates[ARROW_ROLE] = _arrow_template(
                source_path, parsed, ele_data, donor_path, donor_parsed, donor_ele
            )

        plan = plan_semantic_dressing(parsed)
        if len(plan) > max_additions:
            raise FpmError(
                f"V9 semantic plan adds {len(plan)} entities, above --max-additions={max_additions}."
            )

        bank_paths = [entry["path"] for entry in ent["entries"]]
        bank_lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
        role_bank: dict[str, int] = {}
        for role, template in templates.items():
            asset_path = template.asset_path
            key = fabric.norm(asset_path)
            if key not in bank_lookup:
                bank_paths.append(asset_path)
                bank_lookup[key] = len(bank_paths)
            role_bank[role] = bank_lookup[key]

        kept_records: list[bytes] = []
        removed_roles: dict[str, int] = {}
        for entity in parsed["entities"]:
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            base_name = fabric.basename(entity.get("asset"))
            if base_name in STRIP_BASENAMES:
                removed_roles[base_name] = removed_roles.get(base_name, 0) + 1
                continue
            kept_records.append(ele_data[start:end])

        new_records: list[bytes] = []
        placements: list[dict[str, Any]] = []
        role_counts: dict[str, int] = {}
        seen: set[tuple[str, int, int, int]] = set()
        for item in plan:
            ry_key = -1 if item.ry is None else int(round(float(item.ry) * 10.0))
            key = (
                item.role,
                int(round(item.x * 10.0)),
                int(round(item.z * 10.0)),
                ry_key,
            )
            if key in seen:
                continue
            seen.add(key)
            template = templates[item.role]
            new_records.append(_patched_patch_record(template, role_bank[item.role], item))
            role_counts[item.role] = role_counts.get(item.role, 0) + 1
            placements.append(
                {
                    "role": item.role,
                    "x": item.x,
                    "y": item.y,
                    "z": item.z,
                    "ry": item.ry,
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
        generated_manifest = {row["name"]: row["sha256"] for row in generated.member_manifest()}

    if (
        int(gparsed["entity_count"]) != new_count
        or not gparsed["fully_traversed"]
        or int(gparsed["trailing_bytes"]) != 0
    ):
        raise FpmError("Generated V9 semantic FPM failed exact ELE verification.")

    changed = sorted(
        name for name, sha in generated_manifest.items() if source_manifest.get(name) != sha
    )
    allowed = {
        name
        for name in generated_manifest
        if name.replace("\\", "/").lower() in {"map.ent", "map.ele"}
    }
    if set(changed) - allowed:
        raise FpmError(
            "V9 semantic pass changed unrelated FPM members: "
            + ", ".join(sorted(set(changed) - allowed))
        )

    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "semantic_policy": SEMANTIC_POLICY,
        "road_counts": road_counts,
        "removed_existing_detail": sum(removed_roles.values()),
        "removed_by_basename": removed_roles,
        "added_entities": len(new_records),
        "role_counts": role_counts,
        "placements": placements,
        "changed_decrypted_members": changed,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 semantic road dressing v9")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"Removed inherited road-detail entities: {report['removed_existing_detail']}")
    print(f"Added semantic entities: {report['added_entities']}")
    for role, count in sorted(report["role_counts"].items()):
        print(f"  {role:24s} {count}")
    print("[PASS] Center lines are target-road-centered, not donor-offset replays.")
    print("[PASS] Only straight-ahead arrows are authored, and only on aligned 4-way approaches.")
    print("[PASS] T-junction arrows/text are omitted rather than guessed.")
    print("[PASS] Street lamps are paired with exact GameGuru MAX dynamic light markers.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument("--donor-fpm", type=Path, required=True)
    parser.add_argument("--max-additions", type=int, default=2200)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compile_semantic_dressing(
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
    except (FpmError, OSError, ValueError, KeyError, TypeError, struct.error) as exc:
        print(f"FPM ROAD SEMANTICS V9 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
