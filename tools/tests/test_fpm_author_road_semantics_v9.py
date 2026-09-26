import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v9 as v9


def entity(asset: str, x: float, z: float, yaw: float, record_index: int) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": record_index,
    }


class SemanticRoadDressingV9Tests(unittest.TestCase):
    def test_fourway_dressing_is_semantic_and_lit(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        south_approach = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 2)
        east_approach = entity(roads.ROAD_SPECS["straight4"]["path"], 500.0, 0.0, 90.0, 3)
        plan = v9.plan_semantic_dressing(
            {"entities": [fourway, south_approach, east_approach]}
        )

        by_role: dict[str, list] = {}
        for placement in plan:
            by_role.setdefault(placement.role, []).append(placement)

        self.assertEqual(len(by_role.get("road_center_yellow", [])), 2)
        self.assertEqual(len(by_role.get("crosswalk", [])), 4)
        self.assertEqual(len(by_role.get(v9.ARROW_ROLE, [])), 2)
        self.assertEqual(len(by_role.get("street_lamp", [])), 1)
        self.assertEqual(len(by_role.get("street_dynamic_light", [])), 1)

        # Center markings are authored from the target road pivots, not copied from
        # arbitrary donor-local offsets.
        centers = by_role["road_center_yellow"]
        self.assertTrue(any(abs(p.x - 0.0) < 0.01 and abs(p.z + 500.0) < 0.01 for p in centers))
        self.assertTrue(any(abs(p.x - 500.0) < 0.01 and abs(p.z - 0.0) < 0.01 for p in centers))

        # Every generated arrow is explicitly tied to a four-way approach.
        self.assertTrue(all("4-way" in p.note for p in by_role[v9.ARROW_ROLE]))

        lamp = by_role["street_lamp"][0]
        light = by_role["street_dynamic_light"][0]
        self.assertAlmostEqual(lamp.x, light.x)
        self.assertAlmostEqual(lamp.z, light.z)
        self.assertAlmostEqual(lamp.y + v9.LAMP_LIGHT_Y, light.y)

    def test_tee_only_approach_gets_no_guessed_arrow(self) -> None:
        tee = entity(roads.ROAD_SPECS["tee"]["path"], 0.0, 0.0, 0.0, 10)
        approach = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 11)
        plan = v9.plan_semantic_dressing({"entities": [tee, approach]})
        self.assertFalse(any(p.role == v9.ARROW_ROLE for p in plan))
        self.assertFalse(any(p.role == "crosswalk" for p in plan))

    def test_off_axis_straight_cannot_steal_fourway_arrow(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 20)
        # Within radial search distance but not on this straight's longitudinal axis.
        off_axis = entity(roads.ROAD_SPECS["straight4"]["path"], 500.0, 300.0, 0.0, 21)
        plan = v9.plan_semantic_dressing({"entities": [fourway, off_axis]})
        self.assertFalse(any(p.role == v9.ARROW_ROLE for p in plan))


if __name__ == "__main__":
    unittest.main()
