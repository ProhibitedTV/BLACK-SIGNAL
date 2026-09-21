import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_city_mass_compat as compat


class CityMassCompatTests(unittest.TestCase):
    @staticmethod
    def entity(index: int, x: float, z: float, creation_group: int = 0) -> dict:
        return {
            "record_index": index,
            "position": {"x": x, "y": 1000.0, "z": z},
            "staticflag": 1,
            "v319_group_count": 0,
            "creation_of_group_id": creation_group,
        }

    def test_adaptive_clustering_breaks_citywide_chain_into_buildings(self):
        # Four 4-piece buildings. Adjacent buildings are 400 units apart at the
        # closest edge, so the old 525-unit radius chained all 16 pieces into a
        # >2200-unit component that the production filter rejected.
        entities = []
        idx = 1
        for base_x in (0.0, 700.0, 1400.0, 2100.0):
            for dx in (0.0, 100.0, 200.0, 300.0):
                entities.append(self.entity(idx, base_x + dx, 0.0))
                idx += 1

        old = compat._original_cluster_entities(entities, "foreground", 525.0)
        old_valid = [c for c in old if compat._valid_cluster(c, "foreground")]
        self.assertEqual(old_valid, [])

        adaptive = compat._adaptive_cluster_entities(entities, "foreground", 525.0)
        valid = [c for c in adaptive if compat._valid_cluster(c, "foreground")]
        self.assertGreaterEqual(len(valid), 4)
        self.assertEqual(sum(len(c.entities) for c in valid), 16)

    def test_grouped_structural_piece_is_cloneable(self):
        e = self.entity(42, 100.0, 100.0, creation_group=17)
        self.assertTrue(compat._cloneable_city_piece(e))

    def test_entity_one_and_global_group_payload_remain_blocked(self):
        e1 = self.entity(1, 0.0, 0.0)
        self.assertFalse(compat._cloneable_city_piece(e1))
        e2 = self.entity(2, 0.0, 0.0)
        e2["v319_group_count"] = 2
        self.assertFalse(compat._cloneable_city_piece(e2))


if __name__ == "__main__":
    unittest.main()
