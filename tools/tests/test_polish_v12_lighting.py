import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import fpm_polish_city_v12 as base
import fpm_polish_city_v12_lighting as lighting


class LightingPassTests(unittest.TestCase):
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
        ) = lighting.plan(cls.parsed, cls.old, cls.measured)

    def test_grouped_source_prefix_remains_identity_stable(self):
        base.assert_grouped_source_prefix(self.parsed, self.rows)
        source_count = len(self.parsed["entities"])
        self.assertEqual(
            [r.get("source_index") for r in self.rows[: source_count - 1]],
            list(range(2, source_count + 1)),
        )

    def test_native_review_tents_stay_removed(self):
        appended = [r for r in self.rows if r.get("source_index") is None]
        self.assertFalse(any(r.get("group") == "sheltered-life" for r in appended))

    def test_neon_is_sparse_and_surface_locked(self):
        neons = [r for r in self.rows if r.get("group") == "lighting-neon"]
        self.assertEqual(len(neons), 4)
        by_name = {p["name"]: p for p in self.heroes}
        neon = self.measured[lighting.NEON_ASSET]
        wall = self.measured["CS_Wall_01"]
        self.assertLess(neon["size"][2], 0.05)
        self.assertAlmostEqual(abs(abs(neon["min"][2]) - abs(wall["min"][2])), 1.0, delta=0.5)
        for row in neons:
            p = by_name[row["parcel"]]
            self.assertIsNone(row.get("source_index"))
            self.assertEqual(row["x"], p["x"] + p["width"] / 2)
            self.assertEqual(row["mount_gap"], 1.0)
            if row["mount_side"] == "north":
                self.assertEqual(row["z"], p["z"])
                self.assertEqual(row["yaw"], 0)
            else:
                self.assertEqual(row["z"], p["z"] + p["depth"])
                self.assertEqual(row["yaw"], 180)
            self.assertGreaterEqual(row["x"] + neon["min"][0], p["x"] + 20)
            self.assertLessEqual(row["x"] + neon["max"][0], p["x"] + p["width"] - 20)
            self.assertLessEqual(
                row["y"] + neon["max"][1],
                p["ground"] + p["floors"] * 200 - 20,
            )

    def test_one_new_practical_pool_per_hero(self):
        lights = [r for r in self.rows if r.get("group") == "lighting-practical"]
        self.assertEqual(len(lights), len(self.heroes))
        self.assertEqual({r["parcel"] for r in lights}, {p["name"] for p in self.heroes})
        self.assertTrue(all(r.get("source_index") is None for r in lights))

    def test_lighting_additions_have_unique_transforms(self):
        additions = [
            r
            for r in self.rows
            if r.get("group") in ("lighting-neon", "lighting-practical")
        ]
        signatures = [base.signature(r) for r in additions]
        self.assertEqual(len(signatures), len(set(signatures)))


if __name__ == "__main__":
    unittest.main()
