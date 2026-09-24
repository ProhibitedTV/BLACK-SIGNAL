import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_network_v3 as network
import fpm_validate_road_system_v7 as validator


def foundation_report(grid_size=5):
    placements = []
    for item in network.plan_uniform_network(grid_size):
        placements.append(
            {
                "kind": item.kind,
                "x": item.x,
                "y": 10.0,
                "z": item.z,
                "yaw": 0.0,
                "connections": sorted(item.mask),
                "note": item.note,
            }
        )
    return {"grid_size": grid_size, "placements": placements}


class RoadSystemV7ValidationTests(unittest.TestCase):
    def test_uniform_foundation_contract_passes(self):
        errors = validator.validate_foundation_contract(foundation_report())
        self.assertEqual(errors, [])

    def test_missing_span_module_fails_closed(self):
        report = foundation_report()
        report["placements"] = [
            row
            for row in report["placements"]
            if not (row["note"] == "avenue-h-0-0" and row["x"] == -3100.0)
        ]
        errors = validator.validate_foundation_contract(report)
        self.assertTrue(any("horizontal span 0,0" in error for error in errors))

    def test_non_uniform_span_module_fails_closed(self):
        report = foundation_report()
        row = next(row for row in report["placements"] if row["note"] == "avenue-v-0-0")
        row["kind"] = "straight2"
        errors = validator.validate_foundation_contract(report)
        self.assertTrue(any("vertical span 0,0 contains non-uniform module" in error for error in errors))

    def test_surface_policy_rejects_arrow_on_intersection(self):
        report = {
            "surface_attachment_policy": validator.EXPECTED_SURFACE_POLICY,
            "approach_junction_kinds": ["fourway", "tee"],
            "placements": [
                {"role": "road_arrow_straight", "road_kind": "fourway"}
            ],
        }
        errors = validator.validate_surface_policy(report)
        self.assertTrue(any("expected 'straight4'" in error for error in errors))

    def test_surface_policy_accepts_arrow_on_straight(self):
        report = {
            "surface_attachment_policy": validator.EXPECTED_SURFACE_POLICY,
            "approach_junction_kinds": ["fourway", "tee"],
            "placements": [
                {"role": "road_arrow_straight", "road_kind": "straight4"}
            ],
        }
        self.assertEqual(validator.validate_surface_policy(report), [])


if __name__ == "__main__":
    unittest.main()
