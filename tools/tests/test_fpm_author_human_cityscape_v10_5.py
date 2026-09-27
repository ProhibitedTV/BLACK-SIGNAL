import sys
import unittest
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_human_cityscape_v10_5 as v105
import fpm_author_road_network_v2 as roads


def entity(asset: str, x: float, z: float, yaw: float, record_index: int) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": record_index,
    }


class HumanCityscapeV105Tests(unittest.TestCase):
    def test_one_fourway_reproduces_human_corner_and_rotates_all_quadrants(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 10)
        plan = v105.plan_human_cityscape({"entities": [fourway]})
        counts = Counter(p.role for p in plan)
        self.assertEqual(counts, Counter(v105.human_role_counts(1)))

        def rows(role: str):
            return [p for p in plan if p.role == role]

        # Exact hand-authored NW reference is retained.
        self.assertTrue(any(
            abs(p.x + 350.0) < 0.01 and abs(p.z - 350.0) < 0.01 and abs(p.ry - 90.0) < 0.01
            for p in rows("human_planter")
        ))
        self.assertTrue(any(
            abs(p.x + 220.0) < 0.01 and abs(p.z - 290.0) < 0.01 and abs(p.ry - 270.0) < 0.01
            for p in rows("human_stop_light")
        ))
        self.assertTrue(any(
            abs(p.x + 245.0) < 0.01 and abs(p.z - 245.0) < 0.01
            for p in rows("human_trash_can")
        ))
        self.assertTrue(any(
            abs(p.x + 215.0) < 0.01 and abs(p.z - 500.0) < 0.01
            for p in rows("human_sidewalk_light")
        ))

        # The same corner grammar is rotated to all four quadrants.
        planter_xy = {(round(p.x), round(p.z)) for p in rows("human_planter")}
        self.assertEqual(
            planter_xy,
            {(-350, 350), (350, 350), (350, -350), (-350, -350)},
        )
        self.assertEqual(len(rows("human_sidewalk_light")), 16)
        self.assertEqual(len(rows("human_bench")), 1)

    def test_junction_yaw_rotates_the_entire_human_grammar(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 1000.0, 2000.0, 90.0, 11)
        plan = v105.plan_human_cityscape({"entities": [fourway]})
        planters = [p for p in plan if p.role == "human_planter"]
        # Local NW (-350,+350) with a 90-degree junction yaw -> world (+350,+350).
        self.assertTrue(any(
            abs(p.x - 1350.0) < 0.01 and abs(p.z - 2350.0) < 0.01
            for p in planters
        ))

    def test_bench_corner_varies_deterministically_between_junctions(self) -> None:
        a = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        b = entity(roads.ROAD_SPECS["fourway"]["path"], 1800.0, 0.0, 0.0, 2)
        plan = v105.plan_human_cityscape({"entities": [b, a]})
        benches = [p for p in plan if p.role == "human_bench"]
        self.assertEqual(len(benches), 2)
        self.assertNotEqual(
            (round(benches[0].x), round(benches[0].z)),
            (round(benches[1].x - 1800.0), round(benches[1].z)),
        )

    def test_expected_citywide_counts_fit_semantic_budget(self) -> None:
        counts = v105.human_role_counts(25)
        self.assertEqual(counts["human_planter"], 100)
        self.assertEqual(counts["human_tree"], 100)
        self.assertEqual(counts["human_stop_light"], 100)
        self.assertEqual(counts["human_trash_can"], 100)
        self.assertEqual(counts["human_sidewalk_light"], 400)
        self.assertEqual(counts["human_bench"], 25)
        self.assertEqual(sum(counts.values()), 825)


if __name__ == "__main__":
    unittest.main()
