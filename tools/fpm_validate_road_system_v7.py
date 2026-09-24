#!/usr/bin/env python3
"""Fail-closed validation gate for the District 12 v7 road pipeline.

The compiler should never promote a map merely because the FPM can be parsed. This
validator cross-checks the final authored map against the foundation/detail/surface
reports immediately before promotion. It is intentionally strict: a missing road,
unexpected recognized road, duplicate pivot, broken planned span, policy regression,
or semantically invalid approach marking aborts the production build.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as legacy
import fpm_author_road_surface_v6 as v6
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


EXPECTED_DETAIL_POLICY = "nearest-compatible-road-owner"
EXPECTED_SURFACE_POLICY = "role-aware-nearest-compatible-road"
EXPECTED_APPROACH_JUNCTIONS = ("fourway", "tee")
NODE_RE = re.compile(r"^node-(\d+)-(\d+)$")
HSPAN_RE = re.compile(r"^avenue-h-(\d+)-(\d+)$")
VSPAN_RE = re.compile(r"^avenue-v-(\d+)-(\d+)$")


def _q(value: float, scale: float = 10.0) -> int:
    return int(round(float(value) * scale))


def _yaw_q(value: float) -> int:
    return _q(float(value) % 360.0)


def _expected_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["kind"],
        _q(row["x"]),
        _q(row["y"]),
        _q(row["z"]),
        _yaw_q(row["yaw"]),
    )


def _actual_signature(entity: dict[str, Any]) -> tuple[Any, ...]:
    p = entity["position"]
    return (
        legacy.road_kind(entity.get("asset")),
        _q(p["x"]),
        _q(p["y"]),
        _q(p["z"]),
        _yaw_q(entity["rotation_euler"]["y"]),
    )


def validate_foundation_contract(report: dict[str, Any]) -> list[str]:
    """Validate the planned road graph encoded by the v3 foundation report."""
    errors: list[str] = []
    grid_size = int(report.get("grid_size", 0))
    placements = list(report.get("placements") or [])
    if grid_size < 5 or grid_size % 2 == 0:
        return [f"invalid foundation grid_size={grid_size}"]
    if not placements:
        return ["foundation report contains no placements"]

    nodes: dict[tuple[int, int], dict[str, Any]] = {}
    hspans: dict[tuple[int, int], list[dict[str, Any]]] = {}
    vspans: dict[tuple[int, int], list[dict[str, Any]]] = {}
    unknown_notes: list[str] = []

    for row in placements:
        note = str(row.get("note") or "")
        match = NODE_RE.match(note)
        if match:
            key = (int(match.group(1)), int(match.group(2)))
            if key in nodes:
                errors.append(f"duplicate planned node {note}")
            nodes[key] = row
            continue
        match = HSPAN_RE.match(note)
        if match:
            key = (int(match.group(1)), int(match.group(2)))
            hspans.setdefault(key, []).append(row)
            continue
        match = VSPAN_RE.match(note)
        if match:
            key = (int(match.group(1)), int(match.group(2)))
            vspans.setdefault(key, []).append(row)
            continue
        unknown_notes.append(note)

    expected_nodes = grid_size * grid_size
    if len(nodes) != expected_nodes:
        errors.append(f"planned node count {len(nodes)} != {expected_nodes}")
    if unknown_notes:
        errors.append("unrecognized foundation placement notes: " + ", ".join(sorted(set(unknown_notes))))

    directions = {
        "E": (1, 0, "W"),
        "W": (-1, 0, "E"),
        "N": (0, 1, "S"),
        "S": (0, -1, "N"),
    }
    for (ix, iz), row in sorted(nodes.items()):
        exits = set(row.get("connections") or [])
        for direction, (dx, dz, reciprocal) in directions.items():
            neighbor_key = (ix + dx, iz + dz)
            neighbor_exists = neighbor_key in nodes
            has_exit = direction in exits
            if has_exit != neighbor_exists:
                errors.append(
                    f"node-{ix}-{iz} {direction} exit={has_exit} but neighbor_exists={neighbor_exists}"
                )
                continue
            if neighbor_exists:
                neighbor_exits = set(nodes[neighbor_key].get("connections") or [])
                if reciprocal not in neighbor_exits:
                    errors.append(
                        f"node-{ix}-{iz} {direction} is not reciprocated by node-{neighbor_key[0]}-{neighbor_key[1]}"
                    )

    for iz in range(grid_size):
        for ix in range(grid_size - 1):
            rows = hspans.get((ix, iz), [])
            if len(rows) != 3:
                errors.append(f"horizontal span {ix},{iz} has {len(rows)} modules; expected 3")
            for row in rows:
                if row.get("kind") != "straight4" or set(row.get("connections") or []) != {"E", "W"}:
                    errors.append(f"horizontal span {ix},{iz} contains non-uniform module")

    for ix in range(grid_size):
        for iz in range(grid_size - 1):
            rows = vspans.get((ix, iz), [])
            if len(rows) != 3:
                errors.append(f"vertical span {ix},{iz} has {len(rows)} modules; expected 3")
            for row in rows:
                if row.get("kind") != "straight4" or set(row.get("connections") or []) != {"N", "S"}:
                    errors.append(f"vertical span {ix},{iz} contains non-uniform module")

    expected_h = grid_size * (grid_size - 1)
    expected_v = grid_size * (grid_size - 1)
    if len(hspans) != expected_h:
        errors.append(f"horizontal span group count {len(hspans)} != {expected_h}")
    if len(vspans) != expected_v:
        errors.append(f"vertical span group count {len(vspans)} != {expected_v}")
    return errors


def validate_final_roads(
    parsed: dict[str, Any], foundation_report: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    roads = [
        entity
        for entity in parsed["entities"]
        if legacy.road_kind(entity.get("asset")) is not None
    ]
    try:
        grammar_counts = v4.validate_uniform_grammar(parsed)
    except FpmError as exc:
        errors.append(str(exc))
        grammar_counts = {}

    expected = Counter(
        _expected_signature(row) for row in foundation_report.get("placements", [])
    )
    actual = Counter(_actual_signature(entity) for entity in roads)
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        errors.append(f"final map is missing {sum(missing.values())} expected road placement(s)")
    if unexpected:
        errors.append(f"final map contains {sum(unexpected.values())} unexpected road placement(s)")

    pivots = Counter(
        (_q(entity["position"]["x"]), _q(entity["position"]["z"])) for entity in roads
    )
    duplicate_pivots = sorted(key for key, count in pivots.items() if count > 1)
    if duplicate_pivots:
        errors.append(f"final map contains {len(duplicate_pivots)} duplicate road pivot(s)")

    metrics = {
        "recognized_road_entities": len(roads),
        "expected_road_entities": sum(expected.values()),
        "grammar_counts": grammar_counts,
        "missing_placements": sum(missing.values()),
        "unexpected_placements": sum(unexpected.values()),
        "duplicate_road_pivots": len(duplicate_pivots),
    }
    return errors, metrics


def validate_detail_policy(detail_report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if detail_report.get("detail_policy") != EXPECTED_DETAIL_POLICY:
        errors.append("structural detail report is not using the v7 ownership policy")
    if detail_report.get("cross_module_profile_capture") != "rejected":
        errors.append("structural detail report does not reject cross-module profile capture")
    return errors


def validate_surface_policy(surface_report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if surface_report.get("surface_attachment_policy") != EXPECTED_SURFACE_POLICY:
        errors.append("surface report is not using the v7 role-aware attachment policy")
    if tuple(surface_report.get("approach_junction_kinds") or []) != EXPECTED_APPROACH_JUNCTIONS:
        errors.append("surface report allows an unexpected approach-junction kind")

    for row in surface_report.get("placements") or []:
        role = row.get("role")
        if role in v6.ARROW_ROLES or role in v6.TEXT_ROLES:
            if row.get("road_kind") != "straight4":
                errors.append(
                    f"approach marking {role} attached to {row.get('road_kind')!r}, expected 'straight4'"
                )
    return errors


def validate(
    final_fpm: Path,
    foundation_report_path: Path,
    detail_report_path: Path,
    surface_report_path: Path,
) -> dict[str, Any]:
    foundation_report = json.loads(foundation_report_path.read_text(encoding="utf-8"))
    detail_report = json.loads(detail_report_path.read_text(encoding="utf-8"))
    surface_report = json.loads(surface_report_path.read_text(encoding="utf-8"))

    with FpmArchive(final_fpm) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        parsed = parse_map_ele(archive.read("map.ele"), ent["entries"])

    errors: list[str] = []
    errors.extend(validate_foundation_contract(foundation_report))
    road_errors, metrics = validate_final_roads(parsed, foundation_report)
    errors.extend(road_errors)
    errors.extend(validate_detail_policy(detail_report))
    errors.extend(validate_surface_policy(surface_report))

    return {
        "final_fpm": str(final_fpm.resolve()),
        "foundation_report": str(foundation_report_path.resolve()),
        "detail_report": str(detail_report_path.resolve()),
        "surface_report": str(surface_report_path.resolve()),
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        **metrics,
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 road-system v7 promotion gate")
    print(f"Final FPM: {report['final_fpm']}")
    print(
        f"Roads: {report['recognized_road_entities']} / expected {report['expected_road_entities']}"
    )
    print(f"Missing placements: {report['missing_placements']}")
    print(f"Unexpected placements: {report['unexpected_placements']}")
    print(f"Duplicate road pivots: {report['duplicate_road_pivots']}")
    for kind, count in sorted(report.get("grammar_counts", {}).items()):
        print(f"  {kind:10s} {count}")
    if report["status"] == "pass":
        print("[PASS] Planned node exits are reciprocal and every span uses exactly three Straight 4X modules.")
        print("[PASS] Final recognized roads exactly match the foundation placement contract.")
        print("[PASS] Structural and surface detail reports prove v7 ownership policies were used.")
        print("[PASS] No arrow/regulatory-text placement is attached to a non-Straight-4X road.")
    else:
        for error in report["errors"]:
            print(f"[FAIL] {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_fpm", type=Path)
    parser.add_argument("--foundation-report", type=Path, required=True)
    parser.add_argument("--detail-report", type=Path, required=True)
    parser.add_argument("--surface-report", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate(
            args.final_fpm,
            args.foundation_report,
            args.detail_report,
            args.surface_report,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0 if report["status"] == "pass" else 3
    except (FpmError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FPM ROAD SYSTEM V7 VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
