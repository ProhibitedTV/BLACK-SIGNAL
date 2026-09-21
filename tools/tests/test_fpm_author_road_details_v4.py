import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_details_v4 as detail
from fpm_inspect import FpmError


def road(asset: str, *, x=0.0, y=0.0, z=0.0, yaw=0.0, index=1) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": y, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": index,
    }


class CoherentRoadDetailTests(unittest.TestCase):
    def test_uniform_grammar_accepts_only_full_width_main_road_family(self):
        parsed = {
            "entities": [
                road("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe"),
                road("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_4_Way_2.fpe", index=2),
                road("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_T-Intersect_3.fpe", index=3),
                road("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Curve_1.fpe", index=4),
            ]
        }
        counts = detail.validate_uniform_grammar(parsed)
        self.assertEqual(counts["straight4"], 1)
        self.assertEqual(sum(counts.values()), 4)

    def test_uniform_grammar_rejects_smaller_straight_substitutions(self):
        parsed = {
            "entities": [
                road("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe"),
                road("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_2X.fpe", index=2),
            ]
        }
        with self.assertRaises(FpmError):
            detail.validate_uniform_grammar(parsed)

    def test_straight_profile_requires_real_center_marking(self):
        self.assertEqual(
            detail.REQUIRED_PROFILE_ROLES["straight4"],
            frozenset(("road_center_yellow",)),
        )
        self.assertIn("street_lamp", detail.PROFILE_ROLES["straight4"])
        self.assertIn("street_dynamic_light", detail.PROFILE_ROLES["straight4"])

    def test_member_transform_rotates_exemplar_offset_with_target_road(self):
        member = detail.AssemblyMember(
            role="road_center_yellow",
            asset_path="CS_Street_Double_Center_Line.fpe",
            parsed={},
            raw_record=b"",
            local_x=100.0,
            y_offset=2.0,
            local_z=0.0,
            relative_yaw=0.0,
            donor_record_index=99,
        )
        target = road("CS_Street_Straight_4X.fpe", x=1000.0, y=25.0, z=2000.0, yaw=90.0, index=7)
        placement = detail.placement_for_member(member, target)
        self.assertAlmostEqual(placement.x, 1000.0, places=4)
        self.assertAlmostEqual(placement.z, 1900.0, places=4)
        self.assertAlmostEqual(placement.y, 27.0, places=4)
        self.assertAlmostEqual(placement.ry, 90.0, places=4)

    def test_assembly_score_prefers_required_role_coverage(self):
        center = detail.AssemblyMember(
            role="road_center_yellow",
            asset_path="center.fpe",
            parsed={},
            raw_record=b"",
            local_x=0.0,
            y_offset=0.0,
            local_z=0.0,
            relative_yaw=0.0,
            donor_record_index=1,
        )
        lamp = detail.AssemblyMember(
            role="street_lamp",
            asset_path="lamp.fpe",
            parsed={},
            raw_record=b"",
            local_x=10.0,
            y_offset=0.0,
            local_z=0.0,
            relative_yaw=0.0,
            donor_record_index=2,
        )
        self.assertGreater(
            detail.assembly_score("straight4", [center]),
            detail.assembly_score("straight4", [lamp]),
        )


if __name__ == "__main__":
    unittest.main()
