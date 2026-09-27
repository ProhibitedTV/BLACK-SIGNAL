#!/usr/bin/env python3
"""V10.3 film-set street-level dressing for District 12's central Hero Block.

This wraps the proven v9.2 road-semantic compiler rather than replacing it.  Roads,
markings, sidewalk corners, lamps and exact dynamic-light handling remain owned by the
existing compiler.  V10.3 adds a small deterministic set of ordinary static street props
only around the central Hero Block used for filming:

* paired crosswalk bollards just outside the measured 4-way asphalt envelope;
* curb guards/rails on the eight central-facing block edges;
* low sidewalk lights farther down those same pedestrian corridors;
* four sparse utility poles near the outer ends of the Hero Block streets.

The pass deliberately avoids random scattering and keeps entries/crosswalk openings clear.
All added assets are normal static Cyberpunk Streets Booster Pack props.  Exact donor ELE
records are preferred; installed-but-unplaced static props may use the established generic
static carrier.  Dynamic light markers keep the stricter v9 compatibility policy.
"""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v9_2 as base
import fpm_author_road_semantics_v9_compat as compat
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmError

STREET_LEVEL_ROLES = (
    "bollard_stop",
    "curb_guard",
    "sidewalk_light",
    "utility_pole",
)

EXPECTED_STREET_LEVEL_COUNTS = {
    "bollard_stop": 8,
    "curb_guard": 8,
    "sidewalk_light": 8,
    "utility_pole": 4,
}

# Central 4-way is measured as 600 x 600.  These placements live outside the +/-300
# asphalt envelope and inside the Hero Block sidewalk/set-dressing zone.
BOLLARD_LAYOUT = (
    (-340.0, 260.0, 0.0),
    (-260.0, 340.0, 0.0),
    (260.0, 340.0, 0.0),
    (340.0, 260.0, 0.0),
    (340.0, -260.0, 0.0),
    (260.0, -340.0, 0.0),
    (-260.0, -340.0, 0.0),
    (-340.0, -260.0, 0.0),
)

# One rail on each central-facing side of the four Hero Block parcels.  The 650-unit
# longitudinal location keeps the rails away from the ground-floor entry bays at ~900.
GUARD_LAYOUT = (
    (650.0, 270.0, 90.0),
    (270.0, 650.0, 0.0),
    (-650.0, 270.0, 90.0),
    (-270.0, 650.0, 0.0),
    (650.0, -270.0, 90.0),
    (270.0, -650.0, 0.0),
    (-650.0, -270.0, 90.0),
    (-270.0, -650.0, 0.0),
)

# Low sidewalk fixtures provide eye-level depth without repeating the much larger street
# lamps.  Keep them farther down-block than the rails and outside the curb opening.
SIDEWALK_LIGHT_LAYOUT = (
    (1100.0, 330.0, 180.0),
    (330.0, 1100.0, 270.0),
    (-1100.0, 330.0, 180.0),
    (-330.0, 1100.0, 90.0),
    (1100.0, -330.0, 0.0),
    (330.0, -1100.0, 270.0),
    (-1100.0, -330.0, 0.0),
    (-330.0, -1100.0, 90.0),
)

# Sparse, alternating utility poles at the outer end of each filming corridor.  Four is
# enough to establish vertical street infrastructure without recreating the old pole forest.
UTILITY_POLE_LAYOUT = (
    (1250.0, 360.0, 180.0),
    (-360.0, 1250.0, 90.0),
    (-1250.0, -360.0, 0.0),
    (360.0, -1250.0, 270.0),
)


def _central_fourway(parsed: dict[str, Any]) -> dict[str, Any]:
    recognized = [
        e for e in parsed.get("entities", []) if roads.road_kind(e.get("asset")) is not None
    ]
    fourways = [e for e in recognized if roads.road_kind(e.get("asset")) == "fourway"]
    if not recognized or not fourways:
        raise FpmError("V10.3 street-level dressing requires a recognized central 4-way.")
    cx = statistics.median(float(e["position"]["x"]) for e in recognized)
    cz = statistics.median(float(e["position"]["z"]) for e in recognized)
    return min(
        fourways,
        key=lambda e: (
            (float(e["position"]["x"]) - cx) ** 2
            + (float(e["position"]["z"]) - cz) ** 2,
            int(e["record_index"]),
        ),
    )


def _hero_block_dressing(parsed: dict[str, Any]) -> list[fabric.Placement]:
    junction = _central_fourway(parsed)
    out: list[fabric.Placement] = []

    def add_layout(role: str, layout: tuple[tuple[float, float, float], ...]) -> None:
        for lx, lz, yaw in layout:
            out.append(
                base.core._placement(
                    role,
                    junction,
                    lx,
                    lz,
                    0.0,
                    yaw,
                    f"v10.3 hero-block controlled {role} around central 4-way #{junction['record_index']}",
                )
            )

    add_layout("bollard_stop", BOLLARD_LAYOUT)
    add_layout("curb_guard", GUARD_LAYOUT)
    add_layout("sidewalk_light", SIDEWALK_LIGHT_LAYOUT)
    add_layout("utility_pole", UTILITY_POLE_LAYOUT)
    return out


def _static_street_template(
    role: str,
    source_path: Path,
    parsed: dict[str, Any],
    ele_data: bytes,
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> fabric.Template:
    template = fabric.source_template_from_parsed(
        role, parsed, ele_data, source_path, "target-exact"
    )
    if template is None:
        template = fabric.source_template_from_parsed(
            role, donor_parsed, donor_ele, donor_path, "cybercity-exact"
        )
    if template is not None:
        return template

    if role not in STREET_LEVEL_ROLES:
        raise FpmError(f"No v10.3 static fallback is defined for role: {role}")
    spec = fabric.ASSETS[role]
    carrier = fabric.find_generic_static_template(donor_parsed, donor_ele, donor_path)
    return fabric.Template(
        role=role,
        asset_path=str(spec["path"]),
        parsed=carrier.parsed,
        raw_record=carrier.raw_record,
        source_fpm=carrier.source_fpm,
        source_kind="generic-static-v10.3-street-level",
    )


def main(argv: list[str] | None = None) -> int:
    original_roles = base.FABRIC_ROLES
    original_template = base._fabric_template
    original_plan = base.plan_semantic_dressing
    original_strip = base.STRIP_BASENAMES

    controlled_basenames = {
        fabric.basename(fabric.ASSETS[role]["basename"]) for role in STREET_LEVEL_ROLES
    }

    def street_level_template(
        role: str,
        source_path: Path,
        parsed: dict[str, Any],
        ele_data: bytes,
        donor_path: Path,
        donor_parsed: dict[str, Any],
        donor_ele: bytes,
    ) -> fabric.Template:
        if role in STREET_LEVEL_ROLES:
            return _static_street_template(
                role,
                source_path,
                parsed,
                ele_data,
                donor_path,
                donor_parsed,
                donor_ele,
            )
        return original_template(
            role,
            source_path,
            parsed,
            ele_data,
            donor_path,
            donor_parsed,
            donor_ele,
        )

    def street_level_plan(parsed: dict[str, Any]) -> list[fabric.Placement]:
        return list(original_plan(parsed)) + _hero_block_dressing(parsed)

    try:
        base.FABRIC_ROLES = tuple(original_roles) + STREET_LEVEL_ROLES
        base._fabric_template = street_level_template
        base.plan_semantic_dressing = street_level_plan
        base.STRIP_BASENAMES = frozenset(set(original_strip) | controlled_basenames)
        return compat.main(argv)
    finally:
        base.FABRIC_ROLES = original_roles
        base._fabric_template = original_template
        base.plan_semantic_dressing = original_plan
        base.STRIP_BASENAMES = original_strip


if __name__ == "__main__":
    raise SystemExit(main())
