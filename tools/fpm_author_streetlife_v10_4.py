#!/usr/bin/env python3
"""V10.4 Hero Block street-life layer: measured planters, city trees and accent lights.

This wraps the accepted v10.3 street-level pass.  It does not modify roads, markings,
Astra building shells, storefront overlays, bollards, rails, utility poles or the current
street-lamp cadence.  Installed vegetation is discovered and measured at build time; only
entity-bank paths and placement metadata enter the generated FPM.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import fpm_author_road_semantics_v10_3 as street
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmError

STREETLIFE_ROLES = ("city_planter", "city_tree", "planter_light")
EXPECTED_STREETLIFE_COUNTS = {
    "city_planter": 8,
    "city_tree": 8,
    "planter_light": 8,
}

# Eight paired planter/tree moments frame the Hero Block without filling every sidewalk.
# They sit between the v10.3 guard rails (~650) and low sidewalk lights (~1100), outside
# the measured +/-300 central asphalt envelope and away from the storefront entry pivots.
PLANTER_LAYOUT = (
    (820.0, 410.0, 180.0),
    (410.0, 820.0, 270.0),
    (-820.0, 410.0, 180.0),
    (-410.0, 820.0, 90.0),
    (820.0, -410.0, 0.0),
    (410.0, -820.0, 270.0),
    (-820.0, -410.0, 0.0),
    (-410.0, -820.0, 90.0),
)

# One low fixture per planter, shifted toward the curb so it can graze the foliage and
# create foreground depth without turning the block into another street-lamp forest.
PLANTER_LIGHT_LAYOUT = (
    (820.0, 330.0, 180.0),
    (330.0, 820.0, 270.0),
    (-820.0, 330.0, 180.0),
    (-330.0, 820.0, 90.0),
    (820.0, -330.0, 0.0),
    (330.0, -820.0, 270.0),
    (-820.0, -330.0, 0.0),
    (-330.0, -820.0, 90.0),
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


def _safe_asset_row(row: Any, label: str) -> tuple[str, str]:
    if not isinstance(row, dict):
        raise FpmError(f"v10.4 street-life discovery is missing {label}")
    raw = str(row.get("asset") or "").replace("/", "\\")
    path = Path(raw.replace("\\", "/"))
    if not raw or path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".fpe":
        raise FpmError(f"unsafe discovered {label} asset path: {raw!r}")
    return raw, path.name


def load_asset_config(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("policy") != "v10.4-installed-measured-streetlife-assets":
        raise FpmError("street-life discovery report has the wrong policy")
    planter_path, planter_name = _safe_asset_row(payload.get("planter"), "planter")
    tree_path, tree_name = _safe_asset_row(payload.get("tree"), "tree")
    return {
        "city_planter": {"path": planter_path, "basename": planter_name, "dynamic": False},
        "city_tree": {"path": tree_path, "basename": tree_name, "dynamic": False},
        # Reuse the existing low-profile Cyberpunk sidewalk fixture as a distinct semantic
        # role.  The validator accounts for the shared mesh basename explicitly.
        "planter_light": {
            "path": fabric.ASSETS["sidewalk_light"]["path"],
            "basename": fabric.ASSETS["sidewalk_light"]["basename"],
            "dynamic": False,
        },
    }


def _streetlife_dressing(parsed: dict[str, Any]) -> list[fabric.Placement]:
    junction = street._central_fourway(parsed)
    out: list[fabric.Placement] = []
    for index, (lx, lz, yaw) in enumerate(PLANTER_LAYOUT):
        for role in ("city_planter", "city_tree"):
            out.append(
                street.base.core._placement(
                    role,
                    junction,
                    lx,
                    lz,
                    0.0,
                    (yaw + (index * 45.0 if role == "city_tree" else 0.0)) % 360.0,
                    f"v10.4 hero-block measured {role} pair {index + 1} around central 4-way #{junction['record_index']}",
                )
            )
    for index, (lx, lz, yaw) in enumerate(PLANTER_LIGHT_LAYOUT):
        out.append(
            street.base.core._placement(
                "planter_light",
                junction,
                lx,
                lz,
                0.0,
                yaw,
                f"v10.4 hero-block planter accent light {index + 1} around central 4-way #{junction['record_index']}",
            )
        )
    return out


def _streetlife_template(
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

    carrier = fabric.find_generic_static_template(donor_parsed, donor_ele, donor_path)
    spec = fabric.ASSETS[role]
    return fabric.Template(
        role=role,
        asset_path=str(spec["path"]),
        parsed=carrier.parsed,
        raw_record=carrier.raw_record,
        source_fpm=carrier.source_fpm,
        source_kind="generic-static-v10.4-streetlife",
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        args, config_value = _pop_option(args, "--streetlife-assets")
        if config_value is None:
            raise FpmError("v10.4 requires --streetlife-assets from the local discovery preflight")
        discovered = load_asset_config(Path(config_value))
    except (FpmError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"FPM STREETLIFE V10.4 ERROR: {exc}", file=sys.stderr)
        return 2

    original_assets = dict(fabric.ASSETS)
    original_roles = street.STREET_LEVEL_ROLES
    original_counts = dict(street.EXPECTED_STREET_LEVEL_COUNTS)
    original_dressing = street._hero_block_dressing
    original_template = street._static_street_template

    def combined_dressing(parsed: dict[str, Any]) -> list[fabric.Placement]:
        return list(original_dressing(parsed)) + _streetlife_dressing(parsed)

    def combined_template(
        role: str,
        source_path: Path,
        parsed: dict[str, Any],
        ele_data: bytes,
        donor_path: Path,
        donor_parsed: dict[str, Any],
        donor_ele: bytes,
    ) -> fabric.Template:
        if role in STREETLIFE_ROLES:
            return _streetlife_template(
                role, source_path, parsed, ele_data, donor_path, donor_parsed, donor_ele
            )
        return original_template(
            role, source_path, parsed, ele_data, donor_path, donor_parsed, donor_ele
        )

    try:
        fabric.ASSETS.update(discovered)
        street.STREET_LEVEL_ROLES = tuple(original_roles) + STREETLIFE_ROLES
        street.EXPECTED_STREET_LEVEL_COUNTS = {**original_counts, **EXPECTED_STREETLIFE_COUNTS}
        street._hero_block_dressing = combined_dressing
        street._static_street_template = combined_template
        return street.main(args)
    finally:
        fabric.ASSETS.clear()
        fabric.ASSETS.update(original_assets)
        street.STREET_LEVEL_ROLES = original_roles
        street.EXPECTED_STREET_LEVEL_COUNTS = original_counts
        street._hero_block_dressing = original_dressing
        street._static_street_template = original_template


if __name__ == "__main__":
    raise SystemExit(main())
