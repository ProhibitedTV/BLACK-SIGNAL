#!/usr/bin/env python3
"""Fail-closed promotion gate for District 12 v10.4 Hero Block street life."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_semantics_v10_3 as street
import fpm_author_street_fabric as fabric
import fpm_author_streetlife_v10_4 as life
import fpm_validate_road_semantics_v9_compat as base
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


def validate(
    final_fpm: Path,
    foundation_report_path: Path,
    semantic_report_path: Path,
    streetlife_assets_path: Path,
) -> dict[str, Any]:
    semantic_report = json.loads(semantic_report_path.read_text(encoding="utf-8"))
    discovered = life.load_asset_config(streetlife_assets_path)
    original_assets = dict(fabric.ASSETS)
    fabric.ASSETS.update(discovered)
    try:
        all_roles = tuple(street.STREET_LEVEL_ROLES) + life.STREETLIFE_ROLES
        expected_role_counts = {
            **street.EXPECTED_STREET_LEVEL_COUNTS,
            **life.EXPECTED_STREETLIFE_COUNTS,
        }
        role_assets = {
            role: fabric.basename(fabric.ASSETS[role]["basename"])
            for role in all_roles
        }

        original_profile = v4.PROFILE_DETAIL_BASENAMES
        controlled_basenames = set(role_assets.values())
        v4.PROFILE_DETAIL_BASENAMES = frozenset(
            name for name in original_profile if name not in controlled_basenames
        )
        try:
            report = base.validate(final_fpm, foundation_report_path, semantic_report_path)
        finally:
            v4.PROFILE_DETAIL_BASENAMES = original_profile

        errors = list(report.get("errors") or [])
        role_counts = semantic_report.get("role_counts") or {}
        placements = semantic_report.get("placements") or []

        with FpmArchive(final_fpm) as archive:
            ent = parse_map_ent(archive.read("map.ent"))
            parsed = parse_map_ele(archive.read("map.ele"), ent["entries"])

        actual_counts: dict[str, int] = defaultdict(int)
        for entity in parsed["entities"]:
            actual_counts[fabric.basename(entity.get("asset"))] += 1

        for role, expected in expected_role_counts.items():
            reported = int(role_counts.get(role, 0))
            if reported != expected:
                errors.append(f"v10.4 controlled {role} count is invalid ({reported}, expected {expected})")

        # Compare by physical asset basename so shared sidewalk-light meshes are counted
        # correctly across v10.3 sidewalk_light and v10.4 planter_light semantic roles.
        expected_by_asset: dict[str, int] = defaultdict(int)
        for role in all_roles:
            expected_by_asset[role_assets[role]] += int(role_counts.get(role, 0))
        for asset, expected in expected_by_asset.items():
            actual = int(actual_counts.get(asset, 0))
            if actual != expected:
                errors.append(
                    f"final FPM count for controlled asset {asset} ({actual}) does not match semantic roles ({expected})"
                )

        controlled = [p for p in placements if p.get("role") in all_roles]
        expected_total = sum(expected_role_counts.values())
        if len(controlled) != expected_total:
            errors.append(
                f"v10.4 controlled placement report has {len(controlled)} rows, expected {expected_total}"
            )

        seen: set[tuple[str, int, int]] = set()
        life_rows = [p for p in controlled if p.get("role") in life.STREETLIFE_ROLES]
        for row in controlled:
            role = str(row.get("role"))
            note = str(row.get("note") or "")
            required_tag = "v10.4 hero-block" if role in life.STREETLIFE_ROLES else "v10.3 hero-block controlled"
            if required_tag not in note:
                errors.append(f"controlled {role} placement is not tied to the expected Hero Block policy")
            x = float(row.get("x", 0.0))
            z = float(row.get("z", 0.0))
            key = (role, int(round(x * 10.0)), int(round(z * 10.0)))
            if key in seen:
                errors.append(f"duplicate controlled placement: {role} at {key[1:]}")
            seen.add(key)
            if role in life.STREETLIFE_ROLES and abs(x) <= 300.0 and abs(z) <= 300.0:
                errors.append(f"v10.4 {role} entered the measured central asphalt envelope")

        planter_xy = {
            (round(float(p.get("x", 0.0)), 2), round(float(p.get("z", 0.0)), 2))
            for p in life_rows if p.get("role") == "city_planter"
        }
        tree_xy = {
            (round(float(p.get("x", 0.0)), 2), round(float(p.get("z", 0.0)), 2))
            for p in life_rows if p.get("role") == "city_tree"
        }
        if planter_xy != tree_xy or len(planter_xy) != life.EXPECTED_STREETLIFE_COUNTS["city_planter"]:
            errors.append("every v10.4 city tree must be paired 1:1 at a controlled planter pivot")

        report["streetlife_role_counts"] = {
            role: int(role_counts.get(role, 0)) for role in all_roles
        }
        report["streetlife_assets"] = {
            "planter": discovered["city_planter"]["path"],
            "tree": discovered["city_tree"]["path"],
        }
        report["errors"] = errors
        report["error_count"] = len(errors)
        report["status"] = "pass" if not errors else "fail"
        return report
    finally:
        fabric.ASSETS.clear()
        fabric.ASSETS.update(original_assets)


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 v10.4 Hero Block street-life promotion gate")
    print(f"Final FPM: {report['final_fpm']}")
    print(f"Roads: {report['recognized_road_entities']} / expected {report['expected_road_entities']}")
    for role, count in sorted((report.get("streetlife_role_counts") or {}).items()):
        print(f"  {role:24s} {count}")
    if report["status"] == "pass":
        print("[PASS] V10.4 preserved the exact validated road graph and v9.2 road semantics.")
        print("[PASS] V10.3 bollards/rails/lights/poles remain controlled and deterministic.")
        print("[PASS] Eight measured planter/tree pairs and eight planter accent lights stay in pedestrian set-dressing zones.")
    else:
        for error in report["errors"]:
            print(f"[FAIL] {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_fpm", type=Path)
    parser.add_argument("--foundation-report", type=Path, required=True)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--streetlife-assets", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate(
            args.final_fpm,
            args.foundation_report,
            args.semantic_report,
            args.streetlife_assets,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print_report(report)
        return 0 if report["status"] == "pass" else 3
    except (FpmError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FPM V10.4 STREETLIFE VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
