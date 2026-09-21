import math
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_city_mass as city


def ent(idx, x, y, z, yaw=0.0, asset='x.fpe'):
    return {
        'record_index': idx,
        'position': {'x': float(x), 'y': float(y), 'z': float(z)},
        'rotation_euler': {'x': 0.0, 'y': float(yaw), 'z': 0.0},
        'asset': asset,
    }


class CityMassTests(unittest.TestCase):
    def test_cluster_entities_keeps_authored_assembly_together(self):
        e = [ent(1, 0, 0, 0), ent(2, 300, 0, 0), ent(3, 5000, 0, 5000)]
        clusters = city.cluster_entities(e, 'foreground', 525.0)
        sizes = sorted(len(c.entities) for c in clusters)
        self.assertEqual(sizes, [1, 2])

    def test_transform_preserves_source_road_relationship(self):
        source = ent(1, 1000, 100, 2000, 0)
        target = ent(2, 5000, 200, 6000, 90)
        p = {'x': 1300.0, 'y': 150.0, 'z': 2200.0}
        x, y, z, delta = city.transform_position(p, source, target)
        self.assertAlmostEqual(delta, 90.0)
        self.assertAlmostEqual(x, 5200.0, places=3)
        self.assertAlmostEqual(z, 5700.0, places=3)
        self.assertAlmostEqual(y, 250.0, places=3)

    def test_background_plan_rotates_whole_stack_about_cluster_center(self):
        a = ent(10, 0, 100, 0, 0)
        b = ent(11, 200, 300, 0, 90)
        c = city.make_cluster([a, b], 'background')
        plan = city.ClonePlan(c, None, None, 1000, 50, 2000, 90, 'skyline')
        x, y, z, yaw = city.plan_entity_transform(plan, a)
        self.assertAlmostEqual(x, c.cx + 1000, places=3)
        self.assertAlmostEqual(z, c.cz + 2000 + 100, places=3)
        self.assertAlmostEqual(y, 150.0, places=3)
        self.assertAlmostEqual(yaw, 90.0, places=3)

    def test_bbox_intersection_padding(self):
        self.assertFalse(city.bbox_intersects((0, 100, 0, 100), (250, 350, 0, 100), 50))
        self.assertTrue(city.bbox_intersects((0, 100, 0, 100), (140, 240, 0, 100), 50))


if __name__ == '__main__':
    unittest.main()
