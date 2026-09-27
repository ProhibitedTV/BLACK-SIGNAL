from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_human_cityscape_v10_5 as v105
import fpm_author_road_semantics_v9_compat as compat
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_inspect import FpmArchive, parse_map_ele, parse_map_ent


class HumanTemplateRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ref = ROOT / "gameguru" / "references" / "District 12 - human corner.fpm"
        if not cls.ref.exists() or cls.ref.stat().st_size < 1_000_000:
            raise unittest.SkipTest("materialized canonical LFS FPM is required")
        with FpmArchive(cls.ref) as archive:
            ent = parse_map_ent(archive.read("map.ent"))
            cls.bank = ent["entries"]
            cls.ele = archive.read("map.ele")
            cls.parsed = parse_map_ele(cls.ele, cls.bank)
        cls.templates = v105._exact_reference_templates(cls.ref)

    def test_each_patched_human_record_preserves_schema_size(self) -> None:
        bank_paths = [row["path"] for row in self.bank]
        lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
        version = int(self.parsed["version"])
        for role, template in self.templates.items():
            with self.subTest(role=role, asset=template.asset_path):
                bank_index = lookup[fabric.norm(template.asset_path)]
                src = template.parsed
                placement = fabric.Placement(
                    role=role,
                    x=float(src["position"]["x"]) + 123.0,
                    y=float(src["position"]["y"]),
                    z=float(src["position"]["z"]) + 57.0,
                    ry=(float(src["rotation_euler"]["y"]) + 90.0) % 360.0,
                )
                patched = _patched_patch_record(template, bank_index, placement)
                self.assertEqual(len(patched), len(template.raw_record))
                stream = struct.pack("<ii", version, 1) + patched
                reparsed = parse_map_ele(stream, self.bank)
                self.assertEqual(reparsed["entity_count"], 1)
                self.assertEqual(reparsed["entities"][0]["record_bytes"], len(patched))

    def test_full_human_clone_batch_roundtrips_as_records(self) -> None:
        bank_paths = [row["path"] for row in self.bank]
        lookup = {fabric.norm(path): i + 1 for i, path in enumerate(bank_paths)}
        version = int(self.parsed["version"])
        plan = v105.plan_human_cityscape(self.parsed)
        records = []
        for item in plan:
            template = self.templates[item.role]
            bank_index = lookup[fabric.norm(template.asset_path)]
            records.append(_patched_patch_record(template, bank_index, item))
        stream = struct.pack("<ii", version, len(records)) + b"".join(records)
        reparsed = parse_map_ele(stream, self.bank)
        self.assertEqual(reparsed["entity_count"], len(records))
        self.assertEqual(reparsed["trailing_bytes"], 0)

    def test_dynamic_marker_is_taken_from_captured_reference(self) -> None:
        template = v105._exact_reference_dynamic_template(self.ref)
        self.assertEqual(template.role, compat.DYNAMIC_ROLE)
        self.assertEqual(template.source_kind, "human-reference-exact-dynamic")
        self.assertEqual(Path(template.source_fpm), self.ref.resolve())
        self.assertEqual(
            fabric.basename(template.asset_path),
            fabric.basename(fabric.ASSETS[compat.DYNAMIC_ROLE]["basename"]),
        )


if __name__ == "__main__":
    unittest.main()
