#!/usr/bin/env python3
"""Compatibility entrypoint for measured-city v10.1 storefront assets.

CyberCity's stock map does not necessarily place every storefront model that exists in
the installed Cyberpunk Streets Booster Pack. The measured-city compiler correctly
requires live mesh measurements, but v10.1 originally also required an exact placed ELE
record for each storefront. That made a valid installed-but-unplaced storefront fail.

For storefronts only, this wrapper keeps exact donor records when available and otherwise
uses the established safe generic-static ELE carrier while banking the actual storefront
FPE path. All non-storefront assets remain fail-closed and must still have safe exact
donor records.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fpm_author_measured_city_v10 as core
import fpm_author_street_fabric as fabric
from fpm_inspect import FpmError

STOREFRONT_FOLDER = r"Cyberpunk Streets Booster Pack\Store Fronts"


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
            role="measured-city-v10.1",
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
                role="measured-city-v10.1",
                asset_path=f"{STOREFRONT_FOLDER}\\{canonical}.fpe",
                parsed=carrier.parsed,
                raw_record=carrier.raw_record,
                source_fpm=carrier.source_fpm,
                source_kind="generic-static-measured-storefront",
            )

    return out


def main(argv: list[str] | None = None) -> int:
    original = core.donor_templates
    try:
        core.donor_templates = donor_templates_with_static_storefront_fallback
        return core.main(argv)
    finally:
        core.donor_templates = original


if __name__ == "__main__":
    raise SystemExit(main())
