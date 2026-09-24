#!/usr/bin/env python3
"""Author structural road detail with explicit donor-road ownership.

v4 correctly stopped mixing road surface families, but its exemplar harvester used a
radius around each donor road. In a dense street grid, that can capture a crosswalk,
lamp, light marker, or bollard that actually belongs to the neighboring road module.
Replaying that contaminated assembly across District 12 can create duplicate markings
and furniture that appears to float beside the asphalt.

v7 keeps the proven v4 writer and transforms, but tightens donor harvesting:

* every detail role has an explicit set of compatible road kinds;
* each donor detail is owned by exactly one nearest compatible donor road;
* an exemplar may replay only details it owns;
* distance/radius and safe-template checks remain mandatory;
* ties are deterministic by donor record index.

No world-space offsets are invented here. The resulting transform is still copied
from a real CyberCity placement relative to its owning road module.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as legacy
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmError


ROLE_ALLOWED_KINDS: dict[str, frozenset[str]] = {}
for _kind, _roles in v4.PROFILE_ROLES.items():
    for _role in _roles:
        ROLE_ALLOWED_KINDS[_role] = frozenset(
            set(ROLE_ALLOWED_KINDS.get(_role, frozenset())) | {_kind}
        )


def compatible_road_kinds(role: str) -> frozenset[str]:
    """Return the road kinds allowed to own a structural detail role."""
    return ROLE_ALLOWED_KINDS.get(role, frozenset())


def nearest_compatible_road(
    detail: dict[str, Any],
    roads: list[dict[str, Any]],
    role: str,
) -> tuple[dict[str, Any] | None, float]:
    """Return the deterministic nearest road that is allowed to own *role*."""
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
    return road, distance2 ** 0.5


def _owned_assembly_members(
    kind: str,
    road: dict[str, Any],
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> list[v4.AssemblyMember]:
    allowed_roles = set(v4.PROFILE_ROLES.get(kind, ()))
    if not allowed_roles:
        return []

    roads = [
        entity
        for entity in donor_parsed["entities"]
        if legacy.road_kind(entity.get("asset")) in v4.ALLOWED_ROAD_KINDS
    ]
    radius = v4.PROFILE_RADIUS[kind]
    members: list[v4.AssemblyMember] = []

    for detail in donor_parsed["entities"]:
        role = v4.detail_role(detail)
        if role not in allowed_roles:
            continue

        owner, owner_distance = nearest_compatible_road(detail, roads, role)
        if owner is None:
            continue
        if int(owner["record_index"]) != int(road["record_index"]):
            continue
        if owner_distance > radius:
            continue

        dynamic = bool(fabric.ASSETS[role].get("dynamic"))
        safe, _reason = fabric.safe_template_entity(detail, dynamic)
        if not safe:
            continue

        start = int(detail["record_start_offset"])
        end = int(detail["record_end_offset"])
        local_x, y_offset, local_z, relative_yaw = v4._local_offset(road, detail)
        members.append(
            v4.AssemblyMember(
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
        key=lambda member: (
            member.role,
            round(member.local_x, 3),
            round(member.local_z, 3),
            member.donor_record_index,
        )
    )
    return members


def choose_owned_assemblies(
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> dict[str, v4.RoadAssembly]:
    """Choose one uncontaminated donor assembly for each structural road kind."""
    assemblies: dict[str, v4.RoadAssembly] = {}
    for kind in v4.PROFILE_ROLES:
        candidates: list[
            tuple[tuple[int, int, int, int], dict[str, Any], list[v4.AssemblyMember]]
        ] = []
        for road in donor_parsed["entities"]:
            if legacy.road_kind(road.get("asset")) != kind:
                continue
            members = _owned_assembly_members(kind, road, donor_parsed, donor_ele)
            score = v4.assembly_score(kind, members)
            ranked = (score[0], score[1], score[2], -int(road["record_index"]))
            candidates.append((ranked, road, members))

        if not candidates:
            if v4.REQUIRED_PROFILE_ROLES.get(kind):
                raise FpmError(
                    f"CyberCity has no donor road exemplar for required profile '{kind}'."
                )
            continue

        _ranked, road, members = max(candidates, key=lambda row: row[0])
        roles = {member.role for member in members}
        missing = v4.REQUIRED_PROFILE_ROLES.get(kind, frozenset()) - roles
        if missing:
            raise FpmError(
                f"CyberCity '{kind}' exemplar could not supply owned required detail role(s): "
                + ", ".join(sorted(missing))
            )

        assemblies[kind] = v4.RoadAssembly(
            kind=kind,
            donor_road_record_index=int(road["record_index"]),
            donor_road_asset=road["asset"],
            members=tuple(members),
        )
    return assemblies


def compile_road_details(
    source_path: Path,
    output_path: Path,
    donor_path: Path,
    max_additions: int,
) -> dict[str, Any]:
    """Run the proven v4 writer with v7's strict ownership harvester."""
    original = v4.choose_assemblies
    v4.choose_assemblies = choose_owned_assemblies
    try:
        report = v4.compile_road_details(
            source_path,
            output_path,
            donor_path,
            max_additions,
        )
    finally:
        v4.choose_assemblies = original

    report["detail_policy"] = "nearest-compatible-road-owner"
    report["cross_module_profile_capture"] = "rejected"
    return report


def print_report(report: dict[str, Any]) -> None:
    v4.print_report(report)
    print("[PASS] Every structural detail belongs to its nearest compatible donor road.")
    print("[PASS] Neighboring road modules cannot contaminate a replayed detail profile.")


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
            import json

            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM ROAD DETAIL V7 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
