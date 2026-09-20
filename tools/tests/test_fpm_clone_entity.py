import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fpm_inspect = load_module("fpm_inspect", TOOLS / "fpm_inspect.py")
fpm_clone_entity = load_module("fpm_clone_entity", TOOLS / "fpm_clone_entity.py")
fixture_helpers = load_module("fixture_helpers", TESTS / "test_fpm_inspect.py")


class FpmCloneEntityTests(unittest.TestCase):
    def test_encrypted_clone_archive_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.fpm"
            output = root / "clone-test.fpm"
            fixture_helpers.make_fixture(source)

            report = fpm_clone_entity.build_clone_test(
                source,
                output,
                "CS_Wall_01.fpe",
                1000.0,
                0.0,
                0.0,
            )

            self.assertTrue(report["gate_b_traversal"])
            self.assertTrue(report["gate_c_byte_identical_raw_roundtrip"])
            self.assertTrue(report["archive_reopen_pass"])
            self.assertTrue(report["non_ele_payloads_preserved"])
            self.assertEqual(report["payloads_changed"], ["map.ele"])
            self.assertEqual(report["gate_d_clone"]["old_entity_count"], 2)
            self.assertEqual(report["gate_d_clone"]["new_entity_count"], 3)
            self.assertAlmostEqual(
                report["generated_last_entity"]["position"]["x"], 1500.0
            )
            self.assertEqual(
                report["generated_last_entity"]["asset"],
                fixture_helpers.bank_path(),
            )

            with zipfile.ZipFile(output, "r") as zf:
                infos = zf.infolist()
                self.assertTrue(infos)
                self.assertTrue(all(info.flag_bits & 0x1 for info in infos))
                with self.assertRaises(RuntimeError):
                    zf.read("map.ele")
                payload = zf.read("map.ele", pwd=fpm_inspect.FPM_PASSWORD)
                self.assertGreater(len(payload), 8)

            with fpm_inspect.FpmArchive(output) as archive:
                ele = fpm_inspect.parse_map_ele(
                    archive.read("map.ele"),
                    fpm_inspect.parse_map_ent(archive.read("map.ent"))["entries"],
                )
                self.assertEqual(ele["entity_count"], 3)
                self.assertEqual(ele["trailing_bytes"], 0)

    def test_in_place_write_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.fpm"
            fixture_helpers.make_fixture(source)
            with self.assertRaises(fpm_inspect.FpmError):
                fpm_clone_entity.build_clone_test(
                    source,
                    source,
                    "CS_Wall_01.fpe",
                    1000.0,
                    0.0,
                    0.0,
                )


if __name__ == "__main__":
    unittest.main()
