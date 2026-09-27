"""Verify the incremental export against the user's saved baseline and its plan."""
import argparse,json,hashlib
from pathlib import Path
from collections import Counter
import fpm_polish_city_v12 as polish
import fpm_city_extras as extras
from fpm_inspect import FpmArchive,FpmError

def validate(candidate,source,report_path=None):
    report_path=report_path or candidate.with_suffix('.report.json')
    report=json.loads(report_path.read_text());rows=report['placements']
    sd,sb,sp=polish.load_scene(source);cd,cb,cp=polish.load_scene(candidate)
    if sp['entities'][0].get('v319_group_count',0):raise FpmError('Grouped baseline requires explicit group-index remapping before edits')
    if report['source_sha256']!=hashlib.sha256(source.read_bytes()).hexdigest():raise FpmError('Baseline changed')
    if report['sha256']!=hashlib.sha256(candidate.read_bytes()).hexdigest():raise FpmError('Candidate changed')
    if len(rows)+1!=cp['entity_count'] or cp['version']!=342 or cp['trailing_bytes']:raise FpmError('Entity stream mismatch')
    lookup={}
    for r,e in zip(rows,cp['entities'][1:]):
        if polish.city.key(e['asset'])!=r['asset'] or any(abs(e['position'][a]-r[a])>.03 for a in ('x','y','z')):raise FpmError('Transform mismatch')
        if abs((e['rotation_euler']['y']-r['yaw']+180)%360-180)>.03:raise FpmError('Yaw mismatch')
        if r.get('source_index'):lookup[r['source_index']]=e
        if 'scale' in r and any(abs(e['scale_xyz'][a]-100*(s-1))>.01 for a,s in zip(('x','y','z'),r['scale'])):raise FpmError('Scaled geometry mismatch')
        if r['group']=='extras' and (e['name']!=r['name'] or e['aimain']!=extras.SCRIPT or e['staticflag']!=0):raise FpmError('Civilian binding mismatch')
    locked=set(report['protected_manual_records'])
    locked.update(e['record_index'] for e in sp['entities'] if polish.city.roads.road_kind(e.get('asset')) or polish.city.key(e.get('asset'))=='CS_Street_Crosswalk_Decal')
    for idx in locked:
        before=sp['entities'][idx-1];after=lookup.get(idx)
        if not after or before['record_sha256']!=after['record_sha256']:raise FpmError(f'Protected manual/infrastructure record changed: {idx}')
    if sd[sp['entities'][0]['record_start_offset']:sp['entities'][0]['record_end_offset']]!=cd[cp['entities'][0]['record_start_offset']:cp['entities'][0]['record_end_offset']]:raise FpmError('Player/global metadata changed')
    measured=json.loads((polish.ROOT/'docs/cybercity-kit-measurements.json').read_text());measured.update(json.loads((polish.ROOT/'docs/city-polish-measurements.json').read_text()))
    scene=[];local=dict(measured)
    import copy
    for i,r in enumerate(rows):
        r=dict(r)
        if 'scale' in r:
            label=r['asset']+'__'+str(i);b=copy.deepcopy(measured[r['asset']])
            for axis,s in enumerate(r['scale']):b['min'][axis]*=s;b['max'][axis]*=s
            local[label]=b;r['asset']=label
        scene.append(r)
    extras.validate(scene,report['parcels'],local,polish.city.hero.world_bounds,polish.city.measured_city.intersects)
    routes=candidate.with_suffix('.routes.lua')
    if not routes.exists():routes=polish.ROOT/'gameguru/Files/scriptbank/user/black_signal/bs_city_extra_routes.lua'
    if routes.read_text()!=extras.render_lua(rows):raise FpmError('Pedestrian routes differ from map')
    for r in rows:
        if r['group'] not in ('upper-deck','upper-stair'):continue
        p=min(report['parcels'],key=lambda p:(r['x']-p['x'])**2+(r['z']-(p['z']+p['depth']/2))**2)
        sy=r.get('scale',[1,1,1])[1];bottom=r['y']+80*sy;top=r['y']+100*sy
        if r['group']=='upper-stair' and abs(bottom-p['ground'])>.02:raise FpmError('Unsupported stair block')
        if r['group']=='upper-deck' and abs(top-p['ground']-200)>.02:raise FpmError('Gallery floor seam')
    with FpmArchive(source) as a,FpmArchive(candidate) as b:
        before={m['name']:m['sha256'] for m in a.member_manifest()};after={m['name']:m['sha256'] for m in b.member_manifest()}
        if {n for n in before if before[n]!=after[n]}-{'map.ele','map.ent','visuals.ini'}:raise FpmError('Unexpected archive member change')
    return dict(status='pass',entity_count=cp['entity_count'],protected_records=len(locked),extras=216,sha256=report['sha256'],native_review='pending')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('--source',required=True,type=Path);p.add_argument('--plan',type=Path);p.add_argument('--report',type=Path)
    a=p.parse_args();result=validate(a.candidate,a.source,a.plan)
    if a.report:a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
