import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_semantics_v9_compat as author_compat
import fpm_validate_road_semantics_v9_compat as validator_compat


class RoadSemanticsV9CompatTests(unittest.TestCase):
    def test_lamp_only_policy_removes_only_pairing_error(self) -> None:
        report = {
            "errors": [
                "street lamp/light-marker pairing is invalid (12 lamps, 0 markers)",
                "some unrelated validation failure",
            ],
            "status": "fail",
            "error_count": 2,
        }
        semantic = {
            "lighting_mode": author_compat.MODE_LAMP_ONLY,
            "role_counts": {"street_lamp": 12, "street_dynamic_light": 0},
        }
        out = validator_compat.apply_lighting_policy(report, semantic)
        self.assertEqual(out["errors"], ["some unrelated validation failure"])
        self.assertEqual(out["status"], "fail")
        self.assertEqual(out["error_count"], 1)

    def test_lamp_only_policy_passes_when_pairing_is_only_error(self) -> None:
        report = {
            "errors": ["street lamp/light-marker pairing is invalid (8 lamps, 0 markers)"],
            "status": "fail",
            "error_count": 1,
        }
        semantic = {
            "lighting_mode": author_compat.MODE_LAMP_ONLY,
            "role_counts": {"street_lamp": 8, "street_dynamic_light": 0},
        }
        out = validator_compat.apply_lighting_policy(report, semantic)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["status"], "pass")
        self.assertEqual(out["error_count"], 0)

    def test_dynamic_mode_keeps_core_pairing_failure(self) -> None:
        report = {
            "errors": ["street lamp/light-marker pairing is invalid (8 lamps, 0 markers)"],
            "status": "fail",
            "error_count": 1,
        }
        semantic = {
            "lighting_mode": author_compat.MODE_DYNAMIC,
            "role_counts": {"street_lamp": 8, "street_dynamic_light": 0},
        }
        out = validator_compat.apply_lighting_policy(report, semantic)
        self.assertEqual(len(out["errors"]), 1)
        self.assertEqual(out["status"], "fail")

    def test_lamp_only_requires_real_lamp_meshes(self) -> None:
        report = {
            "errors": ["street lamp/light-marker pairing is invalid (0 lamps, 0 markers)"],
            "status": "fail",
            "error_count": 1,
        }
        semantic = {
            "lighting_mode": author_compat.MODE_LAMP_ONLY,
            "role_counts": {"street_lamp": 0, "street_dynamic_light": 0},
        }
        out = validator_compat.apply_lighting_policy(report, semantic)
        self.assertIn("lamp-only fallback produced no street-lamp meshes", out["errors"])
        self.assertEqual(out["status"], "fail")


if __name__ == "__main__":
    unittest.main()
