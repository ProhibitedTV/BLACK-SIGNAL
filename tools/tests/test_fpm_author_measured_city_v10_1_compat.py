import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_measured_city_v10 as core
import fpm_author_measured_city_v10_1_compat as compat
import fpm_author_street_fabric as fabric


class MeasuredCityV102CompatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_measured = json.loads(
            (Path(__file__).resolve().parents[2] / "docs/cybercity-kit-measurements.json").read_text()
        )
        cls.measured = copy.deepcopy(cls.base_measured)
        safe = compat.SAFE_STOREFRONT_ASSETS[0]
        cls.measured[safe] = copy.deepcopy(cls.base_measured["CS_Wall_Corner_01"])
        cls.measured[safe]["asset"] = f"Cyberpunk Streets Booster Pack\\Store Fronts\\{safe}.fpe"

    def test_storefront_is_overlay_and_structural_corner_is_preserved(self):
        rows = compat.storefront_overlay_calibration(self.measured)
        shops = [row for row in rows if row["asset"] in compat.SAFE_STOREFRONT_ASSETS]
        ground_corners = [
            row
            for row in rows
            if row["group"] in core.HERO_GROUPS
            and row["asset"] == "CS_Wall_Corner_01"
            and abs(float(row["y"]) - core.GROUND_FLOOR_Y) < 0.01
        ]
        expected = len(core.HERO_GROUPS) * core.STOREFRONTS_PER_BUILDING
        self.assertEqual(len(shops), expected)
        self.assertEqual(len(ground_corners), expected)
        self.assertTrue(all(abs(float(row["y"]) - core.GROUND_FLOOR_Y) < 0.01 for row in shops))

    def test_rejected_neon_signage_variant_is_not_authored(self):
        rows = compat.storefront_overlay_calibration(self.measured)
        self.assertNotIn(
            "CS_Store_Front_02_Corner_Neon_Opposite",
            {row["asset"] for row in rows},
        )

    def test_unplaced_storefront_uses_safe_generic_static_carrier(self):
        carrier = fabric.Template(
            role="generic_static",
            asset_path=r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Trash_Can.fpe",
            parsed={"asset": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Trash_Can.fpe"},
            raw_record=b"safe-static-carrier",
            source_fpm="CyberCity.fpm",
            source_kind="generic-static-target",
        )
        missing_storefront = compat.SAFE_STOREFRONT_ASSETS[0]
        original_assets = core.STOREFRONT_ASSETS
        try:
            core.STOREFRONT_ASSETS = compat.SAFE_STOREFRONT_ASSETS
            with patch.object(compat.fabric, "find_generic_static_template", return_value=carrier):
                templates = compat.donor_templates_with_static_storefront_fallback(
                    {"entities": []},
                    b"",
                    {missing_storefront},
                    Path("CyberCity.fpm"),
                )
        finally:
            core.STOREFRONT_ASSETS = original_assets

        template = templates[missing_storefront]
        self.assertEqual(template.raw_record, carrier.raw_record)
        self.assertIs(template.parsed, carrier.parsed)
        self.assertEqual(template.source_kind, "generic-static-measured-storefront")
        self.assertEqual(
            template.asset_path,
            rf"Cyberpunk Streets Booster Pack\Store Fronts\{missing_storefront}.fpe",
        )

    def test_non_storefront_missing_template_still_fails_closed(self):
        with self.assertRaisesRegex(Exception, "Missing safe measured donor templates"):
            compat.donor_templates_with_static_storefront_fallback(
                {"entities": []},
                b"",
                {"CS_Wall_01"},
                Path("CyberCity.fpm"),
            )


if __name__ == "__main__":
    unittest.main()
