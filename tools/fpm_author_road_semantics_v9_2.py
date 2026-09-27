#!/usr/bin/env python3
"""V9.2 District 12 dressing learned from the manually corrected intersection.

The canonical GameGuru MAX FPM now contains one hand-corrected intersection. A
read-only transform analysis found four useful single-instance corrections amid the
repeated v9.1 pattern. V9.2 promotes those corrections into symmetric road-local
rules instead of continuing to guess from screenshots:

* double-center-line decals keep the proven +/-100 local cadence but align to the
  road axis (0-degree local yaw) instead of the old quarter-turn;
* straight arrows use +/-100 lane offset, +/-180 approach setback, and point along
  traffic (0/180 local yaw);
* the crosswalk decal's 95-unit lateral pivot bias is compensated on all four sides
  of each 4-way junction;
* the manually placed CS_Sidewalk_Corner1 establishes a four-corner 300 x 300
  intersection sidewalk grammar;
* v9.1 lamp spacing/edge offset and dynamic-light safety remain unchanged.

The raw FPM compiler remains the proven v9 writer. This module supplies only the
reference-derived placement plan and the safe static sidewalk-corner template.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fpm_author_road_details_v4 as v4
import fpm_author_road_network_v2 as legacy
import fpm_author_road_semantics_v9 as core
import fpm_author_road_semantics_v9_1 as v91
import fpm_author_street_fabric as fabric

SEMANTIC_POLICY = "target-road-graph-semantic-dressing-v9.2-manual-reference"
ROAD_SURFACE_Y = core.ROAD_SURFACE_Y
CENTER_LOCAL_Z_OFFSETS = v91.CENTER_LOCAL_Z_OFFSETS
CENTER_TREATMENTS_PER_STRAIGHT = len(CENTER_LOCAL_Z_OFFSETS)
CENTER_YAW_OFFSET = 0.0

LAMP_EDGE_X = v91.LAMP_EDGE_X
LAMP_LIGHT_Y = v91.LAMP_LIGHT_Y
LAMP_STRIDE = v91.LAMP_STRIDE

CROSSWALK_EDGE = v91.CROSSWALK_EDGE
CROSSWALK_PIVOT_X = 95.0
ARROW_LANE_X = 100.0
ARROW_LOCAL_Z = 180.0

SIDEWALK_CORNER_ROLE = "sidewalk_corner"
SIDEWALK_CORNER_BASENAME = "CS_Sidewalk_Corner1.fpe"
SIDEWALK_CORNER_PATH = (
    r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Sidewalks\CS_Sidewalk_Corner1.fpe"
)
SIDEWALK_CORNER_EDGE = 300.0
SIDEWALK_CORNER_Y = -0.1
SIDEWALK_CORNERS_PER_FOURWAY = 4

FABRIC_ROLES = tuple(core.FABRIC_ROLES) + (SIDEWALK_CORNER_ROLE,)
ARROW_ROLE = core.ARROW_ROLE
ORIGINAL_FABRIC_TEMPLATE = core._fabric_template
SIDEWALK_CORNER_STRIP_BASENAME = fabric.basename(SIDEWALK_CORNER_BASENAME)


def _exact_sidewalk_corner_template(
    parsed: dict[str, Any],
    ele_data: bytes,
    source_fpm: Path,
    source_kind: str,
) -> fabric.Template | None:
    for entity in parsed["entities"]:
        if fabric.basename(entity.get("asset")) != SIDEWALK_CORNER_STRIP_BASENAME:
            continue
        ok, _reason = fabric.safe_template_entity(entity, False)
        if not ok:
            continue
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        return fabric.Template(
            role=SIDEWALK_CORNER_ROLE,
            asset_path=entity["asset"],
            parsed=entity,
            raw_record=ele_data[start:end],
            source_fpm=str(source_fpm),
            source_kind=source_kind,
        )
    return None


def _fabric_template(
    role: str,
    source_path: Path,
    parsed: dict[str, Any],
    ele_data: bytes,
    donor_path: Path,
    donor_parsed: dict[str, Any],
    donor_ele: bytes,
) -> fabric.Template:
    if role != SIDEWALK_CORNER_ROLE:
        return ORIGINAL_FABRIC_TEMPLATE(
            role,
            source_path,
            parsed,
            ele_data,
            donor_path,
            donor_parsed,
            donor_ele,
        )

    exact = _exact_sidewalk_corner_template(parsed, ele_data, source_path, "target-exact")
    if exact is not None:
        return exact
    exact = _exact_sidewalk_corner_template(
        donor_parsed, donor_ele, donor_path, "cybercity-exact"
    )
    if exact is not None:
        return exact

    # Sidewalk corners are ordinary static DLC geometry. Unlike dynamic light
    # markers, they can safely use the established generic-static carrier while
    # receiving their own map.ent bank path. CyberCity is the reliable static
    # carrier source in production even when the generated target contains only
    # roads/buildings and no pre-existing lamp/planter/trash record.
    carrier = fabric.find_generic_static_template(donor_parsed, donor_ele, donor_path)
    return fabric.Template(
        role=SIDEWALK_CORNER_ROLE,
        asset_path=SIDEWALK_CORNER_PATH,
        parsed=carrier.parsed,
        raw_record=carrier.raw_record,
        source_fpm=carrier.source_fpm,
        source_kind="generic-static-sidewalk-corner",
    )


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
        for local_z in CENTER_LOCAL_Z_OFFSETS:
            out.append(
                core._placement(
                    "road_center_yellow",
                    road,
                    0.0,
                    local_z,
                    ROAD_SURFACE_Y,
                    CENTER_YAW_OFFSET,
                    f"v9.2 manual-reference center line for Straight 4X #{road['record_index']}",
                )
            )

        # Keep the visually improved v9.1 lamp cadence exactly as-is; the manual
        # reference contained no lamp transform outlier.
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
                f"v9.2 sparse curb lamp beside Straight 4X #{road['record_index']}",
            )
            out.append(lamp)
            out.append(
                fabric.Placement(
                    role="street_dynamic_light",
                    x=lamp.x,
                    y=lamp.y + LAMP_LIGHT_Y,
                    z=lamp.z,
                    ry=None,
                    note=f"v9.2 light marker paired with lamp beside Straight 4X #{road['record_index']}",
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
                    0.0 if direction > 0.0 else 180.0,
                    f"v9.2 manual-reference straight approach arrow to 4-way #{junction['record_index']}",
                )
            )

    for junction in sorted(fourways, key=lambda e: int(e["record_index"])):
        # GameGuru's crosswalk asset pivot is not visually centered. The manual
        # correction moved the north crossing from (0,+200) to (+95,+200). Rotate
        # that exact canonical correction around the other three approaches.
        for yaw_offset, lx, lz in (
            (0.0, CROSSWALK_PIVOT_X, CROSSWALK_EDGE),
            (90.0, CROSSWALK_EDGE, -CROSSWALK_PIVOT_X),
            (180.0, -CROSSWALK_PIVOT_X, -CROSSWALK_EDGE),
            (270.0, -CROSSWALK_EDGE, CROSSWALK_PIVOT_X),
        ):
            out.append(
                core._placement(
                    "crosswalk",
                    junction,
                    lx,
                    lz,
                    ROAD_SURFACE_Y,
                    yaw_offset,
                    f"v9.2 pivot-corrected crosswalk at 4-way #{junction['record_index']}",
                )
            )

        # The user's manually placed corner was (-300,+300,-90) in junction-local
        # coordinates. Rotate that exact transform through each quadrant. We only
        # apply it to 4-ways because the manual reference does not prove T geometry.
        for yaw_offset, lx, lz in (
            (-90.0, -SIDEWALK_CORNER_EDGE, SIDEWALK_CORNER_EDGE),
            (0.0, SIDEWALK_CORNER_EDGE, SIDEWALK_CORNER_EDGE),
            (90.0, SIDEWALK_CORNER_EDGE, -SIDEWALK_CORNER_EDGE),
            (180.0, -SIDEWALK_CORNER_EDGE, -SIDEWALK_CORNER_EDGE),
        ):
            out.append(
                core._placement(
                    SIDEWALK_CORNER_ROLE,
                    junction,
                    lx,
                    lz,
                    SIDEWALK_CORNER_Y,
                    yaw_offset,
                    f"v9.2 manual-reference sidewalk corner at 4-way #{junction['record_index']}",
                )
            )

    return out


def main(argv: list[str] | None = None) -> int:
    original_policy = core.SEMANTIC_POLICY
    original_roles = core.FABRIC_ROLES
    original_template = core._fabric_template
    original_plan = core.plan_semantic_dressing
    original_strip = core.STRIP_BASENAMES
    try:
        core.SEMANTIC_POLICY = SEMANTIC_POLICY
        core.FABRIC_ROLES = FABRIC_ROLES
        core._fabric_template = _fabric_template
        core.plan_semantic_dressing = plan_semantic_dressing
        core.STRIP_BASENAMES = frozenset(
            set(original_strip) | {SIDEWALK_CORNER_STRIP_BASENAME}
        )
        return core.main(argv)
    finally:
        core.SEMANTIC_POLICY = original_policy
        core.FABRIC_ROLES = original_roles
        core._fabric_template = original_template
        core.plan_semantic_dressing = original_plan
        core.STRIP_BASENAMES = original_strip


if __name__ == "__main__":
    raise SystemExit(main())
