import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v2 as roads
import fpm_author_streetlife_v10_4 as v104
from fpm_inspect import FpmError


def entity(asset: str, x: float, z: float, yaw: float, record_index: int) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": 100.0, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": record_index,
    }


class StreetLifeV104Tests(unittest.TestCase):
    def test_planter_tree_pairs_and_accent_lights_are_sparse_and_outside_asphalt(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 0.0, 0.0, 0.0, 1)
        rows = v104._streetlife_dressing({"entities": [fourway]})
        counts = {}
        for row in rows:
            counts[row.role] = counts.get(row.role, 0) + 1
            self.assertFalse(abs(row.x) <= 300.0 and abs(row.z) <= 300.0)

        self.assertEqual(counts, v104.EXPECTED_STREETLIFE_COUNTS)
        planters = {(round(p.x, 2), round(p.z, 2)) for p in rows if p.role == "city_planter"}
        trees = {(round(p.x, 2), round(p.z, 2)) for p in rows if p.role == "city_tree"}
        self.assertEqual(planters, trees)
        self.assertEqual(len(planters), 8)

    def test_layout_rotates_with_central_junction(self) -> None:
        fourway = entity(roads.ROAD_SPECS["fourway"]["path"], 1000.0, 2000.0, 90.0, 10)
        rows = v104._streetlife_dressing({"entities": [fourway]})
        planters = [p for p in rows if p.role == "city_planter"]
        self.assertEqual(len(planters), 8)
        # Local (820,410) rotated by 90 degrees -> world (+410,-820) from the junction.
        self.assertTrue(any(abs(p.x - 1410.0) < 0.01 and abs(p.z - 1180.0) < 0.01 for p in planters))

    def test_discovery_report_paths_are_fail_closed(self) -> None:
        good = {
            "policy": "v10.4-installed-measured-streetlife-assets",
            "planter": {"asset": r"Cyberpunk Streets Booster Pack\Misc\CS_Planter_01.fpe"},
            "tree": {"asset": r"Nature\Trees\Small_Tree_01.fpe"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assets.json"
            path.write_text(json.dumps(good), encoding="utf-8")
            config = v104.load_asset_config(path)
            self.assertEqual(config["city_planter"]["basename"], "CS_Planter_01.fpe")
            self.assertEqual(config["city_tree"]["basename"], "Small_Tree_01.fpe")

            good["tree"]["asset"] = r"..\outside.fpe"
            path.write_text(json.dumps(good), encoding="utf-8")
            with self.assertRaises(FpmError):
                v104.load_asset_config(path)


if __name__ == "__main__":
    unittest.main()
