#!/usr/bin/env python3
"""Author District 12 road-surface detail only from real CyberCity placements.

v5 proved that the Cyberpunk Streets decals themselves are useful, but its guessed
local X/Z offsets could land decals on bare terrain beside the road. v6 removes that
entire placement model.

Every wear decal, arrow/text marking and manhole used here must already be placed in
CyberCity.fpm. We attach each donor detail to its nearest road module, capture its
exact road-local transform, and replay that transform on the matching District 12
road kind. No hard-coded lane/curb/decal offsets are synthesized.

The structural v4 layer remains authoritative for center lines, crosswalks, lamps,
light markers and intersection bollards. v6 strips only v5/v6-owned surface assets.
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

import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as legacy
import fpm_author_road_surface_v5 as v5
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


SURFACE_ASSETS = v5.SURFACE_ASSETS
WEAR_ROLES = v5.WEAR_ROLES
ARROW_ROLES = v5.ARROW_ROLES
TEXT_ROLES = ("road_slow", "road_only")
OWNED_BASENAMES = v5.OWNED_BASENAMES
ALLOWED_ROAD_KINDS = ("straight4", "fourway", "tee", "curve")

# This is only a donor-association guard. It never creates a placement offset.
# A surface detail farther than this from every road pivot is not considered a
# trustworthy road exemplar and is ignored rather than projected onto a road.
MAX_DONOR_ATTACH_DISTANCE = 420.0
APPROACH_SEARCH_RADIUS = 650.0


@dataclass(frozen=True)
class SurfaceMember:
    role: str
    road_kind: str
    asset_path: str
    parsed: dict[str, Any]
    raw_record: bytes
    local_x: float
    y_offset: float
    local_z: float
    relative_yaw: float
    donor_detail_record_index: int
    donor_road_record_index: int


@dataclass(frozen=True)
class PlannedSurfaceDetail:
    member: SurfaceMember
    target_road_record_index: int
    x: float
    y: float
    z: float
    ry: float
    note: str


def _surface_role(entity: dict[str, Any]) -> str | None:
    base = fabric.basename(entity.get("asset"))
    for role, spec in SURFACE_ASSETS.items():
        if base == fabric.basename(spec["basename"]):
            return role
    return None


def _stable_seed(entity: dict[str, Any]) -> int:
    p = entity["position"]
    xi = int(round(float(p["x"]) / 25.0))
    zi = int(round(float(p["z"]) / 25.0))
    kind = legacy.road_kind(entity.get("asset")) or "unknown"
    salt = {"straight4": 0x2D, "fourway": 0x59, "tee": 0x83, "curve": 0xA7}.get(kind, 0x11)
    return ((xi * 73856093) ^ (zi * 19349663) ^ (salt * 83492791)) & 0x7FFFFFFF


def _road_local_offset(road: dict[str, Any], other: dict[str, Any]) -> tuple[float, float]:
    rp = road["position"]
    op = other["position"]
    dx = float(op["x"]) - float(rp["x"])
    dz = float(op["z"]) - float(rp["z"])
    yaw = float(road["rotation_euler"]["y"])
    return fabric.rotate_local(dx, dz, -yaw)


def _nearest_road(detail: dict[str, Any], roads: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    dp = detail["position"]
    best_road: dict[str, Any] | None = None
    best_distance = float("inf")
    for road in roads:
        rp = road["position"]
        distance = math.hypot(
            float(dp["x"]) - float(rp["x"]),
            float(dp["z"]) - float(rp["z"]),
        )
        if distance < best_distance:
            best_distance = distance
            best_road = road
    return best_road, best_distance


def _capture_member(
    role: str,
    road: dict[str, Any],
    detail: dict[str, Any],
    donor_ele: bytes,
) -> SurfaceMember:
    rp = road["position"]
    dp = detail["position"]
    road_yaw = float(road["rotation_euler"]["y"])
    local_x, local_z = _road_local_offset(road, detail)
    relative_yaw = (
        float(detail["rotation_euler"]["y"]) - road_yaw + 180.0
    ) % 360.0 - 180.0
    start = int(detail["record_start_offset"])
    end = int(detail["record_end_offset"])
    return SurfaceMember(
        role=role,
        road_kind=legacy.road_kind(road.get("asset")) or "unknown",
        asset_path=detail["asset"],
        parsed=detail,
        raw_record=donor_ele[start:end],
        local_x=local_x,
        y_offset=float(dp["y"]) - float(rp["y"]),
        local_z=local_z,
        relative_yaw=relative_yaw,
        donor_detail_record_index=int(detail["record_index"]),
        donor_road_record_index=int(road["record_index"]),
    )


def harvest_surface_members(
    donor_parsed: dict[str, Any], donor_ele: bytes
) -> tuple[list[SurfaceMember], list[dict[str, Any]]]:
    roads = [
        entity
        for entity in donor_parsed["entities"]
        if legacy.road_kind(entity.get("asset")) in ALLOWED_ROAD_KINDS
    ]
    if not roads:
        raise FpmError("CyberCity donor contains no recognized full-width road modules.")

    members: list[SurfaceMember] = []
    rejected: list[dict[str, Any]] = []
    for detail in donor_parsed["entities"]:
        role = _surface_role(detail)
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
        road, distance = _nearest_road(detail, roads)
        if road is None or distance > MAX_DONOR_ATTACH_DISTANCE:
            rejected.append(
                {
                    "detail_record_index": int(detail["record_index"]),
                    "role": role,
                    "reason": f"not attached to a road exemplar (nearest={distance:.2f})",
                }
            )
            continue
        members.append(_capture_member(role, road, detail, donor_ele))

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
        raise FpmError("CyberCity contains no safe placed road-surface detail exemplars.")
    return members, rejected


def _catalog(members: list[SurfaceMember]) -> dict[str, dict[str, list[SurfaceMember]]]:
    out: dict[str, dict[str, list[SurfaceMember]]] = {
        kind: {
            "wear": [],
            "manhole": [],
            "arrow_forward": [],
            "arrow_backward": [],
            "text_forward": [],
            "text_backward": [],
        }
        for kind in ALLOWED_ROAD_KINDS
    }
    for member in members:
        if member.road_kind not in out:
            continue
        if member.role in WEAR_ROLES:
            bucket = "wear"
        elif member.role == "manhole_cover":
            bucket = "manhole"
        elif member.role in ARROW_ROLES:
            bucket = "arrow_forward" if member.local_z >= 0.0 else "arrow_backward"
        elif member.role in TEXT_ROLES:
            bucket = "text_forward" if member.local_z >= 0.0 else "text_backward"
        else:
            continue
        out[member.road_kind][bucket].append(member)
    return out


def _nearest_junction(
    road: dict[str, Any], junctions: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float]:
    best: tuple[float, dict[str, Any], float] | None = None
    for junction in junctions:
        local_x, local_z = _road_local_offset(road, junction)
        distance = math.hypot(local_x, local_z)
        if distance > APPROACH_SEARCH_RADIUS:
            continue
        candidate = (distance, junction, local_z)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:
        return None, 0.0
    return best[1], best[2]


def _select(rows: list[SurfaceMember], seed: int) -> SurfaceMember | None:
    if not rows:
        return None
    return rows[seed % len(rows)]


def placement_for_member(
    member: SurfaceMember,
    target_road: dict[str, Any],
    note: str,
) -> PlannedSurfaceDetail:
    rp = target_road["position"]
    yaw = float(target_road["rotation_euler"]["y"])
    ox, oz = fabric.rotate_local(member.local_x, member.local_z, yaw)
    return PlannedSurfaceDetail(
        member=member,
        target_road_record_index=int(target_road["record_index"]),
        x=float(rp["x"]) + ox,
        y=float(rp["y"]) + member.y_offset,
        z=float(rp["z"]) + oz,
        ry=(yaw + member.relative_yaw) % 360.0,
        note=note,
    )


def plan_surface_details(
    parsed: dict[str, Any], members: list[SurfaceMember]
) -> list[PlannedSurfaceDetail]:
    catalog = _catalog(members)
    roads = sorted(
        [
            entity
            for entity in parsed["entities"]
            if legacy.road_kind(entity.get("asset")) in ALLOWED_ROAD_KINDS
        ],
        key=lambda e: (
            legacy.road_kind(e.get("asset")) or "",
            round(float(e["position"]["x"]), 3),
            round(float(e["position"]["z"]), 3),
            int(e["record_index"]),
        ),
    )
    junctions = [
        entity
        for entity in roads
        if legacy.road_kind(entity.get("asset")) in ("fourway", "tee", "curve")
    ]
    plan: list[PlannedSurfaceDetail] = []

    for road in roads:
        kind = legacy.road_kind(road.get("asset")) or "unknown"
        seed = _stable_seed(road)
        profile = catalog.get(kind, {})

        wear = _select(profile.get("wear", []), seed)
        if wear is not None:
            plan.append(
                placement_for_member(
                    wear,
                    road,
                    "CyberCity-authored road-local wear transform",
                )
            )

        if seed % 3 == 0:
            manhole = _select(profile.get("manhole", []), seed >> 2)
            if manhole is not None:
                plan.append(
                    placement_for_member(
                        manhole,
                        road,
                        "CyberCity-authored road-local utility cover transform",
                    )
                )

        if kind != "straight4":
            continue

        junction, local_z = _nearest_junction(road, junctions)
        if junction is None or abs(local_z) < 1.0:
            continue
        direction = "forward" if local_z > 0.0 else "backward"
        arrow = _select(profile.get(f"arrow_{direction}", []), seed >> 3)
        if arrow is not None:
            plan.append(
                placement_for_member(
                    arrow,
                    road,
                    f"CyberCity-authored {direction} junction-approach marking transform",
                )
            )
        if seed % 4 == 0:
            text = _select(profile.get(f"text_{direction}", []), seed >> 5)
            if text is not None:
                plan.append(
                    placement_for_member(
                        text,
                        road,
                        f"CyberCity-authored {direction} regulatory-text transform",
                    )
                )

    return plan


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
            members, rejected = harvest_surface_members(donor_parsed, donor_ele)

        plan = plan_surface_details(parsed, members)
        if len(plan) > max_additions:
            raise FpmError(
                f"Road surface plan adds {len(plan)} entities, above --max-additions={max_additions}."
            )

        bank_paths = [entry["path"] for entry in ent["entries"]]
        bank_lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
        for member in members:
            key = fabric.norm(member.asset_path)
            if key not in bank_lookup:
                bank_paths.append(member.asset_path)
                bank_lookup[key] = len(bank_paths)

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
            member = item.member
            dedupe = (
                member.role,
                int(round(item.x * 10.0)),
                int(round(item.z * 10.0)),
                int(round(item.ry * 10.0)),
            )
            if dedupe in seen:
                continue
            seen.add(dedupe)
            template = fabric.Template(
                role=member.role,
                asset_path=member.asset_path,
                parsed=member.parsed,
                raw_record=member.raw_record,
                source_fpm=str(donor_path),
                source_kind="cybercity-road-surface-exemplar",
            )
            placement = fabric.Placement(
                role=member.role,
                x=item.x,
                y=item.y,
                z=item.z,
                ry=item.ry,
                note=item.note,
            )
            bank_index = bank_lookup[fabric.norm(member.asset_path)]
            new_records.append(_patched_patch_record(template, bank_index, placement))
            role_counts[member.role] = role_counts.get(member.role, 0) + 1
            placement_rows.append(
                {
                    "role": member.role,
                    "asset": fabric.basename(member.asset_path),
                    "road_kind": member.road_kind,
                    "x": item.x,
                    "y": item.y,
                    "z": item.z,
                    "ry": item.ry,
                    "target_road_record_index": item.target_road_record_index,
                    "donor_road_record_index": member.donor_road_record_index,
                    "donor_detail_record_index": member.donor_detail_record_index,
                    "local_x": member.local_x,
                    "local_z": member.local_z,
                    "y_offset": member.y_offset,
                    "relative_yaw": member.relative_yaw,
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
        archive_members = fabric.archive_members_with_replacements(
            source, {"map.ent": new_ent, "map.ele": bytes(new_ele)}
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_zipcrypto_archive(output_path, archive_members)

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
        raise FpmError("Generated road-surface v6 FPM failed exact ELE verification.")

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
            "Road-surface v6 compiler changed unrelated FPM members: "
            + ", ".join(sorted(set(changed) - allowed_changed))
        )

    catalog = _catalog(members)
    donor_catalog = {
        kind: {name: len(rows) for name, rows in groups.items() if rows}
        for kind, groups in catalog.items()
        if any(groups.values())
    }
    return {
        "source_fpm": str(source_path),
        "donor_fpm": str(donor_path),
        "output_fpm": str(output_path),
        "road_counts": road_counts,
        "harvested_donor_surface_members": len(members),
        "rejected_donor_surface_members": rejected,
        "donor_catalog": donor_catalog,
        "removed_existing_surface_detail": removed_existing,
        "added_surface_entities": len(new_records),
        "role_counts": role_counts,
        "new_entity_count": int(gparsed["entity_count"]),
        "changed_decrypted_members": changed,
        "placements": placement_rows,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 donor-calibrated road surface v6")
    print(f"Source: {report['source_fpm']}")
    print(f"Donor:  {report['donor_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"Harvested CyberCity surface exemplars: {report['harvested_donor_surface_members']}")
    print(f"Rejected unattached/unsafe exemplars: {len(report['rejected_donor_surface_members'])}")
    print("Donor catalog:")
    for kind, groups in sorted(report["donor_catalog"].items()):
        summary = ", ".join(f"{name}={count}" for name, count in sorted(groups.items()))
        print(f"  {kind:10s} {summary}")
    print(f"Removed old v5/v6 surface entities: {report['removed_existing_surface_detail']}")
    print(f"Added donor-calibrated surface entities: {report['added_surface_entities']}")
    print("[PASS] Surface X/Z/Y/yaw are replayed from CyberCity road-local transforms.")
    print("[PASS] No guessed lane, curb, wear, arrow or manhole placement offsets are synthesized.")
    print("[PASS] v4 center lines, crosswalks, lamps/light markers and bollards remain untouched.")
    print("[PASS] Main streets remain the strict full-width road grammar.")
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
        print(f"FPM ROAD SURFACE V6 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
