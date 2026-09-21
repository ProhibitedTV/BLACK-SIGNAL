import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v2 as road


def ent(idx, x, z, asset="Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe", yaw=0.0):
    return {
        "record_index": idx,
        "position": {"x": float(x), "y": 1000.0, "z": float(z)},
        "rotation_euler": {"x": 0.0, "y": float(yaw), "z": 0.0},
        "asset": asset,
        "staticflag": 1,
        "v319_group_count": 0,
    }


class RoadNetworkV2Tests(unittest.TestCase):
    def test_plan_uses_every_road_surface_module(self):
        plan = road.plan_network(7)
        kinds = {p.kind for p in plan}
        self.assertEqual(kinds, set(road.ROAD_SPECS))
        self.assertGreater(len(plan), 250)

    def test_middle_pattern_can_fill_400_units_with_all_small_lengths(self):
        rows = road.span_modules(0.0, 2)
        self.assertIn((800.0, "straight2"), rows)
        self.assertIn((950.0, "straight1"), rows)
        quarter = [x for x, kind in rows if kind == "quarter"]
        self.assertEqual(quarter, [1012.5, 1037.5, 1062.5, 1087.5])
        self.assertEqual(rows[0], (500.0, "straight4"))
        self.assertEqual(rows[-1], (1300.0, "straight4"))

    def test_curve_neighbor_inference_allows_arc_offsets(self):
        curve = ent(
            1,
            0,
            0,
            "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Curve_1.fpe",
        )
        # Deliberately not collinear with the curve center. The old +/-75-unit
        # test returned an empty connection mask for this geometry.
        east = ent(2, 520, 180)
        north = ent(3, 170, 540)
        far = ent(4, -1200, -1200)
        mask = road.directional_neighbor_mask(curve, [curve, east, north, far], 2)
        self.assertEqual(mask, frozenset(("E", "N")))
        self.assertTrue(road.mask_shape_ok("curve", mask))

    def test_straight_axis_and_curve_masks_rotate_by_quarter_turns(self):
        fake = road.RoadTemplate(
            "straight4",
            "x",
            ent(1, 0, 0),
            b"",
            "x",
            "test",
            frozenset(("N", "S")),
        )
        self.assertEqual(road.yaw_for_mask(fake, frozenset(("N", "S"))), 0.0)
        self.assertEqual(road.yaw_for_mask(fake, frozenset(("E", "W"))), 90.0)

        curve = road.RoadTemplate(
            "curve",
            "x",
            ent(2, 0, 0),
            b"",
            "x",
            "test",
            frozenset(("E", "N")),
        )
        self.assertEqual(road.yaw_for_mask(curve, frozenset(("W", "S"))), 180.0)

    def test_old_street_system_and_curb_dressing_are_removed(self):
        sidewalk = ent(
            2,
            0,
            0,
            "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Sidewalks\\CS_Sidewalk_Tile_4x4.fpe",
        )
        lamp = ent(
            3,
            0,
            0,
            "Cyberpunk Streets Booster Pack\\Misc\\Sidewalk Misc\\CS_Street_Lamp.fpe",
        )
        building = ent(
            4,
            0,
            0,
            "Cyberpunk Streets Booster Pack\\Buildings\\CS_Wall_01.fpe",
        )
        self.assertTrue(road.strip_for_road_foundation(sidewalk))
        self.assertTrue(road.strip_for_road_foundation(lamp))
        self.assertFalse(road.strip_for_road_foundation(building))


if __name__ == "__main__":
    unittest.main()
