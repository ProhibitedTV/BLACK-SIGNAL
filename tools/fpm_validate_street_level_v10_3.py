#!/usr/bin/env python3
"""Fail-closed promotion gate for District 12 v10.3 street-level film-set dressing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_semantics_v10_3 as street
import fpm_author_street_fabric as fabric
import fpm_validate_road_semantics_v9_compat as base
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


def validate(
    final_fpm: Path,
    foundation_report_path: Path,
    semantic_report_path: Path,
) -> dict[str, Any]:
    semantic_report = json.loads(semantic_report_path.read_text(encoding="utf-8"))
    controlled_assets = {
        role: fabric.basename(fabric.ASSETS[role]["basename"])
        for role in street.STREET_LEVEL_ROLES
    }

    # Core v9.2 intentionally rejects old donor-replayed bollards. V10.3 reintroduces
    # only a small explicitly counted set around the Hero Block. Temporarily remove
    # those controlled basenames from the stale-donor list, then validate them below.
    original_profile = v4.PROFILE_DETAIL_BASENAMES
    v4.PROFILE_DETAIL_BASENAMES = frozenset(
        name for name in original_profile if name not in set(controlled_assets.values())
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

    actual_counts: dict[str, int] = {}
    for entity in parsed["entities"]:
        base_name = fabric.basename(entity.get("asset"))
        actual_counts[base_name] = actual_counts.get(base_name, 0) + 1

    for role, expected in street.EXPECTED_STREET_LEVEL_COUNTS.items():
        reported = int(role_counts.get(role, 0))
        actual = int(actual_counts.get(controlled_assets[role], 0))
        if reported != expected:
            errors.append(
                f"v10.3 controlled {role} count is invalid ({reported}, expected {expected})"
            )
        if actual != reported:
            errors.append(
                f"final FPM count for controlled {role} ({actual}) does not match semantic report ({reported})"
            )

    controlled_placements = [p for p in placements if p.get("role") in street.STREET_LEVEL_ROLES]
    expected_total = sum(street.EXPECTED_STREET_LEVEL_COUNTS.values())
    if len(controlled_placements) != expected_total:
        errors.append(
            f"v10.3 street-level placement report has {len(controlled_placements)} rows, expected {expected_total}"
        )

    seen: set[tuple[str, int, int]] = set()
    for row in controlled_placements:
        role = str(row.get("role"))
        note = str(row.get("note") or "")
        if "v10.3 hero-block controlled" not in note:
            errors.append(f"controlled {role} placement is not tied to the Hero Block policy")
        key = (
            role,
            int(round(float(row.get("x", 0.0)) * 10.0)),
            int(round(float(row.get("z", 0.0)) * 10.0)),
        )
        if key in seen:
            errors.append(f"duplicate v10.3 controlled placement: {role} at {key[1:]}")
        seen.add(key)

    report["street_level_role_counts"] = {
        role: int(role_counts.get(role, 0)) for role in street.STREET_LEVEL_ROLES
    }
    report["errors"] = errors
    report["error_count"] = len(errors)
    report["status"] = "pass" if not errors else "fail"
    return report


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 v10.3 street-level promotion gate")
    print(f"Final FPM: {report['final_fpm']}")
    print(f"Roads: {report['recognized_road_entities']} / expected {report['expected_road_entities']}")
    print(f"Missing placements: {report['missing_placements']}")
    print(f"Unexpected placements: {report['unexpected_placements']}")
    print(f"Duplicate road pivots: {report['duplicate_road_pivots']}")
    for role, count in sorted((report.get("street_level_role_counts") or {}).items()):
        print(f"  {role:24s} {count}")
    if report["status"] == "pass":
        print("[PASS] V10.3 preserved the exact validated road graph and v9.2 semantics.")
        print("[PASS] Hero Block bollards, curb guards, sidewalk lights and utility poles match controlled counts.")
        print("[PASS] Street-level props are explicit Hero Block set dressing, not donor-replayed clutter.")
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
        print(f"FPM V10.3 STREET-LEVEL VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
