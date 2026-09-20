import importlib.util
import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
for module_name, file_name in (
    ("fpm_inspect", "fpm_inspect.py"),
    ("fpm_clone_entity", "fpm_clone_entity.py"),
    ("fpm_author_street_fabric", "fpm_author_street_fabric.py"),
):
    if module_name in sys.modules:
        continue
    spec = importlib.util.spec_from_file_location(module_name, TOOLS / file_name)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

street = sys.modules["fpm_author_street_fabric"]


def entity(index, asset, x, y, z, ry=0.0):
    return {
        "record_index": index,
        "asset": asset,
        "position": {"x": x, "y": y, "z": z},
        "rotation_euler": {"x": 0.0, "y": ry, "z": 0.0},
        "staticflag": 1,
        "v319_group_count": 0,
        "creation_of_group_id": 0,
    }


def early_record(uniqueelement=77):
    data = bytearray()
    data += struct.pack("<iii", 1, 9, 1)
    data += struct.pack("<ffffff", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0)
    for value in ("source", "", "no_behavior_selected.lua", ""):
        data += value.encode("utf-8") + b"\r\n"
    data += struct.pack("<i", 0)
    for value in ("", "", ""):
        data += value.encode("utf-8") + b"\r\n"
    data += struct.pack("<i", uniqueelement)
    data += b"\x00" * 128
    return bytes(data)


class StreetFabricTests(unittest.TestCase):
    def test_map_ent_serializer(self):
        payload = street.serialize_map_ent([
            r"A\one.fpe",
            r"B\two.fpe",
        ])
        self.assertEqual(struct.unpack_from("<i", payload, 0)[0], 2)
        self.assertIn(b"A\\one.fpe\r\n", payload)
        self.assertTrue(payload.endswith(b"B\\two.fpe\r\n"))

    def test_plan_contains_required_street_language(self):
        parsed = {
            "entities": [
                entity(
                    2,
                    r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight_4X.fpe",
                    0.0,
                    100.0,
                    0.0,
                ),
                entity(
                    3,
                    r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Straight_4X.fpe",
                    0.0,
                    100.0,
                    400.0,
                ),
                entity(
                    4,
                    r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_4_Way_2.fpe",
                    0.0,
                    100.0,
                    800.0,
                ),
            ]
        }
        plan = street.build_street_plan(parsed)
        counts = {}
        for item in plan:
            counts[item.role] = counts.get(item.role, 0) + 1

        self.assertEqual(counts["road_center_yellow"], 2)
        self.assertEqual(counts["sidewalk_light"], 4)
        self.assertEqual(counts["street_lamp"], 2)
        self.assertEqual(counts["street_dynamic_light"], 2)
        self.assertEqual(counts["curb_guard"], 2)
        self.assertEqual(counts["utility_pole"], 1)
        self.assertEqual(counts["crosswalk"], 4)
        self.assertEqual(counts["bollard_stop"], 4)

        lamps = [p for p in plan if p.role == "street_lamp"]
        self.assertEqual(sorted(round(p.x) for p in lamps), [-325, 325])
        self.assertTrue(all(round(p.y) == 100 for p in lamps))
        markers = [p for p in plan if p.role == "street_dynamic_light"]
        self.assertTrue(all(round(p.y) == 380 for p in markers))
        self.assertTrue(all(p.ry is None for p in markers))

    def test_patch_record_changes_only_safe_prefix_and_clears_unique_token(self):
        raw = early_record(uniqueelement=77)
        parsed = {
            "record_index": 22,
            "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
            "quaternion": {"mode": 0.0, "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        template = street.Template(
            role="curb_guard",
            asset_path=r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Sidewalk_Guard.fpe",
            parsed=parsed,
            raw_record=raw,
            source_fpm="fixture.fpm",
            source_kind="same-version-donor",
        )
        placement = street.Placement(
            role="curb_guard",
            x=100.0,
            y=200.0,
            z=300.0,
            ry=90.0,
        )
        patched = street.patch_record(template, 44, placement)

        self.assertEqual(struct.unpack_from("<i", patched, street.ELE_BANKINDEX_OFFSET)[0], 44)
        self.assertAlmostEqual(struct.unpack_from("<f", patched, street.ELE_X_OFFSET)[0], 100.0)
        self.assertAlmostEqual(struct.unpack_from("<f", patched, street.ELE_Y_OFFSET)[0], 200.0)
        self.assertAlmostEqual(struct.unpack_from("<f", patched, street.ELE_Z_OFFSET)[0], 300.0)
        self.assertAlmostEqual(struct.unpack_from("<f", patched, street.ELE_RY_OFFSET)[0], 90.0)
        unique_offset = street.record_uniqueelement_offset(patched)
        self.assertEqual(struct.unpack_from("<i", patched, unique_offset)[0], 0)

    def test_active_quaternion_refuses_rotation_change(self):
        raw = early_record(uniqueelement=0)
        parsed = {
            "record_index": 22,
            "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
            "quaternion": {"mode": 1.0, "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        template = street.Template(
            role="curb_guard",
            asset_path="guard.fpe",
            parsed=parsed,
            raw_record=raw,
            source_fpm="fixture.fpm",
            source_kind="same-version-donor",
        )
        placement = street.Placement("curb_guard", 0.0, 0.0, 0.0, ry=90.0)
        with self.assertRaises(Exception):
            street.patch_record(template, 2, placement)


if __name__ == "__main__":
    unittest.main()
