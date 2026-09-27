#!/usr/bin/env python3
"""Compatibility front-end for District 12 semantic road dressing v9.2.

The production CyberCity exemplar contains the street-lamp mesh but may not contain
an actually placed ``CS_Street_Light_Marker`` record. Dynamic GameGuru MAX light
markers are not safe to synthesize from an unrelated entity record, so this wrapper:

1. prefers an exact marker already present in the generated target or CyberCity;
2. searches same-ELE-version sibling mapbank FPMs for an exact placed marker;
3. if none exists anywhere available, keeps the visible lamp-mesh pass but omits
   dynamic markers instead of aborting the whole city build or fabricating state.

All semantic-road placement behavior is supplied by the v9.2 manual-reference layer.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_semantics_v9_2 as core
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

DYNAMIC_ROLE = "street_dynamic_light"
MODE_DYNAMIC = "lamp-mesh-plus-exact-dynamic-marker"
MODE_LAMP_ONLY = "lamp-mesh-only-no-safe-dynamic-template"


def _load_parsed(path: Path) -> tuple[dict[str, Any], bytes]:
    with FpmArchive(path) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        ele = archive.read("map.ele")
        return parse_map_ele(ele, ent["entries"]), ele


def _candidate_donor_roots(donor_path: Path) -> list[Path]:
    roots = [donor_path.parent]

    documents_mapbank = (
        Path.home() / "Documents" / "GameGuruApps" / "GameGuruMAX" / "Files" / "mapbank"
    )
    roots.append(documents_mapbank)

    program_files_x86 = os.environ.get("PROGRAMFILES(X86)") or os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        roots.append(
            Path(program_files_x86)
            / "Steam"
            / "steamapps"
            / "common"
            / "GameGuru MAX"
            / "Files"
            / "mapbank"
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve()).lower()
        except OSError:
            key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def resolve_dynamic_template(source_path: Path, donor_path: Path) -> fabric.Template | None:
    source_path = source_path.resolve()
    donor_path = donor_path.resolve()
    source_parsed, source_ele = _load_parsed(source_path)
    donor_parsed, donor_ele = _load_parsed(donor_path)

    target_version = int(source_parsed["version"])
    if int(donor_parsed["version"]) != target_version:
        raise FpmError("CyberCity donor ELE version does not match target.")

    template = fabric.source_template_from_parsed(
        DYNAMIC_ROLE, source_parsed, source_ele, source_path, "target-exact"
    )
    if template is not None:
        return template

    template = fabric.source_template_from_parsed(
        DYNAMIC_ROLE, donor_parsed, donor_ele, donor_path, "cybercity-exact"
    )
    if template is not None:
        return template

    harvested = fabric.harvest_donors(
        [DYNAMIC_ROLE],
        _candidate_donor_roots(donor_path),
        target_version,
        {source_path, donor_path},
    )
    return harvested.get(DYNAMIC_ROLE)


def _argument_path(argv: list[str], flag: str) -> Path | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    return Path(argv[index + 1])


def _annotate_report(report_path: Path | None, mode: str, template: fabric.Template | None) -> None:
    if report_path is None or not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["lighting_mode"] = mode
    report["dynamic_light_template_available"] = template is not None
    if template is not None:
        report["dynamic_light_template_source"] = template.source_fpm
        report["dynamic_light_template_source_kind"] = template.source_kind
    else:
        report["dynamic_light_template_source"] = None
        report["dynamic_light_template_source_kind"] = None
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        return core.main(args)

    source_path = Path(args[0])
    donor_path = _argument_path(args, "--donor-fpm")
    report_path = _argument_path(args, "--report-json")
    if donor_path is None:
        return core.main(args)

    try:
        dynamic_template = resolve_dynamic_template(source_path, donor_path)
    except (FpmError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FPM ROAD SEMANTICS V9 COMPAT ERROR: {exc}", file=sys.stderr)
        return 2

    original_template = core._fabric_template
    original_roles = core.FABRIC_ROLES
    original_plan = core.plan_semantic_dressing

    if dynamic_template is not None:
        mode = MODE_DYNAMIC
        print(
            "V9.2 dynamic-light template: exact same-version record from "
            f"{dynamic_template.source_fpm} ({dynamic_template.source_kind})"
        )

        def sibling_aware_template(
            role: str,
            source: Path,
            parsed: dict[str, Any],
            ele_data: bytes,
            donor: Path,
            donor_parsed: dict[str, Any],
            donor_ele: bytes,
        ) -> fabric.Template:
            if role == DYNAMIC_ROLE:
                return dynamic_template
            return original_template(
                role, source, parsed, ele_data, donor, donor_parsed, donor_ele
            )

        core._fabric_template = sibling_aware_template
    else:
        mode = MODE_LAMP_ONLY
        print(
            "[WARN] No exact same-version CS_Street_Light_Marker record was found in "
            "the target, CyberCity, or sibling mapbank FPMs."
        )
        print(
            "[WARN] V9.2 will author visible street-lamp meshes but will not synthesize "
            "unsafe dynamic-light state."
        )
        core.FABRIC_ROLES = tuple(role for role in original_roles if role != DYNAMIC_ROLE)

        def lamp_mesh_plan(parsed: dict[str, Any]) -> list[fabric.Placement]:
            return [
                placement
                for placement in original_plan(parsed)
                if placement.role != DYNAMIC_ROLE
            ]

        core.plan_semantic_dressing = lamp_mesh_plan

    try:
        result = core.main(args)
    finally:
        core._fabric_template = original_template
        core.FABRIC_ROLES = original_roles
        core.plan_semantic_dressing = original_plan

    if result == 0:
        _annotate_report(report_path, mode, dynamic_template)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
