#!/usr/bin/env python3
"""V9.1 visual tuning for District 12 semantic road dressing.

V9 established safe target-road semantics. V9.1 keeps that topology and safety model
but tunes the visible authored dressing against in-engine screenshots:

* two centered double-yellow decals per Straight 4X module so corridor markings read
  continuously instead of as isolated short chunks;
* one lamp every four Straight 4X modules instead of every other module;
* lamps pushed farther outside the pavement edge;
* 4-way crosswalks pulled inward onto the paved intersection footprint;
* arrow semantics, T-junction omission, and dynamic-light safety remain unchanged.

This module wraps the proven v9 writer rather than duplicating its raw FPM compiler.
"""
from __future__ import annotations

from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as legacy
import fpm_author_road_semantics_v9 as core
import fpm_author_street_fabric as fabric

SEMANTIC_POLICY = "target-road-graph-semantic-dressing-v9.1"
ROAD_SURFACE_Y = core.ROAD_SURFACE_Y
CENTER_LOCAL_Z_OFFSETS = (-100.0, 100.0)
CENTER_TREATMENTS_PER_STRAIGHT = len(CENTER_LOCAL_Z_OFFSETS)
LAMP_EDGE_X = 390.0
LAMP_LIGHT_Y = core.LAMP_LIGHT_Y
LAMP_STRIDE = 4
CROSSWALK_EDGE = 200.0
ARROW_LANE_X = core.ARROW_LANE_X
ARROW_LOCAL_Z = core.ARROW_LOCAL_Z
FABRIC_ROLES = core.FABRIC_ROLES
ARROW_ROLE = core.ARROW_ROLE
_fabric_template = core._fabric_template


def plan_semantic_dressing(parsed: dict[str, Any]) -> list[fabric.Placement]:
    roads = [
        entity
        for entity in parsed["entities"]
        if legacy.road_kind(entity.get("asset")) in v4.ALLOWED_ROAD_KINDS
    ]
    straights = sorted(
        [entity for entity in roads if legacy.road_kind(entity.get("asset")) == "straight4"],
        key=lambda e: (
            round(float(e["position"]["x"]), 3),
            round(float(e["position"]["z"]), 3),
            int(e["record_index"]),
        ),
    )
    fourways = [entity for entity in roads if legacy.road_kind(entity.get("asset")) == "fourway"]
    out: list[fabric.Placement] = []

    for ordinal, road in enumerate(straights):
        # Straight 4X centers are 400 units apart in the authored network. Two
        # symmetric center decals per module fill the visual gap while staying
        # completely inside the module rather than bleeding through junctions.
        for local_z in CENTER_LOCAL_Z_OFFSETS:
            out.append(
                core._placement(
                    "road_center_yellow",
                    road,
                    0.0,
                    local_z,
                    ROAD_SURFACE_Y,
                    90.0,
                    f"v9.1 continuous corridor marking for Straight 4X #{road['record_index']}",
                )
            )

        # The v9 every-other-module rhythm produced a forest of poles and heavily
        # overlapping light pools in engine. Quarter the corridor density, alternate
        # curb side, and move the mesh farther outside the asphalt.
        if ordinal % LAMP_STRIDE == 0:
            lamp_ordinal = ordinal // LAMP_STRIDE
            side = -1.0 if lamp_ordinal % 2 else 1.0
            lamp = core._placement(
                "street_lamp",
                road,
                side * LAMP_EDGE_X,
                0.0,
                0.0,
                180.0 if side < 0.0 else 0.0,
                f"v9.1 sparse curb lamp beside Straight 4X #{road['record_index']}",
            )
            out.append(lamp)
            out.append(
                fabric.Placement(
                    role="street_dynamic_light",
                    x=lamp.x,
                    y=lamp.y + LAMP_LIGHT_Y,
                    z=lamp.z,
                    ry=None,
                    note=f"v9.1 light marker paired with lamp beside Straight 4X #{road['record_index']}",
                )
            )

        junction, local_z = core._nearest_fourway(road, fourways)
        if junction is not None and abs(local_z) > 120.0:
            direction = 1.0 if local_z > 0.0 else -1.0
            out.append(
                core._placement(
                    ARROW_ROLE,
                    road,
                    ARROW_LANE_X * direction,
                    ARROW_LOCAL_Z * direction,
                    ROAD_SURFACE_Y + 0.15,
                    90.0 + (0.0 if direction > 0.0 else 180.0),
                    f"v9.1 straight-ahead approach arrow to 4-way #{junction['record_index']}",
                )
            )

    for junction in sorted(fourways, key=lambda e: int(e["record_index"])):
        # Keep exactly four crossings, but pull them inward from the old 260-unit
        # edge so the decal remains visibly on pavement instead of touching terrain.
        for yaw_offset, lx, lz in (
            (0.0, 0.0, CROSSWALK_EDGE),
            (180.0, 0.0, -CROSSWALK_EDGE),
            (90.0, CROSSWALK_EDGE, 0.0),
            (270.0, -CROSSWALK_EDGE, 0.0),
        ):
            out.append(
                core._placement(
                    "crosswalk",
                    junction,
                    lx,
                    lz,
                    ROAD_SURFACE_Y,
                    yaw_offset,
                    f"v9.1 four-way crosswalk at junction #{junction['record_index']}",
                )
            )

    return out


def main(argv: list[str] | None = None) -> int:
    # The compatibility front-end may temporarily replace these wrapper globals
    # (for sibling-map dynamic markers or lamp-only fallback). Propagate the active
    # values into the proven v9 compiler for exactly this invocation, then restore.
    original_policy = core.SEMANTIC_POLICY
    original_roles = core.FABRIC_ROLES
    original_template = core._fabric_template
    original_plan = core.plan_semantic_dressing
    try:
        core.SEMANTIC_POLICY = SEMANTIC_POLICY
        core.FABRIC_ROLES = FABRIC_ROLES
        core._fabric_template = _fabric_template
        core.plan_semantic_dressing = plan_semantic_dressing
        return core.main(argv)
    finally:
        core.SEMANTIC_POLICY = original_policy
        core.FABRIC_ROLES = original_roles
        core._fabric_template = original_template
        core.plan_semantic_dressing = original_plan


if __name__ == "__main__":
    raise SystemExit(main())
