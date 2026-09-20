import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_street_fabric_compat as compat
from fpm_inspect import FpmError


class StreetFabricQuaternionCompatTests(unittest.TestCase):
    def test_unique_quaternion_payload_is_located(self):
        quat = {"mode": 1065353216.0, "x": 0.0, "y": 0.5, "z": 0.0, "w": 0.8660254}
        raw = b"A" * 37 + struct.pack("<5f", quat["mode"], quat["x"], quat["y"], quat["z"], quat["w"]) + b"B" * 17
        self.assertEqual(compat._find_quaternion_span(raw, quat), 37)

    def test_ambiguous_quaternion_payload_is_rejected(self):
        quat = {"mode": 1.0, "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        needle = struct.pack("<5f", 1.0, 0.0, 0.0, 0.0, 1.0)
        with self.assertRaises(FpmError):
            compat._find_quaternion_span(b"X" + needle + b"Y" + needle, quat)

    def test_patch_record_normalizes_quaternion_to_euler_mode(self):
        raw = bytearray(192)
        quat_offset = 96
        unique_offset = 144
        source_quat = {
            "mode": 1318926976.0,
            "x": 0.1,
            "y": 0.2,
            "z": 0.3,
            "w": 0.9,
        }
        struct.pack_into(
            "<5f",
            raw,
            quat_offset,
            source_quat["mode"],
            source_quat["x"],
            source_quat["y"],
            source_quat["z"],
            source_quat["w"],
        )
        struct.pack_into("<i", raw, unique_offset, 99)

        template = compat.base.Template(
            role="road_center_yellow",
            asset_path="CS_Street_Double_Center_Line.fpe",
            parsed={
                "rotation_euler": {"x": 0.0, "y": 0.0, "z": 0.0},
                "quaternion": source_quat,
            },
            raw_record=bytes(raw),
            source_fpm="District 12.fpm",
            source_kind="target-exact",
        )
        placement = compat.base.Placement(
            role="road_center_yellow",
            x=100.0,
            y=200.0,
            z=300.0,
            rx=0.0,
            ry=90.0,
            rz=0.0,
        )

        with mock.patch.object(
            compat.base, "record_uniqueelement_offset", return_value=unique_offset
        ):
            patched = compat._patched_patch_record(template, 42, placement)

        self.assertEqual(struct.unpack_from("<i", patched, compat.base.ELE_BANKINDEX_OFFSET)[0], 42)
        self.assertEqual(struct.unpack_from("<f", patched, compat.base.ELE_X_OFFSET)[0], 100.0)
        self.assertEqual(struct.unpack_from("<f", patched, compat.base.ELE_Y_OFFSET)[0], 200.0)
        self.assertEqual(struct.unpack_from("<f", patched, compat.base.ELE_Z_OFFSET)[0], 300.0)
        self.assertEqual(struct.unpack_from("<f", patched, compat.base.ELE_RY_OFFSET)[0], 90.0)
        self.assertEqual(struct.unpack_from("<5f", patched, quat_offset), (0.0, 0.0, 0.0, 0.0, 1.0))
        self.assertEqual(struct.unpack_from("<i", patched, unique_offset)[0], 0)


if __name__ == "__main__":
    unittest.main()
