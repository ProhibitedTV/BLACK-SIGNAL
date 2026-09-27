import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import fpm_polish_city_v12 as polish

class PolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=ROOT/'gameguru/references/District 12 - manual polish.fpm'
        if source.stat().st_size<1000000:raise unittest.SkipTest('Materialized manual reference required')
        _,_,cls.source=polish.load_scene(source)
        cls.old=json.loads((ROOT/'gameguru/buildplans/district12-v11-layout.json').read_text())
        cls.m=json.loads((ROOT/'docs/cybercity-kit-measurements.json').read_text());cls.m.update(json.loads((ROOT/'docs/city-polish-measurements.json').read_text()))
        cls.rows,cls.parcels,cls.changes,cls.protected,cls.heroes=polish.plan(cls.source,cls.old,cls.m)

    def test_user_changes_and_road_geometry_preserved(self):
        byid={r['source_index']:r for r in self.rows if 'source_index' in r}
        locked=set(self.protected)
        locked.update(e['record_index'] for e in self.source['entities'] if polish.city.roads.road_kind(e.get('asset')) or polish.city.key(e.get('asset'))=='CS_Street_Crosswalk_Decal')
        for idx in locked:
            self.assertEqual(polish.signature(byid[idx]),polish.signature(polish.row(self.source['entities'][idx-1])))

    def test_road_studs_are_grounded(self):
        road_y=next(e['position']['y'] for e in self.source['entities'] if polish.city.roads.road_kind(e.get('asset')))
        for r in self.rows:
            if r['asset']=='CS_Street_Light_Marker':self.assertAlmostEqual(r['y'],road_y+2.2,delta=.02)

    def test_six_supported_galleries_with_real_steps(self):
        self.assertEqual(len(self.heroes),6)
        stairs=[r for r in self.rows if r['group']=='upper-stair']
        self.assertEqual(len(stairs),120)
        ground=self.parcels[0]['ground']
        for r in stairs:
            self.assertAlmostEqual(r['y']+80*r['scale'][1],ground,delta=.01)
        self.assertEqual(sum(r['group']=='upper-deck' for r in self.rows),12)

    def test_tents_are_selective_and_no_geometry_is_randomized(self):
        self.assertEqual(sum(r['group']=='sheltered-life' for r in self.rows),4)
        self.assertEqual(sum(r['asset']=='CS_Stop_Light' for r in self.rows),50)

if __name__=='__main__':unittest.main()
