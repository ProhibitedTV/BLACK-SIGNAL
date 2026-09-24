#!/usr/bin/env python3
"""Compose authored CyberCity building mass onto District 12's coherent road system.

Unlike the legacy city-mass compiler, this pass keeps the target road FPM and the
CyberCity exemplar separate. Building assemblies are harvested from CyberCity,
then transplanted onto compatible road-family anchors in the already-built District
12 road system. The target's roads, road markings, lighting and surface dressing
remain authoritative.

This prevents the two production builders from replacing each other: the road build
no longer ends as an empty test grid, and the city build no longer discards the
coherent road network by starting over from stock CyberCity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import struct
import sys
from pathlib import Path
from typing import Any

import fpm_author_city_mass as city
import fpm_author_city_mass_compat as compat
import fpm_author_road_details_v4 as road_details
import fpm_author_road_network_v2 as roads
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


def configure_city_compat() -> None:
    """Use the proven CyberCity path/group compatibility rules without hiding them."""
    city.is_road = compat._is_road
    city.is_foreground_building = compat._is_foreground_building
    city.is_background_building = compat._is_background_building
    city.safe_static = compat._cloneable_city_piece
    city.cluster_entities = compat._adaptive_cluster_entities


def recognized_roads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Return actual full-width road surfaces, never bollards or other CS_Street props."""
    return [
        entity
        for entity in parsed["entities"]
        if roads.road_kind(entity.get("asset")) in road_details.ALLOWED_ROAD_KINDS
    ]


def _foreground_clusters(parsed: dict[str, Any]) -> list[city.Cluster]:
    structures = [
        entity
        for entity in parsed["entities"]
        if city.is_foreground_building(entity) and city.safe_static(entity)
    ]
    clusters = [
        cluster
        for cluster in city.cluster_entities(structures, "foreground", 525.0)
        if compat._valid_cluster(cluster, "foreground")
    ]
    clusters.sort(key=lambda cluster: (-len(cluster.entities), cluster.width * cluster.depth))
    return clusters


def _background_clusters(parsed: dict[str, Any]) -> list[city.Cluster]:
    structures = [
        entity
        for entity in parsed["entities"]
        if city.is_background_building(entity) and city.safe_static(entity)
    ]
    clusters = [
        cluster
        for cluster in city.cluster_entities(structures, "background", 650.0)
        if compat._valid_cluster(cluster, "background")
    ]
    clusters.sort(key=lambda cluster: (-len(cluster.entities), -(cluster.max_y - cluster.min_y)))
    return clusters


def _existing_foreground_boxes(parsed: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    return [
        (cluster.min_x, cluster.max_x, cluster.min_z, cluster.max_z)
        for cluster in _foreground_clusters(parsed)
    ]


def choose_foreground_plans(
    donor_parsed: dict[str, Any],
    target_parsed: dict[str, Any],
    max_clones: int,
) -> list[city.ClonePlan]:
    donor_roads = recognized_roads(donor_parsed)
    target_roads = recognized_roads(target_parsed)
    clusters = _foreground_clusters(donor_parsed)
    if not donor_roads or not target_roads or not clusters:
        raise FpmError(
            "Could not find donor building assemblies plus recognized donor/target road anchors."
        )

    exemplars = clusters[: min(8, len(clusters))]
    source_pairs = [(cluster, city.nearest_road(cluster, donor_roads)) for cluster in exemplars]

    target_cx = statistics.median(float(road["position"]["x"]) for road in target_roads)
    target_cz = statistics.median(float(road["position"]["z"]) for road in target_roads)
    target_roads = sorted(
        target_roads,
        key=lambda road: (
            (float(road["position"]["x"]) - target_cx) ** 2
            + (float(road["position"]["z"]) - target_cz) ** 2,
            int(road["record_index"]),
        ),
    )

    existing_boxes = _existing_foreground_boxes(target_parsed)
    accepted_boxes: list[tuple[float, float, float, float]] = []
    plans: list[city.ClonePlan] = []

    for target in target_roads:
        if len(plans) >= max_clones:
            break
        target_kind = roads.road_kind(target.get("asset"))
        if target_kind is None:
            continue
        for cluster, source in source_pairs:
            if roads.road_kind(source.get("asset")) != target_kind:
                continue
            box = city.candidate_bbox(cluster, source, target)
            if any(city.bbox_intersects(box, other, 120.0) for other in existing_boxes):
                continue
            if any(city.bbox_intersects(box, other, 120.0) for other in accepted_boxes):
                continue
            if not city.road_clearance_ok(cluster, source, target, target_roads):
                continue
            plans.append(
                city.ClonePlan(
                    cluster,
                    source,
                    target,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    f"streetwall-{len(plans) + 1}",
                )
            )
            accepted_boxes.append(box)
            break
    return plans


def choose_background_plans(
    donor_parsed: dict[str, Any],
    target_parsed: dict[str, Any],
    max_clones: int,
) -> list[city.ClonePlan]:
    target_roads = recognized_roads(target_parsed)
    clusters = _background_clusters(donor_parsed)
    if not target_roads or not clusters or max_clones <= 0:
        return []

    exemplars = clusters[: min(4, len(clusters))]
    min_x = min(float(road["position"]["x"]) for road in target_roads)
    max_x = max(float(road["position"]["x"]) for road in target_roads)
    min_z = min(float(road["position"]["z"]) for road in target_roads)
    max_z = max(float(road["position"]["z"]) for road in target_roads)
    ground_y = statistics.median(float(road["position"]["y"]) for road in target_roads)
    cx = (min_x + max_x) * 0.5
    cz = (min_z + max_z) * 0.5
    margin = 1050.0
    targets = [
        (min_x - margin, ground_y, cz, 90.0),
        (max_x + margin, ground_y, cz, 270.0),
        (cx, ground_y, min_z - margin, 0.0),
        (cx, ground_y, max_z + margin, 180.0),
        (min_x - margin, ground_y, min_z - margin, 45.0),
        (max_x + margin, ground_y, min_z - margin, 315.0),
        (min_x - margin, ground_y, max_z + margin, 135.0),
        (max_x + margin, ground_y, max_z + margin, 225.0),
    ]

    plans: list[city.ClonePlan] = []
    for index, target in enumerate(targets[:max_clones]):
        cluster = exemplars[index % len(exemplars)]
        tx, ty, tz, yaw = target
        plans.append(
            city.ClonePlan(
                cluster,
                None,
                None,
                tx - cluster.cx,
                ty - cluster.min_y,
                tz - cluster.cz,
                yaw,
                f"skyline-{index + 1}",
            )
        )
    return plans


def ensure_bank_index(bank_paths: list[str], lookup: dict[str, int], asset_path: str) -> int:
    key = fabric.norm(asset_path)
    if key not in lookup:
        bank_paths.append(asset_path)
        lookup[key] = len(bank_paths)
    return lookup[key]


def clone_donor_record(
    raw_record: bytes,
    entity: dict[str, Any],
    bank_index: int,
    x: float,
    y: float,
    z: float,
    yaw: float,
) -> bytes:
    template = fabric.Template(
        role="city_mass_v2",
        asset_path=str(entity.get("asset") or ""),
        parsed=entity,
        raw_record=raw_record,
        source_fpm="CyberCity donor",
        source_kind="exact-donor-record",
    )
    placement = fabric.Placement(role="city_mass_v2", x=x, y=y, z=z, ry=yaw)
    return _patched_patch_record(template, bank_index, placement)


def compile_city_mass(
    source_path: Path,
    output_path: Path,
    donor_path: Path,
    streetwall_clones: int,
    skyline_clones: int,
    max_additions: int,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    donor_path = donor_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source.")
    if not donor_path.exists():
        raise FpmError(f"CyberCity donor does not exist: {donor_path}")

    configure_city_compat()

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        if ent["encoding"] != "crlf":
            raise FpmError("Integrated city writer requires CRLF map.ent encoding.")
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}
        road_counts = road_details.validate_uniform_grammar(parsed)

        with FpmArchive(donor_path) as donor:
            donor_ent = parse_map_ent(donor.read("map.ent"))
            donor_ele = donor.read("map.ele")
            donor_parsed = parse_map_ele(donor_ele, donor_ent["entries"])
            verify_raw_ele_roundtrip(donor_ele, donor_parsed)
            if int(donor_parsed["version"]) != int(parsed["version"]):
                raise FpmError(
                    "CyberCity donor ELE version does not match target "
                    f"({donor_parsed['version']} != {parsed['version']})."
                )

            foreground = choose_foreground_plans(donor_parsed, parsed, streetwall_clones)
            background = choose_background_plans(donor_parsed, parsed, skyline_clones)
            plans = foreground + background
            if not foreground:
                raise FpmError(
                    "No compatible non-overlapping foreground building placements were found. "
                    "Refusing to promote an empty road-only city."
                )

            planned_entities = sum(len(plan.cluster.entities) for plan in plans)
            if planned_entities > max_additions:
                raise FpmError(
                    f"Integrated city plan adds {planned_entities} entities, "
                    f"above --max-additions={max_additions}."
                )

            bank_paths = [entry["path"] for entry in ent["entries"]]
            bank_lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
            new_records: list[bytes] = []
            placement_rows: list[dict[str, Any]] = []

            for plan in plans:
                for entity in plan.cluster.entities:
                    start = int(entity["record_start_offset"])
                    end = int(entity["record_end_offset"])
                    x, y, z, yaw = city.plan_entity_transform(plan, entity)
                    asset_path = str(entity.get("asset") or "")
                    if not asset_path:
                        raise FpmError(
                            f"Donor city entity #{entity['record_index']} has no asset path."
                        )
                    bank_index = ensure_bank_index(bank_paths, bank_lookup, asset_path)
                    new_records.append(
                        clone_donor_record(
                            donor_ele[start:end], entity, bank_index, x, y, z, yaw
                        )
                    )
                    placement_rows.append(
                        {
                            "plan": plan.label,
                            "kind": plan.cluster.kind,
                            "source_record": int(entity["record_index"]),
                            "asset": asset_path,
                            "target_bank_index": bank_index,
                            "x": x,
                            "y": y,
                            "z": z,
                            "ry": yaw,
                        }
                    )

        new_ele = bytearray(ele_data)
        struct.pack_into("<i", new_ele, 4, int(parsed["entity_count"]) + len(new_records))
        for record in new_records:
            new_ele += record
        new_ent = fabric.serialize_map_ent(bank_paths)
        members = fabric.archive_members_with_replacements(
            source, {"map.ent": new_ent, "map.ele": bytes(new_ele)}
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_zipcrypto_archive(output_path, members)

    with FpmArchive(output_path) as generated:
        generated_ent = parse_map_ent(generated.read("map.ent"))
        generated_ele = generated.read("map.ele")
        generated_parsed = parse_map_ele(generated_ele, generated_ent["entries"])
        generated_manifest = {
            row["name"]: row["sha256"] for row in generated.member_manifest()
        }

    expected = int(parsed["entity_count"]) + len(new_records)
    if (
        int(generated_parsed["entity_count"]) != expected
        or not generated_parsed["fully_traversed"]
        or int(generated_parsed["trailing_bytes"]) != 0
    ):
        raise FpmError("Integrated city FPM failed exact ELE traversal/count verification.")

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
            "Integrated city compiler changed unrelated FPM members: "
            + ", ".join(sorted(set(changed) - allowed))
        )

    return {
        "source_fpm": str(source_path),
        "donor_fpm": str(donor_path),
        "output_fpm": str(output_path),
        "ele_version": int(parsed["version"]),
        "road_counts": road_counts,
        "old_entity_count": int(parsed["entity_count"]),
        "new_entity_count": int(generated_parsed["entity_count"]),
        "added_entities": len(new_records),
        "streetwall_clone_count": len(foreground),
        "skyline_clone_count": len(background),
        "changed_decrypted_members": changed,
        "placements": placement_rows,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 integrated city mass v2")
    print(f"Target road source: {report['source_fpm']}")
    print(f"CyberCity donor:    {report['donor_fpm']}")
    print(f"Output:             {report['output_fpm']}")
    print(f"Street-wall assemblies cloned: {report['streetwall_clone_count']}")
    print(f"Skyline assemblies cloned:     {report['skyline_clone_count']}")
    print(f"Added city entities:           {report['added_entities']}")
    print("[PASS] Coherent target road network remained the production base.")
    print("[PASS] Buildings came from exact CyberCity-authored assemblies.")
    print("[PASS] No generic CS_Street props were mistaken for road anchors.")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument("--donor-fpm", type=Path, required=True)
    parser.add_argument("--streetwall-clones", type=int, default=18)
    parser.add_argument("--skyline-clones", type=int, default=8)
    parser.add_argument("--max-additions", type=int, default=2400)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compile_city_mass(
            args.source_fpm,
            args.output_fpm,
            args.donor_fpm,
            args.streetwall_clones,
            args.skyline_clones,
            args.max_additions,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM INTEGRATED CITY V2 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
