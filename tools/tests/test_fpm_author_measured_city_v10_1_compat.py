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


class MeasuredCityV101CompatTests(unittest.TestCase):
    def test_unplaced_storefront_uses_safe_generic_static_carrier(self):
        carrier = fabric.Template(
            role="generic_static",
            asset_path=r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Trash_Can.fpe",
            parsed={"asset": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Trash_Can.fpe"},
            raw_record=b"safe-static-carrier",
            source_fpm="CyberCity.fpm",
            source_kind="generic-static-target",
        )
        missing_storefront = core.STOREFRONT_ASSETS[1]
        with patch.object(compat.fabric, "find_generic_static_template", return_value=carrier):
            templates = compat.donor_templates_with_static_storefront_fallback(
                {"entities": []},
                b"",
                {missing_storefront},
                Path("CyberCity.fpm"),
            )

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
