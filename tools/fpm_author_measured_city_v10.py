#!/usr/bin/env python3
"""Author Astra's measured Hero Block 01 shells onto the validated District 12 road graph.

This pass deliberately reuses the measured calibration plan instead of harvesting nearby
CyberCity pivots as alleged buildings. The target road FPM remains authoritative: roads
are never replaced, and only measured sidewalk infill plus complete building shells are
appended around the most central 4-way junction.

Drop-curb corner pieces are omitted here because the v9.2 semantic pass owns junction
corners. Street lamps are also omitted here because semantic dressing owns lamp cadence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import statistics
import struct
import sys
from pathlib import Path
from typing import Any

import fpm_author_city_mass_v2 as cityv2
import fpm_author_hero_block as hero
import fpm_author_road_network_v2 as roads
import fpm_author_street_fabric as fabric
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

SEMANTIC_OWNER_ASSETS = {"CS_Sidewalk_Corner1_DropCurb"}
OMIT_GROUPS = {"street", "furniture"}


def asset_key(asset_path: str | None) -> str:
    return Path((asset_path or "").replace("\\", "/")).stem


def measured_additions(measured: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the calibrated non-road content that District 12 should inherit."""
    calibration = hero.plan()
    hero.validate(calibration, measured)
    return [
        dict(row)
        for row in calibration
        if row["group"] not in OMIT_GROUPS and row["asset"] not in SEMANTIC_OWNER_ASSETS
    ]


def recognized_target_roads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    return [entity for entity in parsed["entities"] if roads.road_kind(entity.get("asset"))]


def central_fourway(target_roads: list[dict[str, Any]]) -> dict[str, Any]:
    fourways = [r for r in target_roads if roads.road_kind(r.get("asset")) == "fourway"]
    if not fourways:
        raise FpmError("Measured city pass requires at least one 4-way road junction.")
    cx = statistics.median(float(r["position"]["x"]) for r in target_roads)
    cz = statistics.median(float(r["position"]["z"]) for r in target_roads)
    return min(
        fourways,
        key=lambda r: (
            (float(r["position"]["x"]) - cx) ** 2 + (float(r["position"]["z"]) - cz) ** 2,
            int(r["record_index"]),
        ),
    )


def target_road_bounds(target_roads: list[dict[str, Any]], measured: dict[str, Any]):
    bounds = []
    for road in target_roads:
        key = asset_key(road.get("asset"))
        if key not in measured:
            continue
        p = road["position"]
        bounds.append(
            hero.world_bounds(
                {
                    "asset": key,
                    "x": float(p["x"]),
                    "y": float(p["y"]),
                    "z": float(p["z"]),
                    "yaw": float(road["rotation_euler"]["y"]),
                },
                measured,
            )
        )
    if not bounds:
        raise FpmError("No measured road bounds were available for collision validation.")
    return bounds


def intersects(a, b, tolerance: float = 0.01) -> bool:
    ax0, ax1, az0, az1 = a
    bx0, bx1, bz0, bz1 = b
    return min(ax1, bx1) - max(ax0, bx0) > tolerance and min(az1, bz1) - max(az0, bz0) > tolerance


def validate_world_plan(
    rows: list[dict[str, Any]], target_roads: list[dict[str, Any]], measured: dict[str, Any]
) -> None:
    road_boxes = target_road_bounds(target_roads, measured)
    signatures = [(r["asset"], r["x"], r["y"], r["z"], r["yaw"]) for r in rows]
    if len(signatures) != len(set(signatures)):
        raise FpmError("Measured city plan contains duplicate placements.")

    for row in rows:
        if row["group"] == "sidewalk":
            continue
        box = hero.world_bounds(row, measured)
        if any(intersects(box, road_box) for road_box in road_boxes):
            raise FpmError(
                f"Measured building placement intersects validated road geometry: {row['group']} / {row['asset']}"
            )


def donor_templates(
    donor_parsed: dict[str, Any], donor_ele: bytes, required: set[str], donor_path: Path
) -> dict[str, fabric.Template]:
    out: dict[str, fabric.Template] = {}
    for entity in donor_parsed["entities"]:
        key = asset_key(entity.get("asset"))
        if key not in required or key in out:
            continue
        safe, _reason = fabric.safe_template_entity(entity, False)
        if not safe or int(entity.get("profile_scale", 100)) != 100:
            continue
        if any(abs(float(v)) > 0.001 for v in entity.get("scale_xyz", {}).values()):
            continue
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        out[key] = fabric.Template(
            role="measured-city-v10",
            asset_path=str(entity.get("asset") or ""),
            parsed=entity,
            raw_record=donor_ele[start:end],
            source_fpm=str(donor_path),
            source_kind="exact-measured-donor",
        )
    missing = required - set(out)
    if missing:
        raise FpmError("Missing safe measured donor templates: " + ", ".join(sorted(missing)))
    return out


def compile_measured_city(
    source_path: Path,
    output_path: Path,
    donor_path: Path,
    measurements_path: Path,
    max_additions: int,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    donor_path = donor_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source.")
    if output_path.exists():
        raise FpmError(f"Refusing to overwrite existing measured-city output: {output_path}")

    measured = json.loads(measurements_path.read_text(encoding="utf-8"))
    local_rows = measured_additions(measured)
    if len(local_rows) > max_additions:
        raise FpmError(
            f"Measured Hero Block adds {len(local_rows)} entities, above --max-additions={max_additions}."
        )

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        if ent["encoding"] != "crlf":
            raise FpmError("Measured city writer requires CRLF map.ent encoding.")
        source_ele = source.read("map.ele")
        parsed = parse_map_ele(source_ele, ent["entries"])
        verify_raw_ele_roundtrip(source_ele, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}
        target_roads = recognized_target_roads(parsed)
        junction = central_fourway(target_roads)
        center = junction["position"]
        ox, oy, oz = float(center["x"]), float(center["y"]), float(center["z"])

        world_rows = [
            {
                **row,
                "x": ox + float(row["x"]),
                "y": oy + float(row["y"]),
                "z": oz + float(row["z"]),
                "yaw": float(row["yaw"]),
            }
            for row in local_rows
        ]
        validate_world_plan(world_rows, target_roads, measured)

        with FpmArchive(donor_path) as donor:
            donor_ent = parse_map_ent(donor.read("map.ent"))
            donor_ele = donor.read("map.ele")
            donor_parsed = parse_map_ele(donor_ele, donor_ent["entries"])
            verify_raw_ele_roundtrip(donor_ele, donor_parsed)
            if int(donor_parsed["version"]) != int(parsed["version"]):
                raise FpmError(
                    f"CyberCity donor ELE version does not match target ({donor_parsed['version']} != {parsed['version']})."
                )
            required = {row["asset"] for row in world_rows}
            templates = donor_templates(donor_parsed, donor_ele, required, donor_path)

            bank_paths = [entry["path"] for entry in ent["entries"]]
            bank_lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
            new_records: list[bytes] = []
            placement_rows: list[dict[str, Any]] = []
            for row in world_rows:
                template = templates[row["asset"]]
                bank_index = cityv2.ensure_bank_index(
                    bank_paths, bank_lookup, template.asset_path
                )
                new_records.append(
                    cityv2.clone_donor_record(
                        template.raw_record,
                        template.parsed,
                        bank_index,
                        row["x"],
                        row["y"],
                        row["z"],
                        row["yaw"],
                    )
                )
                placement_rows.append({**row, "target_bank_index": bank_index})

        new_ele = bytearray(source_ele)
        struct.pack_into("<i", new_ele, 4, int(parsed["entity_count"]) + len(new_records))
        for record in new_records:
            new_ele += record
        new_ent = fabric.serialize_map_ent(bank_paths)
        members = fabric.archive_members_with_replacements(
            source, {"map.ent": new_ent, "map.ele": bytes(new_ele)}
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        write_zipcrypto_archive(output_path, members)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    with FpmArchive(output_path) as result:
        result_ent = parse_map_ent(result.read("map.ent"))
        result_ele = result.read("map.ele")
        result_parsed = parse_map_ele(result_ele, result_ent["entries"])
        result_manifest = {row["name"]: row["sha256"] for row in result.member_manifest()}

    expected = int(parsed["entity_count"]) + len(new_records)
    if (
        int(result_parsed["entity_count"]) != expected
        or not result_parsed["fully_traversed"]
        or int(result_parsed["trailing_bytes"]) != 0
    ):
        output_path.unlink(missing_ok=True)
        raise FpmError("Measured city output failed exact ELE traversal/count verification.")

    changed = sorted(
        name for name, sha in result_manifest.items() if source_manifest.get(name) != sha
    )
    changed_normalized = {name.replace("\\", "/").lower() for name in changed}
    if changed_normalized - {"map.ent", "map.ele"}:
        output_path.unlink(missing_ok=True)
        raise FpmError("Measured city compiler changed unrelated FPM members: " + ", ".join(changed))

    return {
        "source_fpm": str(source_path),
        "donor_fpm": str(donor_path),
        "output_fpm": str(output_path),
        "measurement_file": str(measurements_path.resolve()),
        "hero_junction_record": int(junction["record_index"]),
        "hero_origin": {"x": ox, "y": oy, "z": oz},
        "old_entity_count": int(parsed["entity_count"]),
        "new_entity_count": int(result_parsed["entity_count"]),
        "added_entities": len(new_records),
        "groups": dict(Counter(row["group"] for row in world_rows)),
        "assets": dict(Counter(row["asset"] for row in world_rows)),
        "changed_decrypted_members": changed,
        "geometry_checks": "pass",
        "native_visual_review": "pending",
        "placements": placement_rows,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 measured city v10")
    print(f"Target road source: {report['source_fpm']}")
    print(f"CyberCity donor:    {report['donor_fpm']}")
    print(f"Output:             {report['output_fpm']}")
    print(f"Hero origin:        {report['hero_origin']}")
    print(f"Added entities:     {report['added_entities']}")
    for group, count in sorted(report["groups"].items()):
        print(f"  {group:20s} {count}")
    print("[PASS] Complete measured shell courses and roofs were authored explicitly.")
    print("[PASS] Validated target roads were preserved and used for collision checks.")
    print("[PASS] Junction corners and street lamps remain owned by the semantic road pass.")
    print("[NEXT] Native GameGuru MAX visual review is still required before production acceptance.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument("--donor-fpm", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--max-additions", type=int, default=1200)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compile_measured_city(
            args.source_fpm,
            args.output_fpm,
            args.donor_fpm,
            args.measurements,
            args.max_additions,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"MEASURED CITY V10 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
