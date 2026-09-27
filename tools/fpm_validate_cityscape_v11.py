"""Independently verify saved city transforms against the reference-derived plan."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import fpm_author_cityscape_v11 as city
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent


def load(path):
    with FpmArchive(path) as f:
        return parse_map_ele(f.read('map.ele'),parse_map_ent(f.read('map.ent'))['entries'])


def validate(path,reference,measurements):
    original=load(reference);actual=load(path)
    rows,parcels=city.plan(original)
    city.validate(rows,parcels,json.loads(measurements.read_text()))
    expected=Counter((r['asset'],round(r['x'],1),round(r['y'],1),round(r['z'],1),round(r['yaw']%360,1) if r['yaw'] is not None else None) for r in rows)
    found=Counter()
    for e in actual['entities'][1:]:
        p=e['position'];name=city.key(e['asset'])
        yaw=None if name=='CS_Street_Light_Marker' else round(e['rotation_euler']['y']%360,1)
        found[(name,round(p['x'],1),round(p['y'],1),round(p['z'],1),yaw)]+=1
        if name in city.extras.ASSETS:
            if e['aimain']!=city.extras.SCRIPT or not e['name'].startswith('BS_EXTRA_') or e['staticflag']!=0:
                raise FpmError('Civilian behavior binding is invalid')
    if expected!=found:raise FpmError(f'Saved placements differ: missing={sum((expected-found).values())}, extra={sum((found-expected).values())}')
    if actual['version']!=original['version'] or actual['trailing_bytes'] or not actual['fully_traversed']:
        raise FpmError('Saved ELE schema is invalid')
    if city.key(actual['entities'][0]['asset'])!='Player Start':raise FpmError('Player Start missing')
    expected_names={r['name'] for r in rows if r['group']=='extras'}
    actual_names=[e['name'] for e in actual['entities'] if city.key(e['asset']) in city.extras.ASSETS]
    if len(actual_names)!=216 or set(actual_names)!=expected_names:raise FpmError('Civilian route identities mismatch')
    routes=path.with_suffix('.routes.lua')
    if not routes.exists():routes=Path(__file__).resolve().parents[1]/'gameguru/Files/scriptbank/user/black_signal/bs_city_extra_routes.lua'
    if not routes.exists() or routes.read_text()!=city.extras.render_lua(rows):raise FpmError('Route sidecar differs from saved level')
    return dict(status='pass',populated_parcels=len(parcels),entity_count=actual['entity_count'],
                ele_version=actual['version'],sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                checked='Exact saved transforms; envelopes; paving; road clearance; ELE traversal; 216 civilian identities, behavior scripts and sidewalk-only routes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('fpm',type=Path)
    p.add_argument('--reference',required=True,type=Path);p.add_argument('--measurements',required=True,type=Path)
    p.add_argument('--report',type=Path);a=p.parse_args();result=validate(a.fpm,a.reference,a.measurements)
    if a.report:a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
