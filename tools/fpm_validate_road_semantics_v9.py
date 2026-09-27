#!/usr/bin/env python3
"""Fail-closed validation for District 12 V9.2 manual-reference road dressing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_semantics_v9_2 as semantics
import fpm_author_road_surface_v5 as v5
import fpm_author_street_fabric as fabric
import fpm_validate_road_system_v7 as base
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


def validate(final_fpm: Path, foundation_report_path: Path, semantic_report_path: Path) -> dict[str, Any]:
    foundation_report = json.loads(foundation_report_path.read_text(encoding="utf-8"))
    semantic_report = json.loads(semantic_report_path.read_text(encoding="utf-8"))
    with FpmArchive(final_fpm) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        parsed = parse_map_ele(archive.read("map.ele"), ent["entries"])

    errors: list[str] = []
    errors.extend(base.validate_foundation_contract(foundation_report))
    road_errors, metrics = base.validate_final_roads(parsed, foundation_report)
    errors.extend(road_errors)

    if semantic_report.get("semantic_policy") != semantics.SEMANTIC_POLICY:
        errors.append("semantic report is not using the v9.2 manual-reference target-road policy")

    road_counts = semantic_report.get("road_counts") or {}
    role_counts = semantic_report.get("role_counts") or {}
    straight_count = int(road_counts.get("straight4", 0))
    fourway_count = int(road_counts.get("fourway", 0))
    expected_centers = straight_count * semantics.CENTER_TREATMENTS_PER_STRAIGHT
    expected_crosswalks = fourway_count * 4
    expected_corners = fourway_count * semantics.SIDEWALK_CORNERS_PER_FOURWAY
    expected_lamps = (straight_count + semantics.LAMP_STRIDE - 1) // semantics.LAMP_STRIDE

    if int(role_counts.get("road_center_yellow", 0)) != expected_centers:
        errors.append(
            "v9.2 did not author exactly two manual-reference center treatments per Straight 4X module"
        )
    if int(role_counts.get("crosswalk", 0)) != expected_crosswalks:
        errors.append("v9.2 did not author exactly four pivot-corrected crosswalks per 4-way junction")
    if int(role_counts.get(semantics.SIDEWALK_CORNER_ROLE, 0)) != expected_corners:
        errors.append(
            "v9.2 did not author exactly four manual-reference sidewalk corners per 4-way junction"
        )

    lamps = int(role_counts.get("street_lamp", 0))
    lights = int(role_counts.get("street_dynamic_light", 0))
    if lamps != expected_lamps:
        errors.append(
            f"v9.2 sparse lamp cadence is invalid ({lamps} lamps, expected {expected_lamps})"
        )
    if lamps <= 0 or lamps != lights:
        errors.append(f"street lamp/light-marker pairing is invalid ({lamps} lamps, {lights} markers)")

    arrows = int(role_counts.get(semantics.ARROW_ROLE, 0))
    if arrows <= 0:
        errors.append("v9.2 produced no validated straight-ahead 4-way approach arrows")

    for row in semantic_report.get("placements") or []:
        role = row.get("role")
        note = str(row.get("note") or "")
        if role == semantics.ARROW_ROLE and "4-way" not in note:
            errors.append("an arrow placement is not explicitly tied to a 4-way approach")
        if role == semantics.SIDEWALK_CORNER_ROLE and "4-way" not in note:
            errors.append("a sidewalk-corner placement is not explicitly tied to a 4-way junction")

    actual_counts: dict[str, int] = {}
    for entity in parsed["entities"]:
        base_name = fabric.basename(entity.get("asset"))
        actual_counts[base_name] = actual_counts.get(base_name, 0) + 1

    expected_assets = {
        "road_center_yellow": fabric.basename(fabric.ASSETS["road_center_yellow"]["basename"]),
        "crosswalk": fabric.basename(fabric.ASSETS["crosswalk"]["basename"]),
        "street_lamp": fabric.basename(fabric.ASSETS["street_lamp"]["basename"]),
        "street_dynamic_light": fabric.basename(fabric.ASSETS["street_dynamic_light"]["basename"]),
        semantics.SIDEWALK_CORNER_ROLE: semantics.SIDEWALK_CORNER_STRIP_BASENAME,
        semantics.ARROW_ROLE: fabric.basename(v5.SURFACE_ASSETS[semantics.ARROW_ROLE]["basename"]),
    }
    for role, asset in expected_assets.items():
        if actual_counts.get(asset, 0) != int(role_counts.get(role, 0)):
            errors.append(
                f"final FPM count for {role} ({actual_counts.get(asset, 0)}) does not match semantic report ({role_counts.get(role, 0)})"
            )

    allowed_profile_assets = {
        expected_assets["road_center_yellow"],
        expected_assets["crosswalk"],
        expected_assets["street_lamp"],
        expected_assets["street_dynamic_light"],
    }
    stale_profile = [
        name for name in v4.PROFILE_DETAIL_BASENAMES
        if name not in allowed_profile_assets and actual_counts.get(name, 0) > 0
    ]
    if stale_profile:
        errors.append("stale donor-replayed structural details remain: " + ", ".join(sorted(stale_profile)))

    allowed_surface = {expected_assets[semantics.ARROW_ROLE]}
    stale_surface = [
        name for name in v5.OWNED_BASENAMES
        if name not in allowed_surface and actual_counts.get(name, 0) > 0
    ]
    if stale_surface:
        errors.append("stale donor/guessed surface decals remain: " + ", ".join(sorted(stale_surface)))

    return {
        "final_fpm": str(final_fpm.resolve()),
        "foundation_report": str(foundation_report_path.resolve()),
        "semantic_report": str(semantic_report_path.resolve()),
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "semantic_role_counts": role_counts,
        **metrics,
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 semantic road-system v9.2 promotion gate")
    print(f"Final FPM: {report['final_fpm']}")
    print(f"Roads: {report['recognized_road_entities']} / expected {report['expected_road_entities']}")
    print(f"Missing placements: {report['missing_placements']}")
    print(f"Unexpected placements: {report['unexpected_placements']}")
    print(f"Duplicate road pivots: {report['duplicate_road_pivots']}")
    for role, count in sorted((report.get("semantic_role_counts") or {}).items()):
        print(f"  {role:24s} {count}")
    if report["status"] == "pass":
        print("[PASS] V9.2 preserved the exact validated road graph.")
        print("[PASS] Manual-reference center lines, crosswalk pivots, arrows and sidewalk corners match semantic counts.")
        print("[PASS] Sparse lamps/light markers remain on the validated v9.1 cadence.")
        print("[PASS] No stale turn arrows/text/wear decals or donor bollard detail survived cleanup.")
    else:
        for error in report["errors"]:
            print(f"[FAIL] {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_fpm", type=Path)
    parser.add_argument("--foundation-report", type=Path, required=True)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate(args.final_fpm, args.foundation_report, args.semantic_report)
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0 if report["status"] == "pass" else 3
    except (FpmError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FPM ROAD SEMANTICS V9.2 VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
