import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_city_mass as city
import fpm_author_city_mass_v3 as v3


def cluster(width: float, depth: float, height: float, count: int = 6) -> city.Cluster:
    entities = [{"record_index": i} for i in range(count)]
    return city.Cluster(
        entities=entities,
        kind="foreground",
        min_x=0.0,
        max_x=width,
        min_z=0.0,
        max_z=depth,
        min_y=0.0,
        max_y=height,
    )


class CityMassV3QualityTests(unittest.TestCase):
    def test_rejects_thin_facade_sliver(self) -> None:
        self.assertFalse(v3.acceptable_foreground_cluster(cluster(35.0, 900.0, 1100.0)))

    def test_rejects_implausibly_tall_narrow_stack(self) -> None:
        self.assertFalse(v3.acceptable_foreground_cluster(cluster(100.0, 230.0, 2000.0)))

    def test_accepts_broad_authored_building_mass(self) -> None:
        self.assertTrue(v3.acceptable_foreground_cluster(cluster(240.0, 420.0, 850.0)))

    def test_accepts_compact_modular_pivot_cloud(self) -> None:
        # MAX modular meshes can share tight X/Z pivots even though the meshes
        # themselves form a complete authored shell. Pivot extent is not mesh extent.
        self.assertTrue(v3.acceptable_foreground_cluster(cluster(40.0, 180.0, 700.0, count=8)))

    def test_rejects_tiny_component_group(self) -> None:
        self.assertFalse(v3.acceptable_foreground_cluster(cluster(240.0, 420.0, 400.0, count=3)))


if __name__ == "__main__":
    unittest.main()
