import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fpm_author_cityscape_v11 as city
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


class CityscapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[2]
        cls.measured=json.loads((root/'docs/cybercity-kit-measurements.json').read_text())
        # Synthetic grid keeps structural tests independent of commercial/LFS assets.
        entities=[]
        for iz in range(7):
            for ix in range(7):
                entities.append(dict(record_index=len(entities)+1,asset='CS_Street_4_Way_2.fpe',
                    position=dict(x=ix*1800.,y=1208.8,z=iz*1800.),rotation_euler=dict(x=0.,y=0.,z=0.)))
        cls.parsed=dict(entities=entities)

    def test_every_parcel_is_filled(self):
        rows,parcels=city.plan(self.parsed)
        self.assertEqual(len(parcels),36)
        city.validate(rows,parcels,self.measured)
        self.assertGreaterEqual(len(set(p['floors'] for p in parcels)),5)

    def test_displaced_facade_rejected_even_when_count_is_correct(self):
        rows,parcels=city.plan(self.parsed)
        next(r for r in rows if r['asset']=='CS_Wall_Corner_01')['x']+=50
        with self.assertRaisesRegex(FpmError,'displaced envelope'):city.validate(rows,parcels,self.measured)

    def test_missing_far_parcel_rejected(self):
        rows,parcels=city.plan(self.parsed)
        with self.assertRaisesRegex(FpmError,'36 parcels'):city.validate(rows,parcels[:-1],self.measured)

    def test_missing_sidewalk_rejected(self):
        rows,parcels=city.plan(self.parsed)
        rows.remove(next(r for r in rows if r['asset']=='CS_Sidewalk_Tile_4x4'))
        with self.assertRaisesRegex(FpmError,'paving'):city.validate(rows,parcels,self.measured)

    def test_mesh_pivot_drift_rejected(self):
        rows,parcels=city.plan(self.parsed);bounds=copy.deepcopy(self.measured)
        bounds['CS_Roof_Tile_2x2']['min'][1]+=40
        with self.assertRaisesRegex(FpmError,'seam'):city.validate(rows,parcels,bounds)

    def test_editor_reference_remains_parseable(self):
        ref=Path(__file__).resolve().parents[2]/'gameguru/references/District 12 - human corner.fpm'
        if not ref.exists() or ref.stat().st_size<1000000:self.skipTest('Materialized LFS reference required')
        with FpmArchive(ref) as archive:
            parsed=parse_map_ele(archive.read('map.ele'),parse_map_ent(archive.read('map.ent'))['entries'])
        self.assertTrue(parsed['fully_traversed'])
        self.assertEqual(parsed['version'],342)

    def test_service_prop_cannot_block_door(self):
        rows,parcels=city.plan(self.parsed)
        r=next(r for r in rows if r['asset']=='CS_Dumpster_Closed')
        r['x']=parcels[0]['x']+400
        with self.assertRaisesRegex(FpmError,'door corridor'):city.validate(rows,parcels,self.measured)

    def test_floating_furniture_rejected(self):
        rows,parcels=city.plan(self.parsed)
        next(r for r in rows if r['group']=='dressing-furniture')['y']+=20
        with self.assertRaisesRegex(FpmError,'ground support'):city.validate(rows,parcels,self.measured)

    def test_streets_have_commercial_and_service_dressing(self):
        rows,parcels=city.plan(self.parsed)
        for p in parcels:
            assets={r['asset'] for r in rows if r.get('parcel')==p['name']}
            self.assertTrue({'CS_Dumpster_Closed','CS_ATM','CS_ATM_Screen','CS_Store_Front_01_Entrance','CS_Box_01','CS_Bench','CS_Trash_Can'}<=assets)


if __name__=='__main__':unittest.main()
