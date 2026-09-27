import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v9_2 as v92


def entity(asset: str, x: float, z: float, yaw: float, record_index: int) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": record_index,
    }


def by_role(plan):
    out = {}
    for placement in plan:
        out.setdefault(placement.role, []).append(placement)
    return out


class SemanticRoadDressingV92Tests(unittest.TestCase):
    def test_manual_reference_transforms_are_promoted_symmetrically(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        south = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 2)
        north = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, 500.0, 0.0, 3)
        plan = v92.plan_semantic_dressing({"entities": [fourway, south, north]})
        roles = by_role(plan)

        self.assertEqual(len(roles["road_center_yellow"]), 4)
        self.assertEqual(len(roles["crosswalk"]), 4)
        self.assertEqual(len(roles[v92.ARROW_ROLE]), 2)
        self.assertEqual(len(roles[v92.SIDEWALK_CORNER_ROLE]), 4)

        self.assertTrue(all(abs((p.ry or 0.0) % 360.0) < 0.01 for p in roles["road_center_yellow"]))

        crosswalks = {(round(p.x), round(p.z), round((p.ry or 0.0) % 360.0)) for p in roles["crosswalk"]}
        self.assertEqual(
            crosswalks,
            {
                (95, 200, 0),
                (200, -95, 90),
                (-95, -200, 180),
                (-200, 95, 270),
            },
        )

        corners = {(round(p.x), round(p.z), round((p.ry or 0.0) % 360.0)) for p in roles[v92.SIDEWALK_CORNER_ROLE]}
        self.assertEqual(
            corners,
            {
                (-300, 300, 270),
                (300, 300, 0),
                (300, -300, 90),
                (-300, -300, 180),
            },
        )

        arrows = {(round(p.x), round(p.z), round((p.ry or 0.0) % 360.0)) for p in roles[v92.ARROW_ROLE]}
        self.assertIn((100, -320, 0), arrows)
        self.assertIn((-100, 320, 180), arrows)

    def test_reference_rules_rotate_with_road_and_junction_yaw(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 1000.0, 1000.0, 90.0, 10)
        plan = v92.plan_semantic_dressing({"entities": [fourway]})
        roles = by_role(plan)

        crosswalks = {(round(p.x), round(p.z), round((p.ry or 0.0) % 360.0)) for p in roles["crosswalk"]}
        self.assertEqual(
            crosswalks,
            {
                (1200, 905, 90),
                (905, 800, 180),
                (800, 1095, 270),
                (1095, 1200, 0),
            },
        )

    def test_lamps_use_measured_curb_strip_and_six_module_cadence(self) -> None:
        straights = [
            entity(roads.ROAD_SPECS["straight4"]["path"], float(i * 400), 0.0, 90.0, i + 1)
            for i in range(12)
        ]
        plan = v92.plan_semantic_dressing({"entities": straights})
        lamps = [p for p in plan if p.role == "street_lamp"]
        lights = [p for p in plan if p.role == "street_dynamic_light"]
        self.assertEqual(v92.LAMP_STRIDE, 6)
        self.assertEqual(v92.LAMP_EDGE_X, 270.0)
        self.assertEqual(len(lamps), 2)
        self.assertEqual(len(lights), 2)
        self.assertEqual(len([p for p in plan if p.role == "road_center_yellow"]), 24)
        # yaw=90 rotates local +/-X into world +/-Z, so each lamp sits 270 units
        # off the road centerline on the measured curb strip.
        self.assertTrue(all(abs(abs(p.z) - 270.0) < 0.01 for p in lamps))

    def test_tee_gets_no_unproven_sidewalk_or_marking_grammar(self) -> None:
        tee = entity(roads.ROAD_SPECS["tee"]["path"], 0.0, 0.0, 0.0, 20)
        approach = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 21)
        plan = v92.plan_semantic_dressing({"entities": [tee, approach]})
        self.assertFalse(any(p.role == v92.ARROW_ROLE for p in plan))
        self.assertFalse(any(p.role == "crosswalk" for p in plan))
        self.assertFalse(any(p.role == v92.SIDEWALK_CORNER_ROLE for p in plan))


if __name__ == "__main__":
    unittest.main()
