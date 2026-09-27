import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v10_3 as v103


def entity(asset: str, x: float, z: float, yaw: float, record_index: int) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": record_index,
    }


class StreetLevelV103Tests(unittest.TestCase):
    def test_hero_block_dressing_has_small_controlled_counts(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        west = entity(roads.ROAD_SPECS["straight4"]["path"], -500.0, 0.0, 90.0, 2)
        east = entity(roads.ROAD_SPECS["straight4"]["path"], 500.0, 0.0, 90.0, 3)
        south = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 4)
        north = entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, 500.0, 0.0, 5)
        plan = v103._hero_block_dressing({"entities": [fourway, west, east, south, north]})

        counts = {}
        for placement in plan:
            counts[placement.role] = counts.get(placement.role, 0) + 1
            self.assertIn("v10.3 hero-block controlled", placement.note)

        self.assertEqual(counts, v103.EXPECTED_STREET_LEVEL_COUNTS)
        self.assertEqual(len(plan), sum(v103.EXPECTED_STREET_LEVEL_COUNTS.values()))

    def test_every_controlled_prop_stays_outside_central_asphalt_envelope(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        plan = v103._hero_block_dressing({"entities": [fourway]})
        # Measured 4-way is 600x600, so at least one horizontal coordinate must be
        # beyond +/-300 for every sidewalk/street-level placement.
        self.assertTrue(all(max(abs(p.x), abs(p.z)) > 300.0 for p in plan))

    def test_center_selection_prefers_network_median_fourway(self) -> None:
        rows = [
            entity(roads.ROAD_SPECS["fourway"]["path"], -1800.0, 0.0, 0.0, 1),
            entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 2),
            entity(roads.ROAD_SPECS["fourway"]["path"], 1800.0, 0.0, 0.0, 3),
            entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, -500.0, 0.0, 4),
            entity(roads.ROAD_SPECS["straight4"]["path"], 0.0, 500.0, 0.0, 5),
        ]
        self.assertEqual(v103._central_fourway({"entities": rows})["record_index"], 2)


if __name__ == "__main__":
    unittest.main()
