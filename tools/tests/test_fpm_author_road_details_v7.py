import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_details_v7 as detail


STRAIGHT = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe"
FOURWAY = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_4_Way_2.fpe"
TEE = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_T-Intersect_3.fpe"


def entity(asset: str, *, x=0.0, z=0.0, index=1) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 0.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
        "record_index": index,
    }


class RoleAwareStructuralOwnershipTests(unittest.TestCase):
    def test_crosswalk_cannot_be_owned_by_straight_even_when_straight_is_closer(self):
        roads = [
            entity(STRAIGHT, x=0.0, z=0.0, index=10),
            entity(FOURWAY, x=300.0, z=0.0, index=20),
        ]
        crosswalk = entity("crosswalk.fpe", x=20.0, z=0.0, index=99)
        owner, distance = detail.nearest_compatible_road(crosswalk, roads, "crosswalk")
        self.assertIsNotNone(owner)
        self.assertEqual(owner["record_index"], 20)
        self.assertAlmostEqual(distance, 280.0)

    def test_centerline_is_owned_only_by_straight(self):
        roads = [
            entity(FOURWAY, x=0.0, z=0.0, index=10),
            entity(STRAIGHT, x=250.0, z=0.0, index=20),
        ]
        centerline = entity("center.fpe", x=15.0, z=0.0, index=98)
        owner, _distance = detail.nearest_compatible_road(
            centerline, roads, "road_center_yellow"
        )
        self.assertIsNotNone(owner)
        self.assertEqual(owner["record_index"], 20)

    def test_crosswalk_can_choose_between_fourway_and_tee(self):
        roads = [
            entity(FOURWAY, x=0.0, z=0.0, index=10),
            entity(TEE, x=200.0, z=0.0, index=20),
        ]
        crosswalk = entity("crosswalk.fpe", x=175.0, z=0.0, index=97)
        owner, _distance = detail.nearest_compatible_road(crosswalk, roads, "crosswalk")
        self.assertIsNotNone(owner)
        self.assertEqual(owner["record_index"], 20)

    def test_equal_distance_tie_is_deterministic_by_record_index(self):
        roads = [
            entity(FOURWAY, x=-100.0, z=0.0, index=12),
            entity(TEE, x=100.0, z=0.0, index=8),
        ]
        crosswalk = entity("crosswalk.fpe", x=0.0, z=0.0, index=90)
        owner, _distance = detail.nearest_compatible_road(crosswalk, roads, "crosswalk")
        self.assertIsNotNone(owner)
        self.assertEqual(owner["record_index"], 8)


if __name__ == "__main__":
    unittest.main()
