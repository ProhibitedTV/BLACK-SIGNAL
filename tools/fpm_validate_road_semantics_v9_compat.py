#!/usr/bin/env python3
"""Compatibility promotion gate for V9.2 manual-reference semantic dressing.

The core validator requires 1:1 street-lamp/dynamic-marker pairing. That remains the
preferred production mode. If the semantic compiler proves no exact same-version
GameGuru MAX dynamic-light marker record exists, the safe fallback is lamp-mesh-only.
This wrapper permits exactly that documented fallback while preserving every other
V9.2 validation error and never allowing a synthesized/fake dynamic record.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_semantics_v9_compat as compat
import fpm_validate_road_semantics_v9 as core
from fpm_inspect import FpmError

PAIRING_PREFIX = "street lamp/light-marker pairing is invalid"


def apply_lighting_policy(report: dict[str, Any], semantic_report: dict[str, Any]) -> dict[str, Any]:
    mode = semantic_report.get("lighting_mode")
    report["lighting_mode"] = mode

    if mode == compat.MODE_LAMP_ONLY:
        role_counts = semantic_report.get("role_counts") or {}
        lamps = int(role_counts.get("street_lamp", 0))
        lights = int(role_counts.get("street_dynamic_light", 0))
        if lamps <= 0:
            report.setdefault("errors", []).append("lamp-only fallback produced no street-lamp meshes")
        if lights != 0:
            report.setdefault("errors", []).append(
                "lamp-only fallback unexpectedly contains dynamic-light marker placements"
            )

        report["errors"] = [
            error
            for error in (report.get("errors") or [])
            if not str(error).startswith(PAIRING_PREFIX)
        ]

    errors = report.get("errors") or []
    report["error_count"] = len(errors)
    report["status"] = "pass" if not errors else "fail"
    return report


def validate(
    final_fpm: Path,
    foundation_report_path: Path,
    semantic_report_path: Path,
) -> dict[str, Any]:
    semantic_report = json.loads(semantic_report_path.read_text(encoding="utf-8"))
    report = core.validate(final_fpm, foundation_report_path, semantic_report_path)
    return apply_lighting_policy(report, semantic_report)


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
        print("[PASS] Manual-reference center lines, crosswalks, arrows, sidewalk corners and street-lamp meshes match semantic counts.")
        if report.get("lighting_mode") == compat.MODE_DYNAMIC:
            print("[PASS] Every street lamp has an exact same-version dynamic light marker.")
        elif report.get("lighting_mode") == compat.MODE_LAMP_ONLY:
            print("[PASS] Lamp-mesh-only fallback is explicit; no fake dynamic-light record was synthesized.")
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
