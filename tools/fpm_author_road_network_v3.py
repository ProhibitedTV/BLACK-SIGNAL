#!/usr/bin/env python3
"""Author a clean, uniform District 12 road foundation.

This pass deliberately stops treating every installed road mesh as interchangeable.
The previous compiler mixed 4X, 2X, 1X and quarter pieces inside ordinary traffic
lanes before their actual mesh footprints had been calibrated. That produced the
visible width/length discontinuities and exposed terrain gaps.

The playable network now uses only the donor-proven full-width road grammar:
- CS_Street_4_Way_2
- CS_Street_T-Intersect_3
- CS_Street_Curve_1
- CS_Street_Straight_4X

Every block span is identical: junction -> 4X -> 4X -> 4X -> junction. Smaller
straight pieces remain available for a later calibrated service-road/driveway pass,
but are never substituted randomly into main streets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_network_v2 as legacy
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

PLAYABLE_KINDS = ("fourway", "tee", "curve", "straight4")
NODE_SPACING = 1800.0
STRAIGHT_CENTERS = (500.0, 900.0, 1300.0)


def plan_uniform_network(grid_size: int) -> list[legacy.PlannedRoad]:
    if grid_size < 5 or grid_size % 2 == 0:
        raise ValueError("grid_size must be an odd integer >= 5")
    half = grid_size // 2
    coords = [(i - half) * NODE_SPACING for i in range(grid_size)]
    plan: list[legacy.PlannedRoad] = []

    for iz, z in enumerate(coords):
        for ix, x in enumerate(coords):
            kind, mask = legacy.node_kind_mask(ix, iz, grid_size)
            plan.append(legacy.PlannedRoad(kind, x, z, mask, f"node-{ix}-{iz}"))

    # Main streets are intentionally boring at this stage: one road width,
    # one module length, one cadence. Urban variety belongs in the blocks, not
    # in random asphalt dimensions.
    for iz, z in enumerate(coords):
        for ix in range(grid_size - 1):
            start = coords[ix]
            for offset in STRAIGHT_CENTERS:
                plan.append(
                    legacy.PlannedRoad(
                        "straight4",
                        start + offset,
                        z,
                        frozenset(("E", "W")),
                        f"avenue-h-{ix}-{iz}",
                    )
                )

    for ix, x in enumerate(coords):
        for iz in range(grid_size - 1):
            start = coords[iz]
            for offset in STRAIGHT_CENTERS:
                plan.append(
                    legacy.PlannedRoad(
                        "straight4",
                        x,
                        start + offset,
                        frozenset(("N", "S")),
                        f"avenue-v-{ix}-{iz}",
                    )
                )
    return plan


def strip_for_clean_road_foundation(entity: dict[str, Any]) -> bool:
    p = legacy.norm_asset(entity.get("asset"))
    # Start from roads, not from the sparse demo composition. Remove all placed
    # Cyber City kit geometry/dressing so old buildings, sidewalks, lamps and
    # experimental street passes cannot overlap the new grid.
    if p.startswith("cyberpunk streets booster pack\\"):
        return True
    # The stock demo's placed jungle trees are also urban-block obstacles.
    if p.startswith("jungle collection\\trees\\"):
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

        existing_roads = [
            e for e in parsed["entities"] if legacy.road_kind(e.get("asset")) is not None
        ]
        templates, _generic_imports = legacy.find_templates(source_path, parsed, ent, ele_data)
        missing = [kind for kind in PLAYABLE_KINDS if kind not in templates]
        if missing:
            raise FpmError("Missing donor-proven road templates: " + ", ".join(missing))

        ox, oy, oz = legacy.choose_origin(existing_roads)
        plan = plan_uniform_network(grid_size)
        if len(plan) > max_additions:
            raise FpmError(
                f"Road plan adds {len(plan)} road records, above --max-additions={max_additions}."
            )

        bank_paths = [entry["path"] for entry in ent["entries"]]
        lookup = {legacy.norm_asset(path): i + 1 for i, path in enumerate(bank_paths)}
        bank_index: dict[str, int] = {}
        for kind in PLAYABLE_KINDS:
            template = templates[kind]
            key = legacy.norm_asset(template.asset_path)
            if key not in lookup:
                bank_paths.append(template.asset_path)
                lookup[key] = len(bank_paths)
            bank_index[kind] = lookup[key]

        kept_records: list[bytes] = []
        removed = 0
        for entity in parsed["entities"]:
            start = int(entity["record_start_offset"])
            end = int(entity["record_end_offset"])
            if strip_for_clean_road_foundation(entity):
                removed += 1
                continue
            kept_records.append(ele_data[start:end])

        new_records: list[bytes] = []
        placements: list[dict[str, Any]] = []
        used_counts = {kind: 0 for kind in PLAYABLE_KINDS}
        for item in plan:
            template = templates[item.kind]
            yaw = legacy.yaw_for_mask(template, item.mask)
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
            new_records.append(
                _patched_patch_record(carrier, bank_index[item.kind], placement)
            )
            used_counts[item.kind] += 1
            placements.append(
                {
                    "kind": item.kind,
                    "asset": legacy.ROAD_SPECS[item.kind]["basename"],
                    "x": placement.x,
                    "y": placement.y,
                    "z": placement.z,
                    "yaw": yaw,
                    "connections": sorted(item.mask),
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
        raise FpmError("Generated uniform-road FPM failed exact ELE verification.")

    changed = sorted(
        name
        for name, sha in generated_manifest.items()
        if source_manifest.get(name) != sha
    )
    allowed = {
        name
        for name in generated_manifest
        if name.replace("\\", "/").lower() in {"map.ent", "map.ele"}
    }
    if set(changed) - allowed:
        raise FpmError(
            "Road compiler changed unrelated FPM members: "
            + ", ".join(sorted(set(changed) - allowed))
        )

    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "grid_size": grid_size,
        "node_spacing": NODE_SPACING,
        "span_straight_centers": list(STRAIGHT_CENTERS),
        "origin": {"x": ox, "y": oy, "z": oz},
        "old_entity_count": int(parsed["entity_count"]),
        "removed_demo_entities": removed,
        "new_entity_count": int(gparsed["entity_count"]),
        "added_road_entities": len(new_records),
        "used_counts": used_counts,
        "uncalibrated_modules_excluded_from_main_streets": [
            "CS_Street_Straight_2X.fpe",
            "CS_Street_Straight.fpe",
            "CS_Street_Straight_Quarter.fpe",
        ],
        "changed_decrypted_members": changed,
        "placements": placements,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 uniform road foundation v3")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(
        f"Grid: {report['grid_size']} x {report['grid_size']} nodes @ "
        f"{report['node_spacing']:.0f} units"
    )
    print(f"Removed old demo/city-kit placements: {report['removed_demo_entities']}")
    print(f"Added road entities: {report['added_road_entities']}")
    print("Main-street grammar: junction -> 4X -> 4X -> 4X -> junction")
    print("Road modules used:")
    for kind in PLAYABLE_KINDS:
        print(f"  {kind:10s} {report['used_counts'][kind]}")
    print("[PASS] No random 2X/1X/quarter substitutions in traffic lanes.")
    print("[PASS] Old Cyber City demo geometry was removed before rebuilding roads.")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print("[PASS] Only map.ent/map.ele changed.")
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
        report = compile_network(
            args.source_fpm, args.output_fpm, args.grid_size, args.max_additions
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM ROAD NETWORK V3 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
