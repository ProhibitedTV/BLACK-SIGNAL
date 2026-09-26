import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v9_1 as v91


def entity(asset: str, x: float, z: float, yaw: float, record_index: int) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": record_index,
    }


class SemanticRoadDressingV91Tests(unittest.TestCase):
    def test_visual_tuning_uses_two_center_marks_and_inset_crosswalks(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        south = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 2)
        east = entity(roads.ROAD_SPECS["straight4"]["path"], 500.0, 0.0, 90.0, 3)
        plan = v91.plan_semantic_dressing({"entities": [fourway, south, east]})

        by_role: dict[str, list] = {}
        for placement in plan:
            by_role.setdefault(placement.role, []).append(placement)

        self.assertEqual(len(by_role.get("road_center_yellow", [])), 4)
        self.assertEqual(len(by_role.get("crosswalk", [])), 4)
        self.assertEqual(len(by_role.get(v91.ARROW_ROLE, [])), 2)
        self.assertEqual(len(by_role.get("street_lamp", [])), 1)
        self.assertEqual(len(by_role.get("street_dynamic_light", [])), 1)

        south_centers = [
            p for p in by_role["road_center_yellow"] if abs(p.x) < 0.01 and p.z < 0.0
        ]
        self.assertEqual(sorted(round(p.z, 1) for p in south_centers), [-600.0, -400.0])

        crosswalks = by_role["crosswalk"]
        self.assertTrue(any(abs(p.x) < 0.01 and abs(p.z - v91.CROSSWALK_EDGE) < 0.01 for p in crosswalks))
        self.assertTrue(any(abs(p.z) < 0.01 and abs(p.x - v91.CROSSWALK_EDGE) < 0.01 for p in crosswalks))

        lamp = by_role["street_lamp"][0]
        light = by_role["street_dynamic_light"][0]
        self.assertAlmostEqual(abs(lamp.x), v91.LAMP_EDGE_X)
        self.assertAlmostEqual(lamp.x, light.x)
        self.assertAlmostEqual(lamp.z, light.z)
        self.assertAlmostEqual(lamp.y + v91.LAMP_LIGHT_Y, light.y)

    def test_lamp_cadence_is_one_per_four_straights(self) -> None:
        straights = [
            entity(
                roads.ROAD_SPECS["straight4"]["path"],
                float(index * 400),
                0.0,
                90.0,
                index + 1,
            )
            for index in range(8)
        ]
        plan = v91.plan_semantic_dressing({"entities": straights})
        lamps = [p for p in plan if p.role == "street_lamp"]
        lights = [p for p in plan if p.role == "street_dynamic_light"]
        self.assertEqual(len(lamps), 2)
        self.assertEqual(len(lights), 2)
        self.assertEqual(len([p for p in plan if p.role == "road_center_yellow"]), 16)

    def test_tee_still_gets_no_guessed_crosswalk_or_arrow(self) -> None:
        tee = entity(roads.ROAD_SPECS["tee"]["path"], 0.0, 0.0, 0.0, 20)
        approach = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 21)
        plan = v91.plan_semantic_dressing({"entities": [tee, approach]})
        self.assertFalse(any(p.role == v91.ARROW_ROLE for p in plan))
        self.assertFalse(any(p.role == "crosswalk" for p in plan))


if __name__ == "__main__":
    unittest.main()
