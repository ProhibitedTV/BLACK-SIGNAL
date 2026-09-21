#!/usr/bin/env python3
"""Decorate District 12's uniform road grid from one coherent CyberCity profile.

The road surface compiler (v3) intentionally uses only the full-width road grammar:
4-way, T, curve and Straight 4X. This pass keeps that contract and adds road detail
without returning to guessed curb offsets.

For each supported road kind, the tool chooses ONE donor exemplar from CyberCity and
captures only allow-listed road details around it. Those relative transforms are then
reused for every matching target module. We never mix 2X/1X/quarter road surfaces into
the main grid and we never invent furniture offsets.

Current production profile:
- Straight 4X: double center line + street lamps + their real light markers.
- Four-way: crosswalk decals + blocker/bollard posts.
- T intersections: crosswalk decals + blocker/bollard posts when the exemplar has them.

Sidewalk/curb geometry is deliberately not synthesized here. That needs its own
calibrated exemplar profile instead of guessed lateral offsets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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


ALLOWED_ROAD_KINDS = ("fourway", "tee", "curve", "straight4")
PROFILE_ROLES: dict[str, tuple[str, ...]] = {
    "straight4": ("road_center_yellow", "street_lamp", "street_dynamic_light"),
    "fourway": ("crosswalk", "bollard_stop"),
    "tee": ("crosswalk", "bollard_stop"),
}
REQUIRED_PROFILE_ROLES: dict[str, frozenset[str]] = {
    "straight4": frozenset(("road_center_yellow",)),
    "fourway": frozenset(("crosswalk",)),
    "tee": frozenset(),
}
PROFILE_RADIUS: dict[str, float] = {
    "straight4": 520.0,
    "fourway": 700.0,
    "tee": 700.0,
}
DETAIL_ROLE_BY_BASENAME = {
    fabric.basename(fabric.ASSETS[role]["basename"]): role
    for roles in PROFILE_ROLES.values()
    for role in roles
}
PROFILE_DETAIL_BASENAMES = frozenset(DETAIL_ROLE_BY_BASENAME)


@dataclass(frozen=True)
class AssemblyMember:
    role: str
    asset_path: str
    parsed: dict[str, Any]
    raw_record: bytes
    local_x: float
    y_offset: float
    local_z: float
    relative_yaw: float
    donor_record_index: int


@dataclass(frozen=True)
class RoadAssembly:
    kind: str
    donor_road_record_index: int
    donor_road_asset: str
    members: tuple[AssemblyMember, ...]


def detail_role(entity: dict[str, Any]) -> str | None:
    return DETAIL_ROLE_BY_BASENAME.get(fabric.basename(entity.get("asset")))


def validate_uniform_grammar(parsed: dict[str, Any]) -> dict[str, int]:
    counts = {kind: 0 for kind in ALLOWED_ROAD_KINDS}
    disallowed: list[str] = []
    for entity in parsed["entities"]:
        kind = legacy.road_kind(entity.get("asset"))
        if kind is None:
            continue
        if kind not in counts:
            disallowed.append(fabric.basename(entity.get("asset")))
            continue
        counts[kind] += 1

    if disallowed:
        names = ", ".join(sorted(set(disallowed)))
        raise FpmError(
            "Target road network violates the uniform main-road grammar. "
            "Rebuild with fpm_author_road_network_v3.py before adding detail. "
            f"Disallowed road modules: {names}"
        )
    if sum(counts.values()) == 0:
        raise FpmError("Target contains no recognized road modules.")
    if counts["straight4"] == 0:
        raise FpmError("Target contains no Straight 4X main-road modules.")
    return counts


def _local_offset(road: dict[str, Any], detail: dict[str, Any]) -> tuple[float, float, float, float]:
    rp = road["position"]
    dp = detail["position"]
    road_yaw = float(road["rotation_euler"]["y"])
    world_dx = float(dp["x"]) - float(rp["x"])
    world_dz = float(dp["z"]) - float(rp["z"])
    local_x, local_z = fabric.rotate_local(world_dx, world_dz, -road_yaw)
    y_offset = float(dp["y"]) - float(rp["y"])
    relative_yaw = (
        float(detail["rotation_euler"]["y"]) - road_yaw + 180.0
    ) % 360.0 - 180.0
    return local_x, y_offset, local_z, relative_yaw


def _assembly_members(
    kind: str,
    road: dict[str, Any],
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> list[AssemblyMember]:
    allowed_roles = set(PROFILE_ROLES.get(kind, ()))
    if not allowed_roles:
        return []
    radius2 = PROFILE_RADIUS[kind] ** 2
    rp = road["position"]
    members: list[AssemblyMember] = []

    for detail in donor_parsed["entities"]:
        role = detail_role(detail)
        if role not in allowed_roles:
            continue
        dp = detail["position"]
        dx = float(dp["x"]) - float(rp["x"])
        dz = float(dp["z"]) - float(rp["z"])
        if dx * dx + dz * dz > radius2:
            continue

        dynamic = bool(fabric.ASSETS[role].get("dynamic"))
        safe, _reason = fabric.safe_template_entity(detail, dynamic)
        if not safe:
            continue

        start = int(detail["record_start_offset"])
        end = int(detail["record_end_offset"])
        local_x, y_offset, local_z, relative_yaw = _local_offset(road, detail)
        members.append(
            AssemblyMember(
                role=role,
                asset_path=detail["asset"],
                parsed=detail,
                raw_record=donor_ele[start:end],
                local_x=local_x,
                y_offset=y_offset,
                local_z=local_z,
                relative_yaw=relative_yaw,
                donor_record_index=int(detail["record_index"]),
            )
        )

    members.sort(
        key=lambda m: (
            m.role,
            round(m.local_x, 3),
            round(m.local_z, 3),
            m.donor_record_index,
        )
    )
    return members


def assembly_score(kind: str, members: list[AssemblyMember]) -> tuple[int, int, int]:
    roles = {m.role for m in members}
    required = REQUIRED_PROFILE_ROLES.get(kind, frozenset())
    required_hits = len(required.intersection(roles))
    return (required_hits, len(roles), len(members))


def choose_assemblies(
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> dict[str, RoadAssembly]:
    assemblies: dict[str, RoadAssembly] = {}
    for kind in PROFILE_ROLES:
        candidates: list[tuple[tuple[int, int, int, int], dict[str, Any], list[AssemblyMember]]] = []
        for road in donor_parsed["entities"]:
            if legacy.road_kind(road.get("asset")) != kind:
                continue
            members = _assembly_members(kind, road, donor_parsed, donor_ele)
            score = assembly_score(kind, members)
            # Final component prefers the earliest authored exemplar on ties.
            ranked = (score[0], score[1], score[2], -int(road["record_index"]))
            candidates.append((ranked, road, members))

        if not candidates:
            if REQUIRED_PROFILE_ROLES.get(kind):
                raise FpmError(f"CyberCity has no donor road exemplar for required profile '{kind}'.")
            continue

        _ranked, road, members = max(candidates, key=lambda row: row[0])
        roles = {m.role for m in members}
        missing = REQUIRED_PROFILE_ROLES.get(kind, frozenset()) - roles
        if missing:
            raise FpmError(
                f"CyberCity '{kind}' exemplar could not supply required detail role(s): "
                + ", ".join(sorted(missing))
            )
        assemblies[kind] = RoadAssembly(
            kind=kind,
            donor_road_record_index=int(road["record_index"]),
            donor_road_asset=road["asset"],
            members=tuple(members),
        )
    return assemblies


def placement_for_member(
    member: AssemblyMember,
    target_road: dict[str, Any],
) -> fabric.Placement:
    rp = target_road["position"]
    yaw = float(target_road["rotation_euler"]["y"])
    ox, oz = fabric.rotate_local(member.local_x, member.local_z, yaw)
    return fabric.Placement(
        role=member.role,
        x=float(rp["x"]) + ox,
        y=float(rp["y"]) + member.y_offset,
        z=float(rp["z"]) + oz,
        ry=(yaw + member.relative_yaw) % 360.0,
        note=(
            f"{member.role} from CyberCity road profile "
            f"#{member.donor_record_index} -> target road #{target_road['record_index']}"
        ),
    )


def _strip_old_profile_detail(entity: dict[str, Any]) -> bool:
    return fabric.basename(entity.get("asset")) in PROFILE_DETAIL_BASENAMES


def compile_road_details(
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
            raise FpmError("Road-detail writer requires CRLF map.ent encoding.")
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}
        road_counts = validate_uniform_grammar(parsed)

        with FpmArchive(donor_path) as donor:
            dent = parse_map_ent(donor.read("map.ent"))
            donor_ele = donor.read("map.ele")
            donor_parsed = parse_map_ele(donor_ele, dent["entries"])
            verify_raw_ele_roundtrip(donor_ele, donor_parsed)
            if donor_parsed["version"] != parsed["version"]:
                raise FpmError(
                    "CyberCity donor ELE version does not match the uniform-road target "
                    f"({donor_parsed['version']} != {parsed['version']})."
                )
            assemblies = choose_assemblies(donor_path, donor_parsed, donor_ele)

        bank_paths = [entry["path"] for entry in ent["entries"]]
        bank_lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
        role_asset_bank: dict[tuple[str, str], int] = {}
        for assembly in assemblies.values():
            for member in assembly.members:
                key = fabric.norm(member.asset_path)
                if key not in bank_lookup:
                    bank_paths.append(member.asset_path)
                    bank_lookup[key] = len(bank_paths)
                role_asset_bank[(member.role, key)] = bank_lookup[key]

        kept_records: list[bytes] = []
        removed_existing_detail = 0
        for entity in parsed["entities"]:
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            if _strip_old_profile_detail(entity):
                removed_existing_detail += 1
                continue
            kept_records.append(ele_data[start:end])

        target_roads = sorted(
            [
                entity
                for entity in parsed["entities"]
                if legacy.road_kind(entity.get("asset")) in PROFILE_ROLES
            ],
            key=lambda e: (
                legacy.road_kind(e.get("asset")) or "",
                round(float(e["position"]["x"]), 3),
                round(float(e["position"]["z"]), 3),
                int(e["record_index"]),
            ),
        )

        new_records: list[bytes] = []
        placements: list[dict[str, Any]] = []
        seen: set[tuple[str, int, int, int]] = set()

        for road in target_roads:
            kind = legacy.road_kind(road.get("asset"))
            assembly = assemblies.get(kind or "")
            if assembly is None:
                continue
            for member in assembly.members:
                placement = placement_for_member(member, road)
                dedupe_key = (
                    member.role,
                    int(round(placement.x * 10.0)),
                    int(round(placement.z * 10.0)),
                    int(round((placement.ry or 0.0) * 10.0)),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                template = fabric.Template(
                    role=member.role,
                    asset_path=member.asset_path,
                    parsed=member.parsed,
                    raw_record=member.raw_record,
                    source_fpm=str(donor_path),
                    source_kind="cybercity-road-profile",
                )
                bank_index = role_asset_bank[(member.role, fabric.norm(member.asset_path))]
                new_records.append(_patched_patch_record(template, bank_index, placement))
                placements.append(
                    {
                        "road_kind": kind,
                        "role": member.role,
                        "asset": fabric.basename(member.asset_path),
                        "x": placement.x,
                        "y": placement.y,
                        "z": placement.z,
                        "ry": placement.ry,
                        "target_road_record_index": int(road["record_index"]),
                        "donor_detail_record_index": member.donor_record_index,
                    }
                )

        if len(new_records) > max_additions:
            raise FpmError(
                f"Road detail plan adds {len(new_records)} entities, above "
                f"--max-additions={max_additions}."
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
        raise FpmError("Generated road-detail FPM failed exact ELE verification.")

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
            "Road-detail compiler changed unrelated FPM members: "
            + ", ".join(sorted(set(changed) - allowed_changed))
        )

    assembly_report = {}
    for kind, assembly in assemblies.items():
        role_counts: dict[str, int] = {}
        for member in assembly.members:
            role_counts[member.role] = role_counts.get(member.role, 0) + 1
        assembly_report[kind] = {
            "donor_road_record_index": assembly.donor_road_record_index,
            "donor_road_asset": fabric.basename(assembly.donor_road_asset),
            "member_count": len(assembly.members),
            "role_counts": role_counts,
        }

    return {
        "source_fpm": str(source_path),
        "donor_fpm": str(donor_path),
        "output_fpm": str(output_path),
        "road_counts": road_counts,
        "profile_assemblies": assembly_report,
        "removed_existing_profile_detail": removed_existing_detail,
        "added_detail_entities": len(new_records),
        "new_entity_count": int(gparsed["entity_count"]),
        "changed_decrypted_members": changed,
        "placements": placements,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 coherent road detail v4")
    print(f"Source: {report['source_fpm']}")
    print(f"Donor:  {report['donor_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print("Uniform road counts:")
    for kind in ALLOWED_ROAD_KINDS:
        print(f"  {kind:10s} {report['road_counts'][kind]}")
    print("CyberCity detail profiles:")
    for kind, row in report["profile_assemblies"].items():
        roles = ", ".join(
            f"{role}={count}" for role, count in sorted(row["role_counts"].items())
        )
        print(
            f"  {kind:10s} donor road #{row['donor_road_record_index']} "
            f"({row['donor_road_asset']}): {roles or 'no optional members'}"
        )
    print(f"Removed existing profile detail: {report['removed_existing_profile_detail']}")
    print(f"Added detail entities: {report['added_detail_entities']}")
    print("[PASS] Main streets contain no 2X/1X/quarter road substitutions.")
    print("[PASS] Detail transforms come from one CyberCity exemplar per road kind.")
    print("[PASS] No guessed curb/sidewalk offsets are synthesized.")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument("--donor-fpm", type=Path, required=True)
    parser.add_argument("--max-additions", type=int, default=2500)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compile_road_details(
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
        print(f"FPM ROAD DETAIL V4 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
