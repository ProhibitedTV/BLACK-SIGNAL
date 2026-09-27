import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import fpm_polish_city_v12 as base
import fpm_polish_city_v12_nativefix as nativefix


class NativeReviewPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "gameguru/references/District 12 - manual polish.fpm"
        if source.stat().st_size < 1_000_000:
            raise unittest.SkipTest("Materialized manual reference required")
        _, _, cls.parsed = base.load_scene(source)
        cls.old = json.loads((ROOT / "gameguru/buildplans/district12-v11-layout.json").read_text())
        cls.measured = json.loads((ROOT / "docs/cybercity-kit-measurements.json").read_text())
        cls.measured.update(json.loads((ROOT / "docs/city-polish-measurements.json").read_text()))

    def test_native_review_removes_only_appended_sheltered_life(self):
        base_rows, *_ = base.plan(self.parsed, self.old, self.measured)
        rows, *_ = nativefix.plan(self.parsed, self.old, self.measured)
        self.assertEqual(sum(r.get("group") == "sheltered-life" for r in base_rows), 4)
        self.assertEqual(sum(r.get("group") == "sheltered-life" for r in rows), 0)
        self.assertEqual(len(base_rows) - len(rows), 4)

    def test_grouped_source_prefix_remains_identity_preserved(self):
        rows, *_ = nativefix.plan(self.parsed, self.old, self.measured)
        base.assert_grouped_source_prefix(self.parsed, rows)
        source_count = len(self.parsed["entities"])
        self.assertEqual(
            [r.get("source_index") for r in rows[:source_count - 1]],
            list(range(2, source_count + 1)),
        )


if __name__ == "__main__":
    unittest.main()
