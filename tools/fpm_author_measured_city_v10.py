#!/usr/bin/env python3
"""Author Astra's measured Hero Block shells and v10.1 storefront bases onto District 12.

This pass reuses Astra's measured calibration plan instead of harvesting nearby CyberCity
pivots as alleged buildings. The validated target road FPM remains authoritative: roads
are never replaced. Measured sidewalks plus complete building shells are authored around
the most central 4-way junction, and the four ground-floor corner modules on every hero
building are replaced with measured CyberCity storefront corner modules.

Drop-curb junction corners and street lamps remain owned by the semantic road pass, so
this writer never competes for road dressing ownership.
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
STOREFRONT_ASSETS = (
    "CS_Store_Front_02_Corner_With_Window",
    "CS_Store_Front_02_Corner_Neon_Opposite",
)
GROUND_FLOOR_Y = 10.0
HERO_GROUPS = tuple(parcel["name"] for parcel in hero.PARCELS)
STOREFRONTS_PER_BUILDING = 4


def asset_key(asset_path: str | None) -> str:
    return Path((asset_path or "").replace("\\", "/")).stem


def storefront_wrapped_calibration(measured: dict[str, Any]) -> list[dict[str, Any]]:
    """Replace only ground-floor shell corners with measured CyberCity shop corners.

    The original Astra shell is validated first. Storefronts inherit the exact corner
    pivots/yaws of the proven 200-unit shell courses, so upper floors, entries, roofs and
    parcel dimensions remain untouched. The two shop variants alternate deterministically
    by building/corner to avoid cloning one identical frontage around the whole block.
    """
    missing = [name for name in STOREFRONT_ASSETS if name not in measured]
    if missing:
        raise FpmError(
            "Measured storefront geometry is missing: "
            + ", ".join(missing)
            + ". Rerun measure-cybercity-kit.py against the installed Cyberpunk Streets pack."
        )

    calibration = hero.plan()
    hero.validate(calibration, measured)
    parcel_index = {name: i for i, name in enumerate(HERO_GROUPS)}
    seen: Counter[str] = Counter()
    wrapped: list[dict[str, Any]] = []

    for row in calibration:
        replacement = dict(row)
        if (
            row["group"] in parcel_index
            and row["asset"] == "CS_Wall_Corner_01"
            and abs(float(row["y"]) - GROUND_FLOOR_Y) <= 0.01
        ):
            corner_ordinal = seen[row["group"]]
            seen[row["group"]] += 1
            replacement["asset"] = STOREFRONT_ASSETS[
                (parcel_index[row["group"]] + corner_ordinal) % len(STOREFRONT_ASSETS)
            ]
        wrapped.append(replacement)

    for group in HERO_GROUPS:
        if seen[group] != STOREFRONTS_PER_BUILDING:
            raise FpmError(
                f"Storefront wrap expected {STOREFRONTS_PER_BUILDING} ground-floor corners for {group}, got {seen[group]}."
            )

    if any(
        row["group"] in HERO_GROUPS
        and row["asset"] == "CS_Wall_Corner_01"
        and abs(float(row["y"]) - GROUND_FLOOR_Y) <= 0.01
        for row in wrapped
    ):
        raise FpmError("Blank ground-floor hero corners remain after storefront wrapping.")
    return wrapped


def measured_additions(measured: dict[str, Any]) -> list[dict[str, Any]]:
    """Return calibrated non-road content with a measured shopfront ground-floor wrap."""
    calibration = storefront_wrapped_calibration(measured)
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
        if row["asset"] not in measured:
            raise FpmError(f"No measured bounds available for authored asset: {row['asset']}")
        box = hero.world_bounds(row, measured)
        if any(intersects(box, road_box) for road_box in road_boxes):
            raise FpmError(
                f"Measured building placement intersects validated road geometry: {row['group']} / {row['asset']}"
            )


def donor_templates(
    donor_parsed: dict[str, Any], donor_ele: bytes, required: set[str], donor_path: Path
) -> dict[str, fabric.Template]:
    out: dict[str, fabric.Template] = {}
    required_fold = {name.casefold(): name for name in required}
    for entity in donor_parsed["entities"]:
        raw_key = asset_key(entity.get("asset"))
        canonical = required_fold.get(raw_key.casefold())
        if canonical is None or canonical in out:
            continue
        safe, _reason = fabric.safe_template_entity(entity, False)
        if not safe or int(entity.get("profile_scale", 100)) != 100:
            continue
        if any(abs(float(v)) > 0.001 for v in entity.get("scale_xyz", {}).values()):
            continue
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        out[canonical] = fabric.Template(
            role="measured-city-v10.1",
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

    storefront_count = sum(1 for row in world_rows if row["asset"] in STOREFRONT_ASSETS)
    if storefront_count != len(HERO_GROUPS) * STOREFRONTS_PER_BUILDING:
        output_path.unlink(missing_ok=True)
        raise FpmError(f"Unexpected storefront count in final measured plan: {storefront_count}")

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
        "storefront_count": storefront_count,
        "groups": dict(Counter(row["group"] for row in world_rows)),
        "assets": dict(Counter(row["asset"] for row in world_rows)),
        "changed_decrypted_members": changed,
        "geometry_checks": "pass",
        "native_visual_review": "pending",
        "placements": placement_rows,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 measured city v10.1")
    print(f"Target road source: {report['source_fpm']}")
    print(f"CyberCity donor:    {report['donor_fpm']}")
    print(f"Output:             {report['output_fpm']}")
    print(f"Hero origin:        {report['hero_origin']}")
    print(f"Added entities:     {report['added_entities']}")
    print(f"Storefront corners: {report['storefront_count']}")
    for group, count in sorted(report["groups"].items()):
        print(f"  {group:20s} {count}")
    print("[PASS] Complete measured shell courses and roofs were authored explicitly.")
    print("[PASS] Ground-floor blank corners were replaced by measured CyberCity storefront modules.")
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
        print(f"MEASURED CITY V10.1 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
