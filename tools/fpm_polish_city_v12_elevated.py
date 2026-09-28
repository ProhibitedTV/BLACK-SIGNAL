"""Add a restrained multi-level filming layer to District 12.

This pass sits on top of the native-reviewed V12 lighting pass and only appends
new records.  The 9,009-record grouped MAX baseline remains byte/index stable.

The goal is not to turn every block into a platforming maze.  Instead we add a
small number of deliberate vertical sets that read from the street and give the
BLACK SIGNAL episodic camera package more places to stage scenes:

* four second-tier exterior galleries on tall hero buildings;
* two enclosed pedestrian/service skybridges across selected street canyons;
* four rooftop terrace perimeters with camera gaps and practical pools.

Every placement is derived from saved parcel geometry or measured asset bounds.
If the expected relationships stop being true, this pass fails closed rather
than authoring floating decks, rails, or bridges.
"""
import argparse
import math
from pathlib import Path

import fpm_polish_city_v12 as base
import fpm_polish_city_v12_lighting as lighting

_LIGHTING_PLAN = lighting.plan

DECK_ASSET = "CS_Roof_Tile_2x2"
SUPPORT_ASSET = "CS_Wall_01_Overhang"
RAIL_ASSET = "CS_Sidewalk_Guard"
LIGHT_ASSET = "White Light"

# Existing V12 heroes that are tall enough to carry another exterior level.
TIER2_NAMES = (
    "Block-02-01",
    "Block-06-01",
    "Block-04-03",
    "Block-03-04",
)

# Two deliberately selected, aligned street canyons.  Both pairs are separated
# by an exact 1000-unit gap in the saved V11 parcel layout, allowing five 200-unit
# roof tiles to meet the two facade planes exactly without guessed bridge length.
SKYBRIDGE_PAIRS = (
    ("Block-02-03", "Block-03-03"),
    ("Block-04-04", "Block-05-04"),
)

# Rooftops distributed across the district rather than clustered around the
# original six hero buildings.  These become distinct dialogue / surveillance /
# establishing-shot stages instead of every roof receiving identical treatment.
ROOFTOP_NAMES = (
    "Block-04-01",
    "Block-02-04",
    "Block-03-05",
    "Block-05-04",
)

TIER2_HEIGHT = 400.0
SKYBRIDGE_HEIGHT = 600.0
BRIDGE_WIDTH_SCALE = 0.65
ROOFTOP_RAIL_INSET = 60.0


def _assert_profiles(measured):
    deck = measured[DECK_ASSET]
    guard = measured[RAIL_ASSET]
    support = measured[SUPPORT_ASSET]

    # The 2x2 roof tile is the proven V12 deck element.  At scale 1 its local
    # top is +100 from the entity pivot and its bottom is +80.
    if not math.isclose(deck["max"][1], 100.0, abs_tol=0.1):
        raise base.FpmError("Roof-tile top profile changed; elevated deck calibration invalid")
    if not math.isclose(deck["min"][1], 80.0, abs_tol=0.1):
        raise base.FpmError("Roof-tile bottom profile changed; elevated deck calibration invalid")
    if abs(guard["min"][1]) > 0.1:
        raise base.FpmError("Guard no longer sits at its pivot floor plane")
    if not math.isclose(support["max"][1], 200.0, abs_tol=0.1):
        raise base.FpmError("Overhang support height changed; tier-two calibration invalid")


def _append(rows, existing, row):
    sig = base.signature(row)
    if sig in existing:
        return False
    existing.add(sig)
    rows.append(row)
    return True


def _tier2_gallery(parcel, measured):
    """Build an opposite-facade second gallery at ground+400.

    V12's original reachable gallery occupies the west face at ground+200 and an
    upper resident is staged there.  The new level is intentionally moved to the
    east face rather than stacked through that resident.  The overhang starts at
    +200 and reaches +400; the roof-tile deck spans +380..+400, overlapping the
    support by 20 units so there is no visible vertical gap.
    """
    _assert_profiles(measured)
    if parcel["floors"] < 4:
        raise base.FpmError(f"{parcel['name']} is too short for a tier-two gallery")

    x, z, g = parcel["x"], parcel["z"], parcel["ground"]
    facade_x = x + parcel["width"]
    top = g + TIER2_HEIGHT
    rows = []

    # Mirror the proven V12 gallery grammar onto the east facade.  Yaw 270 makes
    # the measured overhang project outward (+X) from the saved facade plane.
    for dz in (300, 500):
        rows.append(
            dict(
                asset=SUPPORT_ASSET,
                x=facade_x,
                y=g + 200,
                z=z + dz,
                yaw=270,
                group="elevated-tier2-support",
                parcel=parcel["name"],
            )
        )
        rows.append(
            dict(
                asset=DECK_ASSET,
                x=facade_x + 120,
                y=top - measured[DECK_ASSET]["max"][1],
                z=z + dz,
                yaw=0,
                group="elevated-tier2-deck",
                parcel=parcel["name"],
                deck_top=top,
                mount_side="east",
            )
        )

    # Outer railing plus both end caps.  The facade is the inner barrier.
    for dz in (250, 350, 450, 550):
        rows.append(
            dict(
                asset=RAIL_ASSET,
                x=facade_x + 220,
                y=top + 0.1,
                z=z + dz,
                yaw=90,
                group="elevated-tier2-rail",
                parcel=parcel["name"],
            )
        )
    for cap_z in (z + 200, z + 600):
        for dx in (70, 170):
            rows.append(
                dict(
                    asset=RAIL_ASSET,
                    x=facade_x + dx,
                    y=top + 0.1,
                    z=cap_z,
                    yaw=0,
                    group="elevated-tier2-rail",
                    parcel=parcel["name"],
                )
            )

    rows.append(
        dict(
            asset=LIGHT_ASSET,
            x=facade_x + 120,
            y=top + 45,
            z=z + 400,
            yaw=0,
            group="elevated-tier2-light",
            parcel=parcel["name"],
        )
    )
    return rows


def _skybridge(left, right, measured):
    """Create a narrow bridge whose deck exactly spans two saved facade planes."""
    _assert_profiles(measured)
    if abs(left["ground"] - right["ground"]) > 0.1:
        raise base.FpmError("Skybridge pair does not share a ground plane")
    if left["z"] != right["z"] or left["depth"] != right["depth"]:
        raise base.FpmError("Skybridge pair is not longitudinally aligned")
    if min(left["floors"], right["floors"]) * 200 < SKYBRIDGE_HEIGHT + 200:
        raise base.FpmError("Skybridge pair is too short for the requested clearance")

    x0 = left["x"] + left["width"]
    x1 = right["x"]
    gap = x1 - x0
    tile_length = measured[DECK_ASSET]["size"][0]
    count = int(round(gap / tile_length))
    if count < 3 or not math.isclose(count * tile_length, gap, abs_tol=0.2):
        raise base.FpmError(
            f"Skybridge gap {gap} is not an exact multiple of the measured deck length {tile_length}"
        )

    g = left["ground"]
    deck_top = g + SKYBRIDGE_HEIGHT
    zc = left["z"] + left["depth"] / 2
    half_width = measured[DECK_ASSET]["size"][2] * BRIDGE_WIDTH_SCALE / 2
    rows = []

    for i in range(count):
        x = x0 + tile_length / 2 + i * tile_length
        rows.append(
            dict(
                asset=DECK_ASSET,
                x=x,
                y=deck_top - measured[DECK_ASSET]["max"][1],
                z=zc,
                yaw=0,
                scale=[1.0, 1.0, BRIDGE_WIDTH_SCALE],
                group="elevated-skybridge-deck",
                bridge=f"{left['name']}--{right['name']}",
                deck_top=deck_top,
            )
        )
        for side in (-1, 1):
            rows.append(
                dict(
                    asset=RAIL_ASSET,
                    x=x,
                    y=deck_top + 0.1,
                    z=zc + side * (half_width - 3),
                    yaw=0,
                    scale=[2.0, 1.0, 1.0],
                    group="elevated-skybridge-rail",
                    bridge=f"{left['name']}--{right['name']}",
                )
            )

    # Two pools create foreground/midground separation for bridge coverage.
    for fraction in (1 / 3, 2 / 3):
        rows.append(
            dict(
                asset=LIGHT_ASSET,
                x=x0 + gap * fraction,
                y=deck_top + 55,
                z=zc,
                yaw=0,
                group="elevated-skybridge-light",
                bridge=f"{left['name']}--{right['name']}",
            )
        )

    rows[0]["contact_left"] = x0
    rows[-3]["contact_right"] = x1
    return rows


def _rooftop_terrace(parcel, measured):
    """Rail a roof perimeter while deliberately preserving a broad camera gap."""
    _assert_profiles(measured)
    if parcel["width"] < 800 or parcel["depth"] < 800:
        raise base.FpmError(f"{parcel['name']} is too small for the rooftop terrace grammar")

    x0, z0 = parcel["x"], parcel["z"]
    w, d = parcel["width"], parcel["depth"]
    roof = parcel["ground"] + parcel["floors"] * 200
    inset = ROOFTOP_RAIL_INSET
    rows = []

    # Four approximately 200-unit rail modules per 800-unit side.  We use a
    # 2x X scale on the measured 96-unit guard.  On the south edge the two
    # central modules are omitted, leaving a ~400-unit camera gap.
    x_centers = [x0 + 100 + i * 200 for i in range(4)]
    z_centers = [z0 + 100 + i * 200 for i in range(4)]
    for side_z, edge_name in ((z0 + inset, "north"), (z0 + d - inset, "south")):
        for i, x in enumerate(x_centers):
            if edge_name == "south" and i in (1, 2):
                continue
            rows.append(
                dict(
                    asset=RAIL_ASSET,
                    x=x,
                    y=roof + 0.1,
                    z=side_z,
                    yaw=0,
                    scale=[2.0, 1.0, 1.0],
                    group="elevated-rooftop-rail",
                    parcel=parcel["name"],
                    edge=edge_name,
                    roof_plane=roof,
                )
            )
    for side_x, edge_name in ((x0 + inset, "west"), (x0 + w - inset, "east")):
        for z in z_centers:
            rows.append(
                dict(
                    asset=RAIL_ASSET,
                    x=side_x,
                    y=roof + 0.1,
                    z=z,
                    yaw=90,
                    scale=[2.0, 1.0, 1.0],
                    group="elevated-rooftop-rail",
                    parcel=parcel["name"],
                    edge=edge_name,
                    roof_plane=roof,
                )
            )

    for dx in (-180, 180):
        rows.append(
            dict(
                asset=LIGHT_ASSET,
                x=x0 + w / 2 + dx,
                y=roof + 70,
                z=z0 + d / 2,
                yaw=0,
                group="elevated-rooftop-light",
                parcel=parcel["name"],
                roof_plane=roof,
            )
        )
    return rows


def plan(parsed, old, measured):
    rows, parcels, changes, protected, heroes = _LIGHTING_PLAN(parsed, old, measured)
    _assert_profiles(measured)
    by_name = {p["name"]: p for p in parcels}
    existing = {base.signature(r) for r in rows}

    missing = (
        set(TIER2_NAMES)
        | set(ROOFTOP_NAMES)
        | {name for pair in SKYBRIDGE_PAIRS for name in pair}
    ) - by_name.keys()
    if missing:
        raise base.FpmError(f"Elevated pass is missing expected saved parcels: {sorted(missing)}")

    for name in TIER2_NAMES:
        for row in _tier2_gallery(by_name[name], measured):
            _append(rows, existing, row)

    for left_name, right_name in SKYBRIDGE_PAIRS:
        left, right = by_name[left_name], by_name[right_name]
        if left["x"] > right["x"]:
            left, right = right, left
        for row in _skybridge(left, right, measured):
            _append(rows, existing, row)

    for name in ROOFTOP_NAMES:
        for row in _rooftop_terrace(by_name[name], measured):
            _append(rows, existing, row)

    base.assert_grouped_source_prefix(parsed, rows)
    return rows, parcels, changes, protected, heroes


def build(source: Path, output: Path):
    original = base.plan
    try:
        base.plan = plan
        return base.build(source, output)
    finally:
        base.plan = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
