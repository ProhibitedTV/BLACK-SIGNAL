#!/usr/bin/env python3
"""Production compatibility/visual-correction entrypoint for measured-city storefronts.

Two production facts are handled here without weakening the measured-city core:

1. CyberCity's stock map does not necessarily place every storefront model that exists
   in the installed Cyberpunk Streets Booster Pack. For storefronts only, an installed,
   measured but unplaced static storefront may use the established safe generic-static
   ELE carrier while banking the real storefront FPE path.
2. Storefront pieces are facade overlays, not structural replacements. The proven Astra
   ground-floor CS_Wall_Corner_01 shell geometry stays in place and storefront geometry is
   added on top of it at the same calibrated corner pivot/yaw.

The visually bad Neon Opposite variant is intentionally excluded from production until
it has its own independently calibrated signage transform. All non-storefront assets
remain fail-closed and still require safe exact donor records.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import fpm_author_measured_city_v10 as core
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmError

STOREFRONT_FOLDER = r"Cyberpunk Streets Booster Pack\Store Fronts"
SAFE_STOREFRONT_ASSETS = (
    "CS_Store_Front_02_Corner_With_Window",
)


def storefront_overlay_calibration(measured: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep the complete measured shell and add storefront geometry as an overlay.

    The shop overlay inherits the exact pivot/yaw of each proven ground-floor corner.
    We deliberately do not remove the structural corner module: the storefront is visual
    frontage, while CS_Wall_Corner_01 continues to close the building envelope.
    """
    missing = [name for name in SAFE_STOREFRONT_ASSETS if name not in measured]
    if missing:
        raise FpmError(
            "Measured storefront geometry is missing: "
            + ", ".join(missing)
            + ". Rerun measure-cybercity-kit.py against the installed Cyberpunk Streets pack."
        )

    calibration = core.hero.plan()
    core.hero.validate(calibration, measured)
    seen: Counter[str] = Counter()
    overlaid: list[dict[str, Any]] = []

    for row in calibration:
        # Always preserve Astra's original measured building geometry.
        overlaid.append(dict(row))

        if (
            row["group"] in core.HERO_GROUPS
            and row["asset"] == "CS_Wall_Corner_01"
            and abs(float(row["y"]) - core.GROUND_FLOOR_Y) <= 0.01
        ):
            overlay = dict(row)
            overlay["asset"] = SAFE_STOREFRONT_ASSETS[0]
            overlaid.append(overlay)
            seen[row["group"]] += 1

    for group in core.HERO_GROUPS:
        if seen[group] != core.STOREFRONTS_PER_BUILDING:
            raise FpmError(
                f"Storefront overlay expected {core.STOREFRONTS_PER_BUILDING} ground-floor corners for {group}, got {seen[group]}."
            )
        preserved = sum(
            1
            for row in overlaid
            if row["group"] == group
            and row["asset"] == "CS_Wall_Corner_01"
            and abs(float(row["y"]) - core.GROUND_FLOOR_Y) <= 0.01
        )
        if preserved != core.STOREFRONTS_PER_BUILDING:
            raise FpmError(
                f"Ground-floor structural corners were not preserved for {group}: {preserved}."
            )

    return overlaid


def donor_templates_with_static_storefront_fallback(
    donor_parsed: dict[str, Any], donor_ele: bytes, required: set[str], donor_path: Path
) -> dict[str, fabric.Template]:
    out: dict[str, fabric.Template] = {}
    required_fold = {name.casefold(): name for name in required}

    for entity in donor_parsed["entities"]:
        raw_key = core.asset_key(entity.get("asset"))
        canonical = required_fold.get(raw_key.casefold())
        if canonical is None or canonical in out:
            continue
        safe, _reason = fabric.safe_template_entity(entity, False)
        if not safe or int(entity.get("profile_scale", 100)) != 100:
            continue
        if any(abs(float(v)) > 0.001 for v in entity.get("scale_xyz", {}).values()):
            continue
        start = int(entity["record_start_offset"])
        end = int(entity["record_end_offset"])
        out[canonical] = fabric.Template(
            role="measured-city-v10.2-overlay",
            asset_path=str(entity.get("asset") or ""),
            parsed=entity,
            raw_record=donor_ele[start:end],
            source_fpm=str(donor_path),
            source_kind="exact-measured-donor",
        )

    missing = required - set(out)
    storefront_missing = missing.intersection(core.STOREFRONT_ASSETS)
    non_storefront_missing = missing - storefront_missing
    if non_storefront_missing:
        raise FpmError(
            "Missing safe measured donor templates: "
            + ", ".join(sorted(non_storefront_missing))
        )

    if storefront_missing:
        carrier = fabric.find_generic_static_template(donor_parsed, donor_ele, donor_path)
        for canonical in sorted(storefront_missing):
            out[canonical] = fabric.Template(
                role="measured-city-v10.2-overlay",
                asset_path=f"{STOREFRONT_FOLDER}\{canonical}.fpe",
                parsed=carrier.parsed,
                raw_record=carrier.raw_record,
                source_fpm=carrier.source_fpm,
                source_kind="generic-static-measured-storefront",
            )

    return out


def print_overlay_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - District 12 measured city v10.2 storefront overlay correction")
    print(f"Target road source: {report['source_fpm']}")
    print(f"CyberCity donor:    {report['donor_fpm']}")
    print(f"Output:             {report['output_fpm']}")
    print(f"Hero origin:        {report['hero_origin']}")
    print(f"Added entities:     {report['added_entities']}")
    print(f"Storefront overlays:{report['storefront_count']:6d}")
    for group, count in sorted(report["groups"].items()):
        print(f"  {group:20s} {count}")
    print("[PASS] Complete measured shell courses, structural ground-floor corners and roofs were preserved.")
    print("[PASS] Storefront geometry was overlaid on the existing ground-floor corners instead of replacing them.")
    print("[PASS] Neon Opposite/signage variant is excluded pending independent sign calibration.")
    print("[PASS] Validated target roads were preserved and used for collision checks.")
    print("[PASS] Junction corners and street lamps remain owned by the semantic road pass.")
    print("[NEXT] Native GameGuru MAX visual review is still required before production acceptance.")


def main(argv: list[str] | None = None) -> int:
    original_templates = core.donor_templates
    original_calibration = core.storefront_wrapped_calibration
    original_assets = core.STOREFRONT_ASSETS
    original_report = core.print_report
    try:
        core.STOREFRONT_ASSETS = SAFE_STOREFRONT_ASSETS
        core.storefront_wrapped_calibration = storefront_overlay_calibration
        core.donor_templates = donor_templates_with_static_storefront_fallback
        core.print_report = print_overlay_report
        return core.main(argv)
    finally:
        core.donor_templates = original_templates
        core.storefront_wrapped_calibration = original_calibration
        core.STOREFRONT_ASSETS = original_assets
        core.print_report = original_report


if __name__ == "__main__":
    raise SystemExit(main())
