import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_surface_v7 as surface


STRAIGHT = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe"
FOURWAY = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_4_Way_2.fpe"
TEE = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_T-Intersect_3.fpe"
CURVE = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Curve_1.fpe"


def road(asset: str, *, x=0.0, z=0.0, index=1) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 0.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
        "record_index": index,
    }


class RoleAwareSurfaceOwnershipTests(unittest.TestCase):
    def test_arrow_attaches_to_straight_approach_not_nearer_intersection(self):
        roads = [
            road(FOURWAY, x=0.0, z=0.0, index=10),
            road(STRAIGHT, x=250.0, z=0.0, index=20),
        ]
        arrow = road("arrow.fpe", x=25.0, z=0.0, index=90)
        owner, distance = surface.nearest_compatible_road(
            arrow, roads, "road_arrow_straight"
        )
        self.assertIsNotNone(owner)
        self.assertEqual(owner["record_index"], 20)
        self.assertAlmostEqual(distance, 225.0)

    def test_regulatory_text_attaches_only_to_straight(self):
        self.assertEqual(
            surface.compatible_road_kinds("road_slow"), frozenset(("straight4",))
        )
        self.assertEqual(
            surface.compatible_road_kinds("road_only"), frozenset(("straight4",))
        )

    def test_wear_can_attach_to_any_supported_full_width_module(self):
        allowed = surface.compatible_road_kinds("road_wear_01")
        self.assertEqual(allowed, frozenset(("straight4", "fourway", "tee", "curve")))

    def test_curve_is_not_a_traffic_junction_for_approach_markings(self):
        approach = road(STRAIGHT, x=0.0, z=0.0, index=1)
        curve = road(CURVE, x=0.0, z=100.0, index=2)
        tee = road(TEE, x=0.0, z=500.0, index=3)
        owner, local_z = surface.nearest_traffic_junction(approach, [curve, tee])
        self.assertIsNotNone(owner)
        self.assertEqual(owner["record_index"], 3)
        self.assertAlmostEqual(local_z, 500.0)


if __name__ == "__main__":
    unittest.main()
