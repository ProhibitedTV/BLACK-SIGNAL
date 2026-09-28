import json
import math
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import fpm_polish_city_v12 as base
import fpm_polish_city_v12_elevated as elevated


class ElevatedPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "gameguru/references/District 12 - manual polish.fpm"
        if source.stat().st_size < 1_000_000:
            raise unittest.SkipTest("Materialized manual reference required")
        _, _, cls.parsed = base.load_scene(source)
        cls.old = json.loads((ROOT / "gameguru/buildplans/district12-v11-layout.json").read_text())
        cls.measured = json.loads((ROOT / "docs/cybercity-kit-measurements.json").read_text())
        cls.measured.update(json.loads((ROOT / "docs/city-polish-measurements.json").read_text()))
        (
            cls.rows,
            cls.parcels,
            cls.changes,
            cls.protected,
            cls.heroes,
        ) = elevated.plan(cls.parsed, cls.old, cls.measured)
        cls.by_name = {p["name"]: p for p in cls.parcels}
        cls.elevated_rows = [r for r in cls.rows if r.get("group", "").startswith("elevated-")]

    def test_grouped_source_prefix_remains_identity_stable(self):
        base.assert_grouped_source_prefix(self.parsed, self.rows)
        source_count = len(self.parsed["entities"])
        self.assertEqual(
            [r.get("source_index") for r in self.rows[: source_count - 1]],
            list(range(2, source_count + 1)),
        )
        self.assertTrue(all(r.get("source_index") is None for r in self.elevated_rows))

    def test_pass_is_bounded_and_keeps_previous_lighting(self):
        self.assertEqual(len(self.elevated_rows), 150)
        self.assertEqual(sum(r.get("group") == "lighting-neon" for r in self.rows), 4)
        self.assertEqual(sum(r.get("group") == "lighting-practical" for r in self.rows), 6)
        self.assertFalse(any(r.get("group") == "sheltered-life" for r in self.rows if r.get("source_index") is None))

    def test_second_tier_galleries_are_supported_not_floating(self):
        deck = self.measured[elevated.DECK_ASSET]
        support = self.measured[elevated.SUPPORT_ASSET]
        for name in elevated.TIER2_NAMES:
            p = self.by_name[name]
            rows = [r for r in self.elevated_rows if r.get("parcel") == name]
            groups = Counter(r["group"] for r in rows)
            self.assertEqual(groups["elevated-tier2-support"], 2)
            self.assertEqual(groups["elevated-tier2-deck"], 2)
            self.assertEqual(groups["elevated-tier2-rail"], 8)
            self.assertEqual(groups["elevated-tier2-light"], 1)

            target = p["ground"] + elevated.TIER2_HEIGHT
            for row in rows:
                if row["group"] == "elevated-tier2-deck":
                    self.assertAlmostEqual(row["y"] + deck["max"][1], target, delta=0.05)
                    self.assertLessEqual(row["y"] + deck["min"][1], target)
                    self.assertEqual(row["x"], p["x"] - 120)
                elif row["group"] == "elevated-tier2-support":
                    self.assertAlmostEqual(row["y"] + support["max"][1], target, delta=0.05)
                elif row["group"] == "elevated-tier2-rail":
                    self.assertAlmostEqual(row["y"], target + 0.1, delta=0.01)

    def test_skybridges_exactly_contact_saved_facade_planes(self):
        deck = self.measured[elevated.DECK_ASSET]
        tile_length = deck["size"][0]
        for left_name, right_name in elevated.SKYBRIDGE_PAIRS:
            left, right = self.by_name[left_name], self.by_name[right_name]
            if left["x"] > right["x"]:
                left, right = right, left
            bridge_name = f"{left['name']}--{right['name']}"
            rows = [r for r in self.elevated_rows if r.get("bridge") == bridge_name]
            decks = [r for r in rows if r["group"] == "elevated-skybridge-deck"]
            rails = [r for r in rows if r["group"] == "elevated-skybridge-rail"]
            lights = [r for r in rows if r["group"] == "elevated-skybridge-light"]
            self.assertEqual(len(decks), 5)
            self.assertEqual(len(rails), 10)
            self.assertEqual(len(lights), 2)

            left_plane = left["x"] + left["width"]
            right_plane = right["x"]
            first = min(decks, key=lambda r: r["x"])
            last = max(decks, key=lambda r: r["x"])
            first_left_edge = first["x"] - tile_length / 2
            last_right_edge = last["x"] + tile_length / 2
            self.assertAlmostEqual(first_left_edge, left_plane, delta=0.05)
            self.assertAlmostEqual(last_right_edge, right_plane, delta=0.05)

            target = left["ground"] + elevated.SKYBRIDGE_HEIGHT
            for row in decks:
                self.assertAlmostEqual(row["y"] + deck["max"][1], target, delta=0.05)
                self.assertEqual(row["scale"], [1.0, 1.0, elevated.BRIDGE_WIDTH_SCALE])
            self.assertGreater(elevated.SKYBRIDGE_HEIGHT, 400)

    def test_rooftop_terraces_sit_on_roof_and_keep_camera_gap(self):
        for name in elevated.ROOFTOP_NAMES:
            p = self.by_name[name]
            roof = p["ground"] + p["floors"] * 200
            rows = [r for r in self.elevated_rows if r.get("parcel") == name]
            roof_rails = [r for r in rows if r["group"] == "elevated-rooftop-rail"]
            roof_lights = [r for r in rows if r["group"] == "elevated-rooftop-light"]
            self.assertEqual(len(roof_rails), 14)
            self.assertEqual(len(roof_lights), 2)
            self.assertEqual(sum(r["edge"] == "north" for r in roof_rails), 4)
            self.assertEqual(sum(r["edge"] == "south" for r in roof_rails), 2)
            self.assertEqual(sum(r["edge"] == "west" for r in roof_rails), 4)
            self.assertEqual(sum(r["edge"] == "east" for r in roof_rails), 4)
            for row in roof_rails:
                self.assertAlmostEqual(row["y"], roof + 0.1, delta=0.01)
                self.assertAlmostEqual(row["roof_plane"], roof, delta=0.01)
                self.assertGreaterEqual(row["x"], p["x"])
                self.assertLessEqual(row["x"], p["x"] + p["width"])
                self.assertGreaterEqual(row["z"], p["z"])
                self.assertLessEqual(row["z"], p["z"] + p["depth"])

    def test_elevated_additions_have_unique_transforms(self):
        signatures = [base.signature(r) for r in self.elevated_rows]
        self.assertEqual(len(signatures), len(set(signatures)))


if __name__ == "__main__":
    unittest.main()
