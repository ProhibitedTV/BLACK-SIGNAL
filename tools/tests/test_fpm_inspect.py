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


class Writer:
    def __init__(self):
        self.data = bytearray()

    def i(self, value=0, count=1):
        for _ in range(count):
            self.data += struct.pack("<i", value)

    def f(self, value=0.0, count=1):
        for _ in range(count):
            self.data += struct.pack("<f", value)

    def s(self, value="", count=1):
        for _ in range(count):
            self.data += value.encode("utf-8") + b"\r\n"


def write_material_slot(w: Writer):
    w.i(count=4)
    w.s(count=2)
    w.f()
    w.s(count=6)
    w.f(count=5)


def write_v342_record(
    w: Writer,
    record_index: int,
    bankindex: int,
    x: float,
    y: float,
    z: float,
    ry: float,
):
    # v101 base
    w.i(1)
    w.i(bankindex)
    w.i(1)
    w.f(x)
    w.f(y)
    w.f(z)
    w.f(0.0)
    w.f(ry)
    w.f(0.0)
    w.s(f"entity-{record_index}")
    w.s("")
    w.s("no_behavior_selected.lua")
    w.s("")
    w.i(0)
    w.s(count=3)
    w.i()
    w.s(count=3)
    w.i(count=2)
    w.s(count=2)
    w.i(count=7)
    w.s()
    w.s()
    w.i(count=4)
    w.f(100.0)
    w.f(count=2)
    w.i(count=9)
    w.s()

    # v102-v107
    w.i(count=6)
    w.f(count=2)
    w.i(count=12)
    w.i(count=9)
    w.i()
    w.i(count=6)
    w.i(count=2)
    w.i()

    # v199/v200
    w.i(count=17)
    w.i(count=6)

    # v217/v218
    w.i(count=17)
    w.i()

    # v301-v313
    w.s(count=4)
    w.i()
    w.f()
    w.f(100.0, count=3)
    w.i(count=2)
    w.i()
    w.i()
    w.i()
    w.i()
    w.i(count=5)
    w.s(count=3)
    w.f()
    w.i()
    w.s()
    w.i()

    # v314 material slot zero
    w.i(count=6)
    w.s(count=2)
    w.f()
    w.i()
    w.s(count=6)
    w.f(count=5)

    # v315
    w.i()

    # v316 relationship header + 10 relationship entries
    w.i(count=7)
    w.f(count=2)
    for _ in range(10):
        w.f()
        w.i(count=3)

    # v317 remaining 99 material slots
    for _ in range(1, fpm_inspect.MAX_MESH_MATERIALS):
        write_material_slot(w)

    # v318 render order bias
    w.f(count=fpm_inspect.MAX_MESH_MATERIALS)

    # v319 group table is physically present only on entity 1.
    if record_index == 1:
        w.i(77)
        w.i(2)
        w.i(1)
        w.i(10)
        w.i(0)
        w.i(1)
        w.f(1.0)
        w.f(2.0)
        w.f(3.0)
        w.f(0.0)
        w.f(0.0)
        w.f(0.0)
        w.f(1.0)
        w.i(0)
        w.i(1)
        w.i(0)
    else:
        w.i(0)
        w.i(0)

    # v320-v328
    w.i(count=4)
    w.f(count=3)
    w.s()
    w.f(count=2)
    w.s()
    w.f(count=2)
    w.i()
    w.f(count=2)
    w.i(count=3)
    w.i()
    w.s(count=2)
    w.i()

    # v329 quaternion
    w.f(1.0)
    w.f(0.0)
    w.f(0.0)
    w.f(0.0)
    w.f(1.0)

    # v330-v333
    w.f()
    w.s()
    w.i()
    w.i()

    # v334 currently writes 100 group-name strings on every entity.
    w.i(100)
    for gi in range(100):
        w.s(f"group-{gi}" if gi < 2 else "")

    # v335-v338. Synthetic static entities are intentionally ungrouped so the
    # write-path tests can safely clone record 2 without inheriting group state.
    w.i(0)
    w.i(count=3)
    w.i()
    w.i(count=3)

    # v339
    w.i()
    w.f(count=7)
    w.s()

    # v340
    w.s()
    w.f()
    w.i(count=2)
    w.f(count=2)
    w.i(count=3)
    w.s(count=3)

    # v341/v342
    w.i()
    w.s()


def make_fixture(path: Path, add_trailing_byte=False):
    header = struct.pack("<ii", 1, 0)
    bank = [
        r"markerbank\Player Start.fpe",
        r"cyberpunk streets booster pack\Buildings\CS_Wall_01.fpe",
    ]
    map_ent = struct.pack("<i", len(bank)) + b"".join(
        x.encode("utf-8") + b"\r\n" for x in bank
    )

    ele = Writer()
    ele.i(342)
    ele.i(2)
    write_v342_record(ele, 1, 1, 100.0, 20.0, 300.0, 0.0)
    write_v342_record(ele, 2, 2, 500.0, 20.0, 300.0, 90.0)
    if add_trailing_byte:
        ele.data += b"X"

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("header.dat", header)
        zf.writestr("map.ent", map_ent)
        zf.writestr("map.ele", bytes(ele.data))
        zf.writestr("cfg.cfg", b"fixture")


class FpmInspectorTests(unittest.TestCase):
    def test_full_v342_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            fpm = Path(td) / "fixture.fpm"
            make_fixture(fpm)
            report = fpm_inspect.inspect_fpm(fpm)

            self.assertEqual(report["header_dat"]["major"], 1)
            self.assertEqual(report["map_ent"]["count"], 2)
            self.assertEqual(report["map_ele"]["version"], 342)
            self.assertEqual(report["map_ele"]["entity_count"], 2)
            self.assertTrue(report["map_ele"]["fully_traversed"])
            self.assertEqual(report["map_ele"]["trailing_bytes"], 0)
            self.assertEqual(
                report["map_ele"]["parsed_bytes"], report["map_ele"]["bytes"]
            )

            first, second = report["map_ele"]["entities"]
            self.assertEqual(first["bankindex"], 1)
            self.assertEqual(first["v319_group_count"], 2)
            self.assertEqual(first["v334_group_name_count"], 100)
            self.assertEqual(second["bankindex"], 2)
            self.assertEqual(second["asset"], bank_path())
            self.assertAlmostEqual(second["position"]["x"], 500.0)
            self.assertAlmostEqual(second["rotation_euler"]["y"], 90.0)
            self.assertEqual(second["creation_of_group_id"], 0)
            self.assertGreater(
                second["record_start_offset"], first["record_end_offset"] - 1
            )

    def test_trailing_data_fails_gate_b(self):
        with tempfile.TemporaryDirectory() as td:
            fpm = Path(td) / "fixture-bad.fpm"
            make_fixture(fpm, add_trailing_byte=True)
            with self.assertRaises(fpm_inspect.FpmError) as ctx:
                fpm_inspect.inspect_fpm(fpm)
            self.assertIn("trailing byte", str(ctx.exception))

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
