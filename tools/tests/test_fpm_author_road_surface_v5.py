import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_surface_v5 as surface


def road(asset: str, *, x=0.0, y=0.0, z=0.0, yaw=0.0, index=1) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": y, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": index,
    }


STRAIGHT = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe"
FOURWAY = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_4_Way_2.fpe"
TEE = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_T-Intersect_3.fpe"


class RoadSurfaceDetailV5Tests(unittest.TestCase):
    def test_pack_roles_include_wear_arrows_and_manhole(self):
        for index in range(1, 10):
            role = f"road_wear_{index:02d}"
            self.assertIn(role, surface.SURFACE_ASSETS)
            self.assertEqual(
                surface.SURFACE_ASSETS[role]["basename"],
                f"CS_Street_Decal_{index:02d}.fpe",
            )
        self.assertIn("road_arrow_straight_right", surface.SURFACE_ASSETS)
        self.assertEqual(
            surface.SURFACE_ASSETS["manhole_cover"]["basename"],
            "CS_Street_Manhole_Cover.fpe",
        )

    def test_every_straight_gets_one_wear_decal(self):
        parsed = {
            "entities": [
                road(STRAIGHT, x=0.0, z=500.0, index=1),
                road(STRAIGHT, x=0.0, z=900.0, index=2),
                road(STRAIGHT, x=0.0, z=1300.0, index=3),
            ]
        }
        plan = surface.plan_surface_details(parsed)
        wear = [p for p in plan if p.role in surface.WEAR_ROLES]
        self.assertEqual(len(wear), 3)
        self.assertEqual({p.road_record_index for p in wear}, {1, 2, 3})

    def test_intersection_approach_gets_one_lane_arrow_aligned_with_road(self):
        parsed = {
            "entities": [
                road(STRAIGHT, x=0.0, z=500.0, yaw=0.0, index=1),
                road(FOURWAY, x=0.0, z=0.0, yaw=0.0, index=2),
            ]
        }
        plan = surface.plan_surface_details(parsed)
        arrows = [p for p in plan if p.role in surface.ARROW_ROLES]
        self.assertEqual(len(arrows), 1)
        arrow = arrows[0]
        self.assertAlmostEqual(arrow.x, -94.0, places=3)
        self.assertAlmostEqual(arrow.z, 388.0, places=3)
        self.assertAlmostEqual(arrow.ry, 270.0, places=3)

    def test_rotated_road_rotates_lane_offset_and_arrow(self):
        parsed = {
            "entities": [
                road(STRAIGHT, x=500.0, z=0.0, yaw=90.0, index=1),
                road(TEE, x=0.0, z=0.0, yaw=0.0, index=2),
            ]
        }
        plan = surface.plan_surface_details(parsed)
        arrows = [p for p in plan if p.role in surface.ARROW_ROLES]
        self.assertEqual(len(arrows), 1)
        arrow = arrows[0]
        # Junction is in the target road's +local-Z direction at yaw 90.
        self.assertAlmostEqual(arrow.x, 612.0, places=3)
        self.assertAlmostEqual(arrow.z, -94.0, places=3)
        self.assertAlmostEqual(arrow.ry, 180.0, places=3)

    def test_plan_is_repeatable_independent_of_entity_order(self):
        entities = [
            road(FOURWAY, x=0.0, z=0.0, index=10),
            road(STRAIGHT, x=0.0, z=500.0, index=11),
            road(STRAIGHT, x=0.0, z=900.0, index=12),
        ]
        a = surface.plan_surface_details({"entities": entities})
        b = surface.plan_surface_details({"entities": list(reversed(entities))})
        signature = lambda plan: sorted(
            (p.role, round(p.x, 3), round(p.z, 3), round(p.ry, 3), p.note)
            for p in plan
        )
        self.assertEqual(signature(a), signature(b))

    def test_surface_pass_does_not_own_v4_centerline_crosswalk_or_bollard_assets(self):
        protected = {
            "cs_street_double_center_line.fpe",
            "cs_street_crosswalk_decal.fpe",
            "cs_street_crosswalk_metal_blocker_post.fpe",
        }
        self.assertTrue(surface.OWNED_BASENAMES.isdisjoint(protected))


if __name__ == "__main__":
    unittest.main()
