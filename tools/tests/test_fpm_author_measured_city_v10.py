import copy
import json
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_measured_city_v10 as v10
import fpm_author_road_network_v2 as roads


def road(kind: str, x: float, z: float, record_index: int):
    return {
        "asset": roads.ROAD_SPECS[kind]["path"],
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
        "record_index": record_index,
    }


class MeasuredCityV10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_measured = json.loads(
            (Path(__file__).resolve().parents[2] / "docs/cybercity-kit-measurements.json").read_text()
        )
        # CI cannot inspect the user's commercial DLC.  Use the proven wall-corner
        # envelope as a synthetic test carrier; production measurements are generated
        # live by measure-cybercity-kit.py before the city stage.
        cls.measured = copy.deepcopy(cls.base_measured)
        for name in v10.STOREFRONT_ASSETS:
            cls.measured[name] = copy.deepcopy(cls.base_measured["CS_Wall_Corner_01"])
            cls.measured[name]["asset"] = f"Cyberpunk Streets Booster Pack\\Store Fronts\\{name}.fpe"

    def test_reuses_calibrated_shells_but_not_competing_road_or_lamp_ownership(self):
        rows = v10.measured_additions(self.measured)
        assets = {row["asset"] for row in rows}
        groups = {row["group"] for row in rows}
        self.assertNotIn("street", groups)
        self.assertNotIn("furniture", groups)
        self.assertNotIn("CS_Sidewalk_Corner1_DropCurb", assets)
        self.assertIn("CS_Roof_Tile_2x2", assets)
        self.assertIn("CS_Sidewalk_Straight_Edge", assets)
        self.assertIn("CS_Sidewalk_Tile_4x4", assets)
        self.assertTrue(set(v10.STOREFRONT_ASSETS).issubset(assets))

    def test_storefront_wrap_replaces_all_blank_ground_floor_corners(self):
        rows = v10.measured_additions(self.measured)
        shops = [row for row in rows if row["asset"] in v10.STOREFRONT_ASSETS]
        self.assertEqual(len(shops), len(v10.HERO_GROUPS) * v10.STOREFRONTS_PER_BUILDING)
        self.assertTrue(all(abs(float(row["y"]) - v10.GROUND_FLOOR_Y) < 0.01 for row in shops))
        self.assertFalse(
            any(
                row["group"] in v10.HERO_GROUPS
                and row["asset"] == "CS_Wall_Corner_01"
                and abs(float(row["y"]) - v10.GROUND_FLOOR_Y) < 0.01
                for row in rows
            )
        )

    def test_missing_live_storefront_measurement_fails_closed(self):
        with self.assertRaisesRegex(Exception, "Measured storefront geometry is missing"):
            v10.measured_additions(self.base_measured)

    def test_measured_additions_keep_all_four_complete_building_sets(self):
        rows = v10.measured_additions(self.measured)
        groups = {row["group"] for row in rows}
        self.assertTrue(
            {"Vale Exchange", "Municipal Annex", "Service Works", "Signal House"}.issubset(groups)
        )
        roofs = [row for row in rows if row["asset"] == "CS_Roof_Tile_2x2"]
        self.assertEqual(len(roofs), 56)

    def test_central_fourway_is_selected_by_network_median(self):
        rows = [
            road("fourway", -1800.0, 0.0, 1),
            road("fourway", 0.0, 0.0, 2),
            road("fourway", 1800.0, 0.0, 3),
            road("straight4", 0.0, -500.0, 4),
            road("straight4", 0.0, 500.0, 5),
        ]
        self.assertEqual(v10.central_fourway(rows)["record_index"], 2)

    def test_building_intrusion_against_measured_road_is_rejected(self):
        target = [road("fourway", 0.0, 0.0, 1)]
        bad = [
            {
                "asset": "CS_Wall_Corner_01",
                "x": 0.0,
                "y": 110.0,
                "z": 0.0,
                "yaw": 0.0,
                "group": "Vale Exchange",
            }
        ]
        with self.assertRaisesRegex(Exception, "intersects validated road"):
            v10.validate_world_plan(bad, target, self.measured)


if __name__ == "__main__":
    unittest.main()
