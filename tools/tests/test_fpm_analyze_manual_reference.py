import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_analyze_manual_reference as analyzer


class ManualReferenceAnalyzerTests(unittest.TestCase):
    def test_v9_1_centerline_signature(self) -> None:
        t = {"local_x": 0.0, "local_y": 2.0, "local_z": 110.0, "yaw_delta": 90.0, "distance": 110.0}
        self.assertTrue(analyzer.matches_expected("road_center_yellow", t))

    def test_manual_centerline_offset_is_detected(self) -> None:
        t = {"local_x": 36.0, "local_y": 2.0, "local_z": 110.0, "yaw_delta": 90.0, "distance": 115.7}
        self.assertFalse(analyzer.matches_expected("road_center_yellow", t))

    def test_v9_1_crosswalk_signature(self) -> None:
        t = {"local_x": -200.0, "local_y": 2.0, "local_z": 0.0, "yaw_delta": -90.0, "distance": 200.0}
        self.assertTrue(analyzer.matches_expected("crosswalk", t))

    def test_lamp_offset_signature(self) -> None:
        t = {"local_x": 390.0, "local_y": 0.0, "local_z": 0.0, "yaw_delta": 0.0, "distance": 390.0}
        self.assertTrue(analyzer.matches_expected("street_lamp", t))


if __name__ == "__main__":
    unittest.main()
