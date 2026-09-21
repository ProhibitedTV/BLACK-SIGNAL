#!/usr/bin/env python3
"""Densify District 12 by cloning complete, engine-authored Cyber City building clusters.

This deliberately does NOT invent modular-building coordinates. It learns complete
foreground building clusters and background skyline stacks from the installed
CyberCity exemplar, then reuses those exact spatial assemblies against other road
anchors in the same map. Only map.ele changes; all cloned records remain tied to
existing map.ent bank entries.
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
from typing import Any

import fpm_author_street_fabric as base
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


@dataclass
class Cluster:
    entities: list[dict[str, Any]]
    kind: str
    min_x: float
    max_x: float
    min_z: float
    max_z: float
    min_y: float
    max_y: float

    @property
    def cx(self) -> float:
        return (self.min_x + self.max_x) * 0.5

    @property
    def cz(self) -> float:
        return (self.min_z + self.max_z) * 0.5

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_z - self.min_z


@dataclass
class ClonePlan:
    cluster: Cluster
    anchor_source: dict[str, Any] | None
    anchor_target: dict[str, Any] | None
    dx: float
    dy: float
    dz: float
    yaw_delta: float
    label: str


def norm(value: str | None) -> str:
    return (value or "").replace("/", "\\").lower()


def is_road(e: dict[str, Any]) -> bool:
    p = norm(e.get("asset"))
    return "\\cyberpunk streets booster pack\\streets and sidewalks\\streets\\cs_street_" in p and "light_marker" not in p


def is_foreground_building(e: dict[str, Any]) -> bool:
    p = norm(e.get("asset"))
    return "\\cyberpunk streets booster pack\\" in p and ("\\buildings\\" in p or "\\store fronts\\" in p)


def is_background_building(e: dict[str, Any]) -> bool:
    p = norm(e.get("asset"))
    return "\\cyberpunk streets booster pack\\background buildings\\" in p


def safe_static(e: dict[str, Any]) -> bool:
    ok, _ = base.safe_template_entity(e, False)
    return ok


def make_cluster(entities: list[dict[str, Any]], kind: str) -> Cluster:
    xs = [float(e["position"]["x"]) for e in entities]
    ys = [float(e["position"]["y"]) for e in entities]
    zs = [float(e["position"]["z"]) for e in entities]
    return Cluster(entities, kind, min(xs), max(xs), min(zs), max(zs), min(ys), max(ys))


def cluster_entities(entities: list[dict[str, Any]], kind: str, radius: float) -> list[Cluster]:
    """Connected components in X/Z. Keeps complete authored assemblies together."""
    if not entities:
        return []
    rr = radius * radius
    remaining = set(range(len(entities)))
    clusters: list[Cluster] = []
    while remaining:
        seed = remaining.pop()
        component = [seed]
        queue = [seed]
        while queue:
            i = queue.pop()
            pi = entities[i]["position"]
            attach: list[int] = []
            for j in remaining:
                pj = entities[j]["position"]
                dx = float(pi["x"]) - float(pj["x"])
                dz = float(pi["z"]) - float(pj["z"])
                if dx * dx + dz * dz <= rr:
                    attach.append(j)
            for j in attach:
                remaining.remove(j)
                component.append(j)
                queue.append(j)
        clusters.append(make_cluster([entities[i] for i in component], kind))
    return clusters


def nearest_road(cluster: Cluster, roads: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        roads,
        key=lambda r: (float(r["position"]["x"]) - cluster.cx) ** 2
        + (float(r["position"]["z"]) - cluster.cz) ** 2,
    )


def bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float], pad: float = 0.0) -> bool:
    aminx, amaxx, aminz, amaxz = a
    bminx, bmaxx, bminz, bmaxz = b
    return not (
        amaxx + pad < bminx or aminx - pad > bmaxx or amaxz + pad < bminz or aminz - pad > bmaxz
    )


def rotate_point(x: float, z: float, yaw_deg: float) -> tuple[float, float]:
    r = math.radians(yaw_deg)
    c = math.cos(r)
    s = math.sin(r)
    return (x * c + z * s, -x * s + z * c)


def transform_position(
    pos: dict[str, float], source_anchor: dict[str, Any], target_anchor: dict[str, Any]
) -> tuple[float, float, float, float]:
    syaw = float(source_anchor["rotation_euler"]["y"])
    tyaw = float(target_anchor["rotation_euler"]["y"])
    delta = (tyaw - syaw) % 360.0
    sx = float(source_anchor["position"]["x"])
    sy = float(source_anchor["position"]["y"])
    sz = float(source_anchor["position"]["z"])
    tx = float(target_anchor["position"]["x"])
    ty = float(target_anchor["position"]["y"])
    tz = float(target_anchor["position"]["z"])
    rx, rz = rotate_point(float(pos["x"]) - sx, float(pos["z"]) - sz, delta)
    return tx + rx, ty + (float(pos["y"]) - sy), tz + rz, delta


def candidate_bbox(cluster: Cluster, source_anchor: dict[str, Any], target_anchor: dict[str, Any]) -> tuple[float, float, float, float]:
    pts = [
        {"x": cluster.min_x, "y": cluster.min_y, "z": cluster.min_z},
        {"x": cluster.min_x, "y": cluster.min_y, "z": cluster.max_z},
        {"x": cluster.max_x, "y": cluster.min_y, "z": cluster.min_z},
        {"x": cluster.max_x, "y": cluster.min_y, "z": cluster.max_z},
    ]
    out = [transform_position(p, source_anchor, target_anchor) for p in pts]
    xs = [p[0] for p in out]
    zs = [p[2] for p in out]
    return min(xs), max(xs), min(zs), max(zs)


def road_clearance_ok(cluster: Cluster, source_anchor: dict[str, Any], target_anchor: dict[str, Any], roads: list[dict[str, Any]]) -> bool:
    # Source-authored building-to-road geometry is preserved around the target anchor.
    # Reject only if the transplanted shell lands directly on some OTHER road center.
    transformed = [transform_position(e["position"], source_anchor, target_anchor) for e in cluster.entities]
    target_id = target_anchor["record_index"]
    for x, _y, z, _d in transformed:
        for road in roads:
            if road["record_index"] == target_id:
                continue
            rp = road["position"]
            if (x - float(rp["x"])) ** 2 + (z - float(rp["z"])) ** 2 < 185.0 ** 2:
                return False
    return True


def choose_foreground_plans(parsed: dict[str, Any], max_clones: int) -> list[ClonePlan]:
    roads = [e for e in parsed["entities"] if is_road(e)]
    structures = [e for e in parsed["entities"] if is_foreground_building(e) and safe_static(e)]
    clusters = [
        c
        for c in cluster_entities(structures, "foreground", 525.0)
        if len(c.entities) >= 4 and c.width <= 2200.0 and c.depth <= 2200.0
    ]
    if not roads or not clusters:
        raise FpmError("Could not find safe foreground building clusters and roads in the CyberCity exemplar.")

    # Prefer complete, information-rich assemblies without letting one giant connected mass dominate.
    clusters.sort(key=lambda c: (-len(c.entities), c.width * c.depth))
    exemplars = clusters[: min(6, len(clusters))]

    existing_boxes = [(c.min_x, c.max_x, c.min_z, c.max_z) for c in clusters]
    accepted_boxes: list[tuple[float, float, float, float]] = []
    plans: list[ClonePlan] = []

    # Most useful road anchors first: central road network rather than extreme perimeter pieces.
    road_cx = statistics.median(float(r["position"]["x"]) for r in roads)
    road_cz = statistics.median(float(r["position"]["z"]) for r in roads)
    target_roads = sorted(
        roads,
        key=lambda r: (
            (float(r["position"]["x"]) - road_cx) ** 2 + (float(r["position"]["z"]) - road_cz) ** 2,
            r["record_index"],
        ),
    )

    # Learn each exemplar's exact relationship to its nearest road and transplant that grammar.
    source_pairs = [(c, nearest_road(c, roads)) for c in exemplars]
    for target in target_roads:
        if len(plans) >= max_clones:
            break
        for cluster, source in source_pairs:
            if source["record_index"] == target["record_index"]:
                continue
            # Match road piece type when possible; this keeps intersections/straights from being conflated.
            if base.basename(source.get("asset")) != base.basename(target.get("asset")):
                continue
            box = candidate_bbox(cluster, source, target)
            if any(bbox_intersects(box, b, 120.0) for b in existing_boxes):
                continue
            if any(bbox_intersects(box, b, 120.0) for b in accepted_boxes):
                continue
            if not road_clearance_ok(cluster, source, target, roads):
                continue
            plans.append(ClonePlan(cluster, source, target, 0.0, 0.0, 0.0, 0.0, f"streetwall-{len(plans)+1}"))
            accepted_boxes.append(box)
            break
    return plans


def choose_background_plans(parsed: dict[str, Any], max_clones: int) -> list[ClonePlan]:
    roads = [e for e in parsed["entities"] if is_road(e)]
    bg_entities = [e for e in parsed["entities"] if is_background_building(e) and safe_static(e)]
    clusters = [c for c in cluster_entities(bg_entities, "background", 650.0) if len(c.entities) >= 2]
    if not roads or not clusters or max_clones <= 0:
        return []
    clusters.sort(key=lambda c: (-len(c.entities), -(c.max_y - c.min_y)))
    exemplars = clusters[: min(4, len(clusters))]

    min_x = min(float(r["position"]["x"]) for r in roads)
    max_x = max(float(r["position"]["x"]) for r in roads)
    min_z = min(float(r["position"]["z"]) for r in roads)
    max_z = max(float(r["position"]["z"]) for r in roads)
    ground_y = statistics.median(float(r["position"]["y"]) for r in roads)
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

    plans: list[ClonePlan] = []
    for i, target in enumerate(targets[:max_clones]):
        c = exemplars[i % len(exemplars)]
        # Background stacks are translated/rotated as intact assemblies around their own centroid.
        tx, ty, tz, yaw = target
        plans.append(
            ClonePlan(
                c,
                None,
                None,
                tx - c.cx,
                ty - c.min_y,
                tz - c.cz,
                yaw,
                f"skyline-{i+1}",
            )
        )
    return plans


def clone_record(raw: bytes, entity: dict[str, Any], x: float, y: float, z: float, yaw: float) -> bytes:
    template = base.Template(
        role="city_mass",
        asset_path=str(entity.get("asset") or ""),
        parsed=entity,
        raw_record=raw,
        source_fpm="CyberCity exemplar",
        source_kind="exact-exemplar-record",
    )
    placement = base.Placement(role="city_mass", x=x, y=y, z=z, ry=yaw)
    return _patched_patch_record(template, int(entity["bankindex"]), placement)


def plan_entity_transform(plan: ClonePlan, entity: dict[str, Any]) -> tuple[float, float, float, float]:
    p = entity["position"]
    source_yaw = float(entity["rotation_euler"]["y"])
    if plan.anchor_source is not None and plan.anchor_target is not None:
        x, y, z, delta = transform_position(p, plan.anchor_source, plan.anchor_target)
        return x, y, z, (source_yaw + delta) % 360.0
    # Background plan rotates around cluster centroid, then translates.
    relx = float(p["x"]) - plan.cluster.cx
    relz = float(p["z"]) - plan.cluster.cz
    rx, rz = rotate_point(relx, relz, plan.yaw_delta)
    x = plan.cluster.cx + plan.dx + rx
    y = float(p["y"]) + plan.dy
    z = plan.cluster.cz + plan.dz + rz
    return x, y, z, (source_yaw + plan.yaw_delta) % 360.0


def compile_city_mass(source_path: Path, output_path: Path, streetwall_clones: int, skyline_clones: int, max_additions: int) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source.")

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}

        fg_plans = choose_foreground_plans(parsed, streetwall_clones)
        bg_plans = choose_background_plans(parsed, skyline_clones)
        plans = fg_plans + bg_plans
        new_records: list[bytes] = []
        rows: list[dict[str, Any]] = []
        for plan in plans:
            for entity in plan.cluster.entities:
                start = int(entity["record_start_offset"])
                end = int(entity["record_end_offset"])
                x, y, z, yaw = plan_entity_transform(plan, entity)
                new_records.append(clone_record(ele_data[start:end], entity, x, y, z, yaw))
                rows.append({
                    "plan": plan.label,
                    "kind": plan.cluster.kind,
                    "source_record": entity["record_index"],
                    "asset": entity.get("asset"),
                    "x": x, "y": y, "z": z, "ry": yaw,
                })

        if not fg_plans:
            raise FpmError("No non-overlapping foreground street-wall clone locations were found.")
        if len(new_records) > max_additions:
            raise FpmError(f"City mass plan adds {len(new_records)} entities, above --max-additions={max_additions}.")

        new_ele = bytearray(ele_data)
        struct.pack_into("<i", new_ele, 4, int(parsed["entity_count"]) + len(new_records))
        for record in new_records:
            new_ele += record
        members = base.archive_members_with_replacements(source, {"map.ele": bytes(new_ele)})

    write_zipcrypto_archive(output_path, members)
    with FpmArchive(output_path) as generated:
        gent = parse_map_ent(generated.read("map.ent"))
        gele = generated.read("map.ele")
        gparsed = parse_map_ele(gele, gent["entries"])
        generated_manifest = {row["name"]: row["sha256"] for row in generated.member_manifest()}

    expected = int(parsed["entity_count"]) + len(new_records)
    if int(gparsed["entity_count"]) != expected or not gparsed["fully_traversed"] or gparsed["trailing_bytes"] != 0:
        raise FpmError("Generated city FPM failed exact ELE traversal/count verification.")
    changed = sorted(name for name, sha in generated_manifest.items() if source_manifest.get(name) != sha)
    allowed = {name for name in generated_manifest if name.replace("\\", "/").lower() == "map.ele"}
    if set(changed) - allowed:
        raise FpmError("Generated city FPM changed unrelated members: " + ", ".join(sorted(set(changed) - allowed)))

    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "ele_version": parsed["version"],
        "old_entity_count": parsed["entity_count"],
        "new_entity_count": gparsed["entity_count"],
        "added_entities": len(new_records),
        "streetwall_clone_count": len(fg_plans),
        "skyline_clone_count": len(bg_plans),
        "changed_decrypted_members": changed,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "placements": rows,
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 city mass compiler")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"ELE version: {report['ele_version']}")
    print(f"Entities: {report['old_entity_count']} -> {report['new_entity_count']} (+{report['added_entities']})")
    print(f"Street-wall assemblies cloned: {report['streetwall_clone_count']}")
    print(f"Skyline assemblies cloned:     {report['skyline_clone_count']}")
    print("[PASS] Generated FPM reopens and traverses exactly to EOF.")
    print("[PASS] map.ent unchanged; only map.ele changed.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_fpm", type=Path)
    p.add_argument("output_fpm", type=Path)
    p.add_argument("--streetwall-clones", type=int, default=10)
    p.add_argument("--skyline-clones", type=int, default=8)
    p.add_argument("--max-additions", type=int, default=1800)
    p.add_argument("--report-json", type=Path)
    args = p.parse_args(argv)
    try:
        report = compile_city_mass(args.source_fpm, args.output_fpm, args.streetwall_clones, args.skyline_clones, args.max_additions)
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM CITY MASS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
