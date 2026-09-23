import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_city_mass_v2 as integrated


ROAD_STRAIGHT4 = (
    "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\"
    "CS_Street_Straight_4X.fpe"
)
BOLLARD = (
    "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\"
    "CS_Street_Crosswalk_Metal_Blocker_Post.fpe"
)
BUILDING = "Cyberpunk Streets Booster Pack\\Buildings\\CS_Wall_01.fpe"


def road(asset: str, record_index: int, x: float, z: float) -> dict:
    return {
        "asset": asset,
        "record_index": record_index,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"y": 0.0},
        "staticflag": 1,
        "v319_group_count": 0,
    }


def building(record_index: int, x: float, z: float) -> dict:
    return {
        "asset": BUILDING,
        "record_index": record_index,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"y": 0.0},
        "staticflag": 1,
        "v319_group_count": 0,
    }


class IntegratedCityMassTests(unittest.TestCase):
    def setUp(self):
        integrated.configure_city_compat()

    def test_recognized_roads_rejects_generic_cs_street_props(self):
        parsed = {
            "entities": [
                road(ROAD_STRAIGHT4, 2, 0.0, 0.0),
                road(BOLLARD, 3, 50.0, 50.0),
            ]
        }
        rows = integrated.recognized_roads(parsed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset"], ROAD_STRAIGHT4)

    def test_bank_extension_is_deterministic_and_reuses_existing_asset(self):
        bank_paths = ["A.fpe"]
        lookup = {"a.fpe": 1}
        self.assertEqual(integrated.ensure_bank_index(bank_paths, lookup, "A.fpe"), 1)
        self.assertEqual(integrated.ensure_bank_index(bank_paths, lookup, "B.fpe"), 2)
        self.assertEqual(integrated.ensure_bank_index(bank_paths, lookup, "B.fpe"), 2)
        self.assertEqual(bank_paths, ["A.fpe", "B.fpe"])

    def test_foreground_assemblies_move_from_donor_to_matching_target_road_family(self):
        donor = {
            "entities": [
                road(ROAD_STRAIGHT4, 10, 0.0, 0.0),
                building(20, 300.0, 0.0),
                building(21, 350.0, 0.0),
                building(22, 300.0, 50.0),
                building(23, 350.0, 50.0),
            ]
        }
        target = {
            "entities": [road(ROAD_STRAIGHT4, 100, 10000.0, 20000.0)]
        }
        plans = integrated.choose_foreground_plans(donor, target, 1)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].anchor_source["record_index"], 10)
        self.assertEqual(plans[0].anchor_target["record_index"], 100)
        self.assertEqual(plans[0].label, "streetwall-1")


if __name__ == "__main__":
    unittest.main()
