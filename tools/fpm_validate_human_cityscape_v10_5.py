#!/usr/bin/env python3
"""Fail-closed promotion gate for the v10.5 human-authored District 12 cityscape."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import fpm_author_human_cityscape_v10_5 as human
import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as roads
import fpm_author_street_fabric as fabric
import fpm_validate_road_semantics_v9_compat as base
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

FOURWAY_NOTE_RE = re.compile(r"four-way #(\d+)")


def _load_final(path: Path) -> dict[str, Any]:
    with FpmArchive(path) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        return parse_map_ele(archive.read("map.ele"), ent["entries"])


def validate(
    final_fpm: Path,
    foundation_report_path: Path,
    semantic_report_path: Path,
) -> dict[str, Any]:
    semantic_report = json.loads(semantic_report_path.read_text(encoding="utf-8"))
    template_sources = semantic_report.get("human_template_sources") or {}
    role_assets: dict[str, str] = {}
    for role in human.HUMAN_ROLES:
        row = template_sources.get(role) or {}
        asset = row.get("asset")
        if asset:
            role_assets[role] = fabric.basename(str(asset))

    original_profile = v4.PROFILE_DETAIL_BASENAMES
    controlled_basenames = set(role_assets.values()) | set(human.REJECTED_OLD_BASENAMES)
    v4.PROFILE_DETAIL_BASENAMES = frozenset(
        name for name in original_profile if name not in controlled_basenames
    )
    try:
        report = base.validate(final_fpm, foundation_report_path, semantic_report_path)
    finally:
        v4.PROFILE_DETAIL_BASENAMES = original_profile

    errors = list(report.get("errors") or [])
    if semantic_report.get("human_cityscape_policy") != human.SEMANTIC_POLICY:
        errors.append("semantic report is not the v10.5 human-corner cityscape policy")

    for role in human.HUMAN_ROLES:
        row = template_sources.get(role)
        if not row:
            errors.append(f"missing exact human-reference template metadata for {role}")
            continue
        if row.get("source_kind") != "human-reference-exact":
            errors.append(f"{role} did not use an exact human-reference ELE record")

    parsed = _load_final(final_fpm)
    fourways = [
        e for e in parsed["entities"] if roads.road_kind(e.get("asset")) == "fourway"
    ]
    expected = human.human_role_counts(len(fourways))
    role_counts = semantic_report.get("role_counts") or {}
    placements = semantic_report.get("placements") or []

    for role, wanted in expected.items():
        got = int(role_counts.get(role, 0))
        if got != wanted:
            errors.append(f"v10.5 {role} count is {got}, expected {wanted}")

    actual_by_asset: Counter[str] = Counter(
        fabric.basename(e.get("asset")) for e in parsed["entities"]
    )
    for role, wanted in expected.items():
        asset = role_assets.get(role)
        if not asset:
            continue
        actual = int(actual_by_asset.get(asset, 0))
        if actual != wanted:
            errors.append(
                f"final FPM has {actual} copies of controlled {asset}, expected {wanted}"
            )

    # The rejected experiment must not leak back into a production build.
    for basename in sorted(human.REJECTED_OLD_BASENAMES):
        actual = int(actual_by_asset.get(basename, 0))
        if actual:
            errors.append(f"rejected v10.3/v10.4 asset survived: {basename} x{actual}")

    controlled = [p for p in placements if p.get("role") in human.HUMAN_ROLES]
    if len(controlled) != sum(expected.values()):
        errors.append(
            f"v10.5 controlled placement report has {len(controlled)} rows, "
            f"expected {sum(expected.values())}"
        )

    seen: set[tuple[str, int, int]] = set()
    by_junction: dict[int, Counter[str]] = defaultdict(Counter)
    for row in controlled:
        role = str(row.get("role"))
        note = str(row.get("note") or "")
        if "v10.5 human-corner" not in note:
            errors.append(f"{role} placement lacks human-corner provenance tag")
        match = FOURWAY_NOTE_RE.search(note)
        if not match:
            errors.append(f"{role} placement does not identify its four-way owner")
        else:
            by_junction[int(match.group(1))][role] += 1
        x = float(row.get("x", 0.0))
        z = float(row.get("z", 0.0))
        key = (role, int(round(x * 10.0)), int(round(z * 10.0)))
        if key in seen:
            errors.append(f"duplicate v10.5 placement: {role} at {key[1:]}")
        seen.add(key)

    per_junction_expected = {
        "human_planter": 4,
        "human_tree": 4,
        "human_trash_can": 4,
        "human_stop_light": 4,
        "human_sidewalk_light": 16,
        "human_bench": human.BENCHES_PER_FOURWAY,
    }
    for junction in fourways:
        record = int(junction["record_index"])
        got = by_junction.get(record, Counter())
        for role, wanted in per_junction_expected.items():
            if int(got.get(role, 0)) != wanted:
                errors.append(
                    f"four-way #{record} has {got.get(role, 0)} {role} placements, expected {wanted}"
                )

    report["human_cityscape_role_counts"] = {
        role: int(role_counts.get(role, 0)) for role in human.HUMAN_ROLES
    }
    report["human_cityscape_fourways"] = len(fourways)
    report["human_cityscape_template_assets"] = role_assets
    report["errors"] = errors
    report["error_count"] = len(errors)
    report["status"] = "pass" if not errors else "fail"
    return report


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 v10.5 human-corner cityscape promotion gate")
    print(f"Final FPM: {report['final_fpm']}")
    print(f"Roads: {report['recognized_road_entities']} / expected {report['expected_road_entities']}")
    print(f"Four-way junctions dressed: {report.get('human_cityscape_fourways', 0)}")
    for role, count in sorted((report.get("human_cityscape_role_counts") or {}).items()):
        print(f"  {role:24s} {count}")
    if report["status"] == "pass":
        print("[PASS] Exact validated road graph and v9.2 road semantics survived.")
        print("[PASS] Human-authored templates were cloned exactly; no generic static carrier was used.")
        print("[PASS] Every four-way received the learned planter/tree/signal/trash/light grammar.")
        print("[PASS] Benches vary deterministically at one corner per junction.")
        print("[PASS] Rejected rails, blocker posts, Joshua trees and v10.3 utility poles are absent.")
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
        print(f"FPM V10.5 HUMAN CITYSCAPE VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
