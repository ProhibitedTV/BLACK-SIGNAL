import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import fpm_polish_city_v12 as polish


class PolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "gameguru/references/District 12 - manual polish.fpm"
        if source.stat().st_size < 1_000_000:
            raise unittest.SkipTest("Materialized manual reference required")
        cls.data, _, cls.source = polish.load_scene(source)
        cls.old = json.loads((ROOT / "gameguru/buildplans/district12-v11-layout.json").read_text())
        cls.m = json.loads((ROOT / "docs/cybercity-kit-measurements.json").read_text())
        cls.m.update(json.loads((ROOT / "docs/city-polish-measurements.json").read_text()))
        (
            cls.rows,
            cls.parcels,
            cls.changes,
            cls.protected,
            cls.heroes,
        ) = polish.plan(cls.source, cls.old, cls.m)
        cls.grouped = polish.is_grouped_baseline(cls.source)

    def test_manual_reference_is_grouped(self):
        self.assertTrue(self.grouped)
        self.assertGreater(self.source["entities"][0].get("v319_group_count", 0), 0)

    def test_grouped_baseline_is_append_only(self):
        source_count = len(self.source["entities"])
        prefix = self.rows[: source_count - 1]
        self.assertEqual(
            [r.get("source_index") for r in prefix],
            list(range(2, source_count + 1)),
        )
        for planned, original in zip(prefix, self.source["entities"][1:]):
            self.assertEqual(polish.signature(planned), polish.signature(polish.row(original)))
            self.assertFalse(planned.get("modified", False))
            self.assertFalse(planned.get("replace_asset", False))
        self.assertTrue(all(r.get("source_index") is None for r in self.rows[source_count - 1 :]))

    def test_source_record_deletion_is_rejected_for_grouped_baseline(self):
        broken = list(self.rows)
        del broken[0]
        with self.assertRaises(polish.FpmError):
            polish.assert_grouped_source_prefix(self.source, broken)

    def test_source_record_reordering_is_rejected_for_grouped_baseline(self):
        broken = list(self.rows)
        broken[0], broken[1] = broken[1], broken[0]
        with self.assertRaises(polish.FpmError):
            polish.assert_grouped_source_prefix(self.source, broken)

    def test_source_transform_edit_is_rejected_for_grouped_baseline(self):
        broken = [dict(r) for r in self.rows]
        broken[0]["x"] += 1
        with self.assertRaises(polish.FpmError):
            polish.assert_grouped_source_prefix(self.source, broken)

    def test_grouped_baseline_changes_are_skipped_not_applied(self):
        skipped = [c for c in self.changes if c.get("skipped")]
        self.assertGreater(len(skipped), 0)
        self.assertTrue(
            all(c.get("skip_reason") == "Grouped baseline is append-only; source record preserved" for c in skipped)
        )

    def test_user_changes_and_road_geometry_preserved(self):
        byid = {r["source_index"]: r for r in self.rows if "source_index" in r}
        locked = set(self.protected)
        locked.update(
            e["record_index"]
            for e in self.source["entities"]
            if polish.city.roads.road_kind(e.get("asset"))
            or polish.city.key(e.get("asset")) == "CS_Street_Crosswalk_Decal"
        )
        for idx in locked:
            self.assertEqual(
                polish.signature(byid[idx]),
                polish.signature(polish.row(self.source["entities"][idx - 1])),
            )

    def test_grouped_road_studs_are_preserved(self):
        planned = {
            r["source_index"]: r
            for r in self.rows
            if r.get("source_index") and r["asset"] == "CS_Street_Light_Marker"
        }
        source = [
            e for e in self.source["entities"] if polish.city.key(e.get("asset")) == "CS_Street_Light_Marker"
        ]
        self.assertEqual(len(planned), len(source))
        for e in source:
            self.assertEqual(
                polish.signature(planned[e["record_index"]]),
                polish.signature(polish.row(e)),
            )

    def test_six_supported_galleries_with_real_steps(self):
        self.assertEqual(len(self.heroes), 6)
        stairs = [r for r in self.rows if r["group"] == "upper-stair"]
        self.assertEqual(len(stairs), 120)
        ground = self.parcels[0]["ground"]
        for r in stairs:
            self.assertAlmostEqual(r["y"] + 80 * r["scale"][1], ground, delta=0.01)
        self.assertEqual(sum(r["group"] == "upper-deck" for r in self.rows), 12)

    def test_tents_are_selective_and_existing_signals_are_not_deleted(self):
        self.assertEqual(sum(r["group"] == "sheltered-life" for r in self.rows), 4)
        source_signals = sum(
            polish.city.key(e.get("asset")) == "CS_Stop_Light" for e in self.source["entities"]
        )
        self.assertEqual(sum(r["asset"] == "CS_Stop_Light" for r in self.rows), source_signals)


if __name__ == "__main__":
    unittest.main()
