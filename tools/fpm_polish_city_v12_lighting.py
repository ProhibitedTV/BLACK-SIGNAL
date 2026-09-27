"""Conservative native-reviewed lighting layer for District 12 V12.

This pass deliberately changes only appended V12 content.  The 9,009-record grouped
MAX baseline remains byte/index stable.  Architectural neon is mounted from measured
Cyberpunk Streets geometry at the exact facade pivot plane; if the asset geometry no
longer proves that contact relationship, the build fails rather than creating a floater.
"""
import argparse
from pathlib import Path

import fpm_polish_city_v12 as base
import fpm_polish_city_v12_nativefix as nativefix

_NATIVE_PLAN = nativefix.plan
NEON_ASSET = "CS_Neon_02"
PRACTICAL_ASSET = "White Light"
NEON_HERO_INDICES = frozenset({0, 1, 3, 5})


def _assert_neon_profile(measured):
    neon = measured[NEON_ASSET]
    wall = measured["CS_Wall_01"]
    # CS_Neon_02 is authored as an effectively planar, wall-mounted object.  Its
    # local Z plane sits one unit beyond the standard Cyberpunk Streets wall skin:
    # wall exterior -20, neon plane -21.  Keep that authored relationship exact.
    if neon["size"][2] > 0.05:
        raise base.FpmError("CS_Neon_02 is no longer a planar facade fixture")
    if abs(neon["min"][2] - neon["max"][2]) > 0.05:
        raise base.FpmError("CS_Neon_02 depth changed; facade lock needs recalibration")
    gap = abs(abs(neon["min"][2]) - abs(wall["min"][2]))
    if not 0.5 <= gap <= 1.5:
        raise base.FpmError("CS_Neon_02 no longer sits one unit outside the standard wall skin")


def _neon_mount(parcel, side, measured):
    """Return a facade-locked neon placement and prove it cannot float.

    Only north/south faces are used in this pass.  Their wall pivots are exactly
    z and z+depth in the city shell, so the standalone neon's authored local Z=-21
    lands one unit outside the wall's local exterior at Z=-20 without guessed offsets.
    """
    _assert_neon_profile(measured)
    neon = measured[NEON_ASSET]
    x = parcel["x"] + parcel["width"] / 2
    y = parcel["ground"] + 220
    if side == "north":
        z, yaw = parcel["z"], 0
    elif side == "south":
        z, yaw = parcel["z"] + parcel["depth"], 180
    else:
        raise base.FpmError(f"Unsupported lighting facade: {side}")

    # Keep the full sign inside the facade horizontally and vertically.  If a
    # future asset/parcel change violates this, fail closed rather than float/overhang.
    left = x + neon["min"][0]
    right = x + neon["max"][0]
    bottom = y + neon["min"][1]
    top = y + neon["max"][1]
    building_top = parcel["ground"] + parcel["floors"] * 200
    if left < parcel["x"] + 20 or right > parcel["x"] + parcel["width"] - 20:
        raise base.FpmError(f"Neon exceeds facade width on {parcel['name']}")
    if bottom < parcel["ground"] + 180 or top > building_top - 20:
        raise base.FpmError(f"Neon exceeds facade height on {parcel['name']}")

    return dict(
        asset=NEON_ASSET,
        x=x,
        y=y,
        z=z,
        yaw=yaw,
        group="lighting-neon",
        parcel=parcel["name"],
        mount_side=side,
        mount_gap=1.0,
    )


def _practical_mount(parcel, side):
    # Invisible practical-light marker just outside the same facade.  This is
    # intentionally modest: one additional pool per hero block, not citywide spam.
    x = parcel["x"] + parcel["width"] / 2
    y = parcel["ground"] + 115
    if side == "north":
        z = parcel["z"] - 38
    elif side == "south":
        z = parcel["z"] + parcel["depth"] + 38
    else:
        raise base.FpmError(f"Unsupported practical-light facade: {side}")
    return dict(
        asset=PRACTICAL_ASSET,
        x=x,
        y=y,
        z=z,
        yaw=0,
        group="lighting-practical",
        parcel=parcel["name"],
        mount_side=side,
    )


def plan(parsed, old, measured):
    rows, parcels, changes, protected, heroes = _NATIVE_PLAN(parsed, old, measured)
    existing = {base.signature(r) for r in rows}

    def add(row):
        sig = base.signature(row)
        if sig in existing:
            return
        existing.add(sig)
        rows.append(row)

    for index, parcel in enumerate(heroes):
        side = "north" if index % 2 == 0 else "south"
        # Every hero block gets one restrained doorway/storefront light pool.
        add(_practical_mount(parcel, side))
        # Four of six heroes get a second architectural neon face; two stay dark
        # deliberately so the city retains hierarchy instead of becoming neon soup.
        if index in NEON_HERO_INDICES:
            add(_neon_mount(parcel, side, measured))

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
