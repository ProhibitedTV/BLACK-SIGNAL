#!/usr/bin/env python3
"""V10.5 District 12 citywide street dressing learned from the human-authored corner.

The v10.4 experiment proved that asset-name discovery is not art direction.  V10.5 uses
only exact GameGuru-authored entity records from the captured human reference FPM and
propagates the observed corner grammar across every validated interior four-way:

* one planter + Broad Tree at each corner;
* one traffic signal and trash can at each corner;
* four low curb lights per corner, using the exact hand-authored 100-ish unit rhythm;
* one bench per junction, rotating which corner receives it to avoid prefab repetition.

The rejected v10.3/v10.4 rails, blocker-post bollards, Joshua trees, guessed planter lights
and utility-pole dressing are not authored by this pass.  Road geometry, markings,
crosswalks, sidewalk corners and the proven sparse street-lamp/dynamic-light cadence remain
owned by v9.2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v9_2 as base
import fpm_author_road_semantics_v9_compat as compat
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent

SEMANTIC_POLICY = "target-road-graph-human-corner-cityscape-v10.5"

HUMAN_ROLES = (
    "human_planter",
    "human_tree",
    "human_trash_can",
    "human_stop_light",
    "human_sidewalk_light",
    "human_bench",
)

ROLE_BASENAMES = {
    "human_planter": "CS_Planter_01.fpe",
    "human_tree": "Broad Tree.fpe",
    "human_trash_can": "CS_Trash_Can.fpe",
    "human_stop_light": "CS_Stop_Light.fpe",
    "human_sidewalk_light": "CS_Sidewalk_Light.fpe",
    "human_bench": "CS_Bench.fpe",
}

# Exact NW-corner transforms measured from commit bc9a0f9's captured GameGuru edit,
# expressed in junction-local coordinates relative to the central four-way.
# (x, y, z, yaw)
CANONICAL_CORNER = {
    "human_planter": (-350.0, 0.0, 350.0, 90.0),
    "human_tree": (-350.0, 20.0, 350.0, 0.0),
    "human_trash_can": (-245.0, 10.0, 245.0, 0.0),
    "human_stop_light": (-220.0, 10.0, 290.0, -90.0),
    "human_bench": (-405.0, 10.0, 555.0, 90.0),
}
CANONICAL_LIGHTS = (
    (-215.0, 10.0, 500.0, 0.0),
    (-215.0, 10.0, 600.0, 0.0),
    (-215.0, 10.0, 700.0, 0.0),
    (-215.0, 10.0, 795.0, 0.0),
)
CORNER_ROTATIONS = (0.0, 90.0, 180.0, 270.0)

# One bench per four-way instead of stamping four identical benches at every junction.
# The selected corner rotates by stable junction order so adjacent intersections vary.
BENCHES_PER_FOURWAY = 1

REJECTED_OLD_BASENAMES = frozenset(
    {
        "cs_sidewalk_guard.fpe",
        "cs_street_crosswalk_metal_blocker_post.fpe",
        "joshua tree - set a.fpe",
        "cs_street_electrical_pole_01.fpe",
    }
)


def _pop_option(args: list[str], flag: str) -> tuple[list[str], str | None]:
    cleaned = list(args)
    try:
        index = cleaned.index(flag)
    except ValueError:
        return cleaned, None
    if index + 1 >= len(cleaned):
        raise FpmError(f"{flag} requires a path")
    value = cleaned[index + 1]
    del cleaned[index:index + 2]
    return cleaned, value


def _load_reference(path: Path) -> tuple[dict[str, Any], bytes]:
    with FpmArchive(path) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        ele = archive.read("map.ele")
        return parse_map_ele(ele, ent["entries"]), ele


def _exact_reference_templates(path: Path) -> dict[str, fabric.Template]:
    parsed, ele = _load_reference(path)
    templates: dict[str, fabric.Template] = {}
    for role, wanted in ROLE_BASENAMES.items():
        candidates = [
            entity
            for entity in parsed["entities"]
            if fabric.basename(entity.get("asset")) == fabric.basename(wanted)
        ]
        if not candidates:
            raise FpmError(f"human reference is missing exact placed asset: {wanted}")
        chosen = None
        rejection_reasons: list[str] = []
        for entity in candidates:
            ok, reason = fabric.safe_template_entity(entity, False)
            if ok:
                chosen = entity
                break
            rejection_reasons.append(reason)
        if chosen is None:
            raise FpmError(
                f"human reference has no safe exact template for {wanted}: "
                + "; ".join(rejection_reasons)
            )
        start = int(chosen["record_start_offset"])
        end = int(chosen["record_end_offset"])
        templates[role] = fabric.Template(
            role=role,
            asset_path=str(chosen["asset"]),
            parsed=chosen,
            raw_record=ele[start:end],
            source_fpm=str(path.resolve()),
            source_kind="human-reference-exact",
        )
    return templates


def _rotated(local_x: float, local_z: float, rotation: float) -> tuple[float, float]:
    return fabric.rotate_local(local_x, local_z, rotation)


def _placement_from_corner(
    role: str,
    junction: dict[str, Any],
    corner_rotation: float,
    row: tuple[float, float, float, float],
    note_suffix: str,
    *,
    extra_yaw: float = 0.0,
) -> fabric.Placement:
    lx, y, lz, yaw = row
    rx, rz = _rotated(lx, lz, corner_rotation)
    return base.core._placement(
        role,
        junction,
        rx,
        rz,
        y,
        yaw + corner_rotation + extra_yaw,
        f"v10.5 human-corner {note_suffix} at four-way #{junction['record_index']}",
    )


def human_role_counts(fourway_count: int) -> dict[str, int]:
    return {
        "human_planter": fourway_count * 4,
        "human_tree": fourway_count * 4,
        "human_trash_can": fourway_count * 4,
        "human_stop_light": fourway_count * 4,
        "human_sidewalk_light": fourway_count * 16,
        "human_bench": fourway_count * BENCHES_PER_FOURWAY,
    }


def plan_human_cityscape(parsed: dict[str, Any]) -> list[fabric.Placement]:
    fourways = sorted(
        [
            entity
            for entity in parsed.get("entities", [])
            if roads.road_kind(entity.get("asset")) == "fourway"
        ],
        key=lambda e: (
            round(float(e["position"]["x"]), 3),
            round(float(e["position"]["z"]), 3),
            int(e["record_index"]),
        ),
    )
    out: list[fabric.Placement] = []

    for junction_ordinal, junction in enumerate(fourways):
        bench_corner = junction_ordinal % len(CORNER_ROTATIONS)
        for corner_index, rotation in enumerate(CORNER_ROTATIONS):
            out.append(
                _placement_from_corner(
                    "human_planter", junction, rotation, CANONICAL_CORNER["human_planter"],
                    f"planter corner={corner_index}",
                )
            )
            # Quarter-turn variation keeps the same measured tree pivot while preventing
            # every Broad Tree silhouette from facing exactly the same way block after block.
            tree_extra_yaw = ((junction_ordinal + corner_index) % 4) * 90.0
            out.append(
                _placement_from_corner(
                    "human_tree", junction, rotation, CANONICAL_CORNER["human_tree"],
                    f"Broad Tree corner={corner_index}", extra_yaw=tree_extra_yaw,
                )
            )
            out.append(
                _placement_from_corner(
                    "human_trash_can", junction, rotation, CANONICAL_CORNER["human_trash_can"],
                    f"trash can corner={corner_index}",
                )
            )
            out.append(
                _placement_from_corner(
                    "human_stop_light", junction, rotation, CANONICAL_CORNER["human_stop_light"],
                    f"traffic signal corner={corner_index}",
                )
            )
            for light_index, light in enumerate(CANONICAL_LIGHTS):
                out.append(
                    _placement_from_corner(
                        "human_sidewalk_light", junction, rotation, light,
                        f"curb-light corner={corner_index} run={light_index}",
                    )
                )
            if corner_index == bench_corner:
                out.append(
                    _placement_from_corner(
                        "human_bench", junction, rotation, CANONICAL_CORNER["human_bench"],
                        f"bench corner={corner_index}",
                    )
                )

    return out


def _annotate_report(
    report_path: Path | None,
    human_reference: Path,
    templates: dict[str, fabric.Template],
) -> None:
    if report_path is None or not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["human_cityscape_policy"] = SEMANTIC_POLICY
    report["human_reference"] = str(human_reference.resolve())
    report["human_template_sources"] = {
        role: {
            "asset": template.asset_path,
            "source_kind": template.source_kind,
            "source_fpm": template.source_fpm,
        }
        for role, template in sorted(templates.items())
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _argument_path(args: list[str], flag: str) -> Path | None:
    try:
        index = args.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(args):
        return None
    return Path(args[index + 1])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        args, reference_value = _pop_option(args, "--human-reference")
        if reference_value is None:
            raise FpmError("v10.5 requires --human-reference captured from the GameGuru editor")
        reference_path = Path(reference_value)
        templates = _exact_reference_templates(reference_path)
    except (FpmError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FPM HUMAN CITYSCAPE V10.5 ERROR: {exc}", file=sys.stderr)
        return 2

    report_path = _argument_path(args, "--report-json")
    original_assets = dict(fabric.ASSETS)
    original_policy = base.SEMANTIC_POLICY
    original_roles = base.FABRIC_ROLES
    original_template = base._fabric_template
    original_plan = base.plan_semantic_dressing
    original_strip = base.core.STRIP_BASENAMES

    # Register exact paths from the human reference, not guessed pack paths.
    for role, template in templates.items():
        fabric.ASSETS[role] = {
            "basename": fabric.basename(template.asset_path),
            "path": template.asset_path,
            "dynamic": False,
        }

    human_basenames = {
        fabric.basename(template.asset_path) for template in templates.values()
    }

    def human_template(
        role: str,
        source_path: Path,
        parsed: dict[str, Any],
        ele_data: bytes,
        donor_path: Path,
        donor_parsed: dict[str, Any],
        donor_ele: bytes,
    ) -> fabric.Template:
        if role in HUMAN_ROLES:
            # No generic carrier fallback: this is the texture/material correctness rule.
            return templates[role]
        return original_template(
            role, source_path, parsed, ele_data, donor_path, donor_parsed, donor_ele
        )

    def combined_plan(parsed: dict[str, Any]) -> list[fabric.Placement]:
        return list(original_plan(parsed)) + plan_human_cityscape(parsed)

    try:
        base.SEMANTIC_POLICY = SEMANTIC_POLICY
        base.FABRIC_ROLES = tuple(original_roles) + HUMAN_ROLES
        base._fabric_template = human_template
        base.plan_semantic_dressing = combined_plan
        base.core.STRIP_BASENAMES = frozenset(
            set(original_strip) | human_basenames | set(REJECTED_OLD_BASENAMES)
        )
        result = compat.main(args)
    finally:
        base.SEMANTIC_POLICY = original_policy
        base.FABRIC_ROLES = original_roles
        base._fabric_template = original_template
        base.plan_semantic_dressing = original_plan
        base.core.STRIP_BASENAMES = original_strip
        fabric.ASSETS.clear()
        fabric.ASSETS.update(original_assets)

    if result == 0:
        _annotate_report(report_path, reference_path, templates)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
