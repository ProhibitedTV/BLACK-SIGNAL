import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network as roads


class RoadNetworkTests(unittest.TestCase):
    def test_seven_by_seven_uses_every_road_kind(self):
        plan = roads.plan_relative_network(7)
        kinds = {p.kind for p in plan}
        self.assertEqual(kinds, {"fourway", "tee", "curve", "straight4", "straight2"})
        self.assertEqual(sum(1 for p in plan if p.kind == "curve"), 4)
        self.assertGreater(sum(1 for p in plan if p.kind == "tee"), 0)
        self.assertGreater(sum(1 for p in plan if p.kind == "fourway"), 0)
        self.assertGreater(sum(1 for p in plan if p.kind == "straight4"), 100)
        self.assertGreater(sum(1 for p in plan if p.kind == "straight2"), 0)

    def test_node_connection_masks_match_topology(self):
        kind, mask = roads.node_mask(0, 0, 7)
        self.assertEqual(kind, "curve")
        self.assertEqual(mask, frozenset(("E", "N")))

        kind, mask = roads.node_mask(3, 0, 7)
        self.assertEqual(kind, "tee")
        self.assertEqual(mask, frozenset(("E", "W", "N")))

        kind, mask = roads.node_mask(3, 3, 7)
        self.assertEqual(kind, "fourway")
        self.assertEqual(mask, frozenset(("N", "E", "S", "W")))

    def test_span_patterns_preserve_1800_node_spacing(self):
        plan = roads.plan_relative_network(5)
        # Horizontal pieces for the first span along z=-3600 must stay between
        # the two node centers at x=-3600 and x=-1800.
        span = [p for p in plan if p.note == "h-0-0"]
        xs = sorted(p.x for p in span)
        self.assertTrue(all(-3600.0 < x < -1800.0 for x in xs))
        self.assertIn(len(xs), (3, 4))

    def test_grid_size_validation(self):
        with self.assertRaises(ValueError):
            roads.plan_relative_network(4)
        with self.assertRaises(ValueError):
            roads.plan_relative_network(6)


if __name__ == "__main__":
    unittest.main()
