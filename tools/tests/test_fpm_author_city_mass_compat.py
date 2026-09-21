import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_city_mass_compat as compat


class CityMassCompatTests(unittest.TestCase):
    @staticmethod
    def entity(index: int, x: float, z: float, creation_group: int = 0, asset: str = "x.fpe") -> dict:
        return {
            "record_index": index,
            "position": {"x": x, "y": 1000.0, "z": z},
            "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
            "staticflag": 1,
            "v319_group_count": 0,
            "creation_of_group_id": creation_group,
            "asset": asset,
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

    def test_real_map_ent_relative_paths_are_classified(self):
        road = self.entity(
            2,
            0.0,
            0.0,
            asset=r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_T-Intersect_3.fpe",
        )
        wall = self.entity(
            3,
            0.0,
            0.0,
            asset=r"Cyberpunk Streets Booster Pack\Buildings\CS_Wall_01.fpe",
        )
        storefront = self.entity(
            4,
            0.0,
            0.0,
            asset=r"Cyberpunk Streets Booster Pack\Store Fronts\CS_Store_Front_02_Corner_With_Window.fpe",
        )
        background = self.entity(
            5,
            0.0,
            0.0,
            asset=r"Cyberpunk Streets Booster Pack\Background Buildings\CS_BG_Building_03_Floor.fpe",
        )
        self.assertTrue(compat._is_road(road))
        self.assertTrue(compat._is_foreground_building(wall))
        self.assertTrue(compat._is_foreground_building(storefront))
        self.assertTrue(compat._is_background_building(background))

    def test_dependency_list_entitybank_prefix_is_also_classified(self):
        road = self.entity(
            6,
            0.0,
            0.0,
            asset=r"entitybank\Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight_4X.fpe",
        )
        wall = self.entity(
            7,
            0.0,
            0.0,
            asset=r"entitybank\Cyberpunk Streets Booster Pack\Buildings\CS_Wall_Corner_01.fpe",
        )
        self.assertTrue(compat._is_road(road))
        self.assertTrue(compat._is_foreground_building(wall))


if __name__ == "__main__":
    unittest.main()
