import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v3 as road


def ent(asset: str) -> dict:
    return {"asset": asset}


class UniformRoadNetworkTests(unittest.TestCase):
    def test_main_grid_uses_only_uniform_full_width_road_grammar(self):
        plan = road.plan_uniform_network(7)
        kinds = {p.kind for p in plan}
        self.assertEqual(kinds, {"fourway", "tee", "curve", "straight4"})
        self.assertNotIn("straight2", kinds)
        self.assertNotIn("straight1", kinds)
        self.assertNotIn("quarter", kinds)

    def test_every_block_span_is_three_straight4_modules(self):
        plan = road.plan_uniform_network(5)
        horizontal = [
            p for p in plan
            if p.note == "avenue-h-0-0"
        ]
        self.assertEqual([p.kind for p in horizontal], ["straight4"] * 3)
        self.assertEqual([p.x for p in horizontal], [-3100.0, -2700.0, -2300.0])

    def test_clean_foundation_removes_old_pack_geometry_and_trees(self):
        self.assertTrue(
            road.strip_for_clean_road_foundation(
                ent("Cyberpunk Streets Booster Pack\\Buildings\\CS_Wall_01.fpe")
            )
        )
        self.assertTrue(
            road.strip_for_clean_road_foundation(
                ent("Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe")
            )
        )
        self.assertTrue(
            road.strip_for_clean_road_foundation(
                ent("Jungle Collection\\Trees\\Broad Tree.fpe")
            )
        )
        self.assertFalse(
            road.strip_for_clean_road_foundation(ent("_markers\\player start.fpe"))
        )

    def test_grid_has_consistent_1800_unit_nodes(self):
        plan = road.plan_uniform_network(7)
        nodes = [p for p in plan if p.note.startswith("node-")]
        xs = sorted({p.x for p in nodes})
        self.assertTrue(all(abs((b - a) - 1800.0) < 0.001 for a, b in zip(xs, xs[1:])))


if __name__ == "__main__":
    unittest.main()
