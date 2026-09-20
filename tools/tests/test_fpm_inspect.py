import importlib.util
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "fpm_inspect.py"
spec = importlib.util.spec_from_file_location("fpm_inspect", MODULE_PATH)
fpm_inspect = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = fpm_inspect
spec.loader.exec_module(fpm_inspect)


def crlf(text: str) -> bytes:
    return text.encode("utf-8") + b"\r\n"


def make_fixture(path: Path) -> None:
    header = struct.pack("<ii", 1, 0)

    bank = [
        r"markerbank\Player Start.fpe",
        r"cyberpunk streets booster pack\Buildings\CS_Wall_01.fpe",
    ]
    map_ent = struct.pack("<i", len(bank)) + b"".join(crlf(x) for x in bank)

    # Only the stable v101 prefix is required by the current read-only probe.
    prefix = bytearray()
    prefix += struct.pack("<ii", 342, 1)  # ELE version, entity count
    prefix += struct.pack("<iii", 1, 2, 1)  # maintype, bankindex, staticflag
    prefix += struct.pack("<ffffff", 100.0, 20.0, 300.0, 0.0, 90.0, 0.0)
    prefix += crlf("wall-test")
    prefix += crlf("")
    prefix += crlf("no_behavior_selected.lua")
    prefix += crlf("")
    prefix += struct.pack("<i", 0)
    # The real record contains many more versioned fields. Add opaque bytes so
    # the inspector proves it does not pretend to parse beyond the safe prefix.
    prefix += b"OPAQUE-V342-TAIL"

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("header.dat", header)
        zf.writestr("map.ent", map_ent)
        zf.writestr("map.ele", bytes(prefix))
        zf.writestr("cfg.cfg", b"fixture")


class FpmInspectorTests(unittest.TestCase):
    def test_inspect_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            fpm = Path(td) / "fixture.fpm"
            make_fixture(fpm)
            report = fpm_inspect.inspect_fpm(fpm)

            self.assertEqual(report["header_dat"]["major"], 1)
            self.assertEqual(report["header_dat"]["minor"], 0)
            self.assertEqual(report["map_ent"]["count"], 2)
            self.assertEqual(report["map_ent"]["encoding"], "crlf")
            self.assertEqual(report["map_ele"]["version"], 342)
            self.assertEqual(report["map_ele"]["entity_count"], 1)

            first = report["map_ele"]["first_entity_prefix"]
            self.assertEqual(first["bankindex"], 2)
            self.assertEqual(first["name"], "wall-test")
            self.assertEqual(first["asset"], bank_path())
            self.assertAlmostEqual(first["position"]["x"], 100.0)
            self.assertAlmostEqual(first["rotation_euler"]["y"], 90.0)

    def test_extract_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fpm = root / "fixture.fpm"
            out = root / "out"
            make_fixture(fpm)
            with fpm_inspect.FpmArchive(fpm) as archive:
                manifest = archive.member_manifest()
                archive.extract(out)
            self.assertTrue((out / "map.ent").is_file())
            self.assertTrue(any(x["name"] == "map.ele" for x in manifest))


def bank_path():
    return r"cyberpunk streets booster pack\Buildings\CS_Wall_01.fpe"


if __name__ == "__main__":
    unittest.main()
