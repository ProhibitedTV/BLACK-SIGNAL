import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fpm_author_hero_block as hero


class HeroBlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bounds = json.loads((Path(__file__).resolve().parents[2] / "docs/cybercity-kit-measurements.json").read_text())

    def test_measured_plan(self):
        hero.validate(hero.plan(), self.bounds)

    def test_missing_corner_rejected(self):
        rows=hero.plan()
        rows.remove(next(r for r in rows if r['asset']=='CS_Wall_Corner_01'))
        with self.assertRaisesRegex(ValueError,'corner'):
            hero.validate(rows,self.bounds)

    def test_floating_roof_rejected(self):
        rows=hero.plan()
        for r in rows:
            if r['asset']=='CS_Roof_Tile_2x2': r['y']+=80
        with self.assertRaisesRegex(ValueError,'Floating roof'):
            hero.validate(rows,self.bounds)

    def test_road_intrusion_rejected(self):
        rows=hero.plan()
        wall=next(r for r in rows if r['asset']=='CS_Wall_Corner_01')
        wall.update(x=0,z=0)
        with self.assertRaisesRegex(ValueError,'intersects road'):
            hero.validate(rows,self.bounds)

    def test_changed_installed_kit_rejected(self):
        bounds=copy.deepcopy(self.bounds)
        bounds['CS_Wall_01']['size'][0]=250
        with self.assertRaisesRegex(ValueError,'Uncalibrated'):
            hero.validate(hero.plan(),bounds)


if __name__=='__main__':
    unittest.main()
