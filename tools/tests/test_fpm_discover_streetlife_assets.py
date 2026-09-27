import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
MODULE_PATH = TOOLS / "discover-streetlife-assets.py"
SPEC = importlib.util.spec_from_file_location("discover_streetlife_assets", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
streetlife = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = streetlife
SPEC.loader.exec_module(streetlife)


class StreetLifeDiscoveryTests(unittest.TestCase):
    def test_street_infrastructure_is_not_a_tree_candidate(self) -> None:
        self.assertFalse(streetlife._is_tree_candidate(Path("CS_Street_Electrical_Pole_01.fpe")))
        self.assertFalse(streetlife._is_tree_candidate(Path("CS_Street_Lamp.fpe")))
        self.assertTrue(streetlife._is_tree_candidate(Path("Small_Tree_01.fpe")))
        self.assertTrue(streetlife._is_tree_candidate(Path("Street_Tree_01.fpe")))

    def test_pick_tree_rejects_non_tree_rows_even_if_dimensions_are_ideal(self) -> None:
        rows = [
            {
                "asset": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Street_Electrical_Pole_01.fpe",
                "basename": "CS_Street_Electrical_Pole_01.fpe",
                "size": [28.0, 550.0, 28.0],
            },
            {
                "asset": r"Nature\Trees\Small_Tree_01.fpe",
                "basename": "Small_Tree_01.fpe",
                "size": [180.0, 520.0, 180.0],
            },
        ]
        picked = streetlife._pick_tree(rows)
        self.assertEqual(picked["basename"], "Small_Tree_01.fpe")

    def test_pick_tree_fails_closed_when_only_street_props_are_supplied(self) -> None:
        with self.assertRaises(ValueError):
            streetlife._pick_tree([
                {
                    "asset": r"Cyberpunk Streets Booster Pack\Misc\CS_Street_Lamp.fpe",
                    "basename": "CS_Street_Lamp.fpe",
                    "size": [40.0, 550.0, 40.0],
                }
            ])


if __name__ == "__main__":
    unittest.main()
