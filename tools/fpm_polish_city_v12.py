"""Bounded edits on the user-saved level. Preserve infrastructure and hand edits."""
import argparse,base64,copy,hashlib,json,math,re,struct
from collections import Counter
from pathlib import Path
import fpm_author_cityscape_v11 as city
import fpm_author_street_fabric as fabric
import fpm_city_extras as extras
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import write_zipcrypto_archive,verify_raw_ele_roundtrip
from fpm_inspect import FpmArchive,FpmError,parse_map_ele,parse_map_ent,BinaryReader,parse_ele_record

ROOT=Path(__file__).resolve().parents[1]
def signature(r):
    yaw=r['yaw']
    if yaw is None:yaw=90 if r['asset']=='CS_Street_Light_Marker' else 0
    return (r['asset'],*(round(r[a],2) for a in ('x','y','z')),round(yaw%360,2))
def row(e):
    return dict(asset=city.key(e['asset']),**e['position'],yaw=e['rotation_euler']['y'],group='manual',source_index=e['record_index'])

def scale_record(raw,factors):
    r=BinaryReader(raw);parse_ele_record(r,304,2,[])
    out=bytearray(raw);struct.pack_into('<fff',out,r.offset,*(100*(f-1) for f in factors))
    return bytes(out)

def bounds(r,m):
    if 'scale' not in r:return city.hero.world_bounds(r,m)
    local=dict(m);b=copy.deepcopy(m[r['asset']])
    for i,s in enumerate(r['scale']):b['min'][i]*=s;b['max'][i]*=s
    local[r['asset']]=b
    return city.hero.world_bounds(r,local)

def plan(parsed,old,measured):
    previous={signature(r):r for r in old['placements']}
    parcels=old['parcels'];rows=[];changes=[];protected=[]
    roads=[e for e in parsed['entities'] if city.roads.road_kind(e.get('asset'))]
    junctions=[e for e in roads if city.roads.road_kind(e['asset'])!='straight4']
    xs=sorted({e['position']['x'] for e in junctions});zs=sorted({e['position']['z'] for e in junctions})
    markers=set();signal_number=0
    for e in parsed['entities'][1:]:
        r=row(e);before=dict(r);prior=previous.get(signature(r))
        if prior:r['group']=prior['group']
        else:protected.append(e['record_index'])
        reason=None;remove=False
        if prior and r['asset']=='CS_Street_Light_Marker' and r['y']>1400:
            # This is an emissive road stud, NOT a dynamic lamp light.
            r['z']=min(zs,key=lambda z:abs(z-r['z']));r['y']=roads[0]['position']['y']+2.2;r['yaw']=0
            spot=(r['x'],r['z'])
            remove=spot in markers;markers.add(spot)
            reason='Ground center-line marker; deduplicate shared road'
        elif prior and r['asset'] in ('CS_Store_Front_01','CS_Store_Front_01_Blue','CS_Store_Front_01_Entrance'):
            r['z']+=24
            if r['asset'].endswith('Entrance'):r['x']+=5
            reason='Match user-calibrated storefront setback'
        elif prior and r['asset'] in ('CS_ATM','CS_ATM_Screen'):
            r['x']-=15;r['z']+=26;reason='Match paired user ATM placement'
        elif prior and r['asset']=='CS_Street_Straight_Arrow_Decal':
            a=math.radians(r['yaw']);r['x']-=90*math.sin(a);r['z']-=90*math.cos(a)
            reason='Match corrected approach-arrow setback'
        elif prior and r['asset']=='CS_Street_Double_Center_Line':
            near=min(junctions,key=lambda j:(r['x']-j['position']['x'])**2+(r['z']-j['position']['z'])**2)
            dx=r['x']-near['position']['x'];dz=r['z']-near['position']['z']
            if abs(math.hypot(dx,dz)-400)<.1:
                r['x']+=dx/4;r['z']+=dz/4;reason='Match user approach center-line cadence'
        elif prior and r['asset']=='CS_Stop_Light':
            signal_number+=1
            if signal_number%4 in (0,2):remove=True;reason='Remove redundant opposite signal silhouette'
        if reason:
            changes.append(dict(source_index=e['record_index'],reason=reason,before=before,after=None if remove else dict(r)))
            r['modified']=True
        if not remove:rows.append(r)
    def add(asset,x,y,z,yaw=0,group='polish',**kw):
        candidate=dict(asset=asset,x=x,y=y,z=z,yaw=yaw,group=group,**kw)
        if any(signature(r)==signature(candidate) for r in rows):return
        rows.append(candidate)
    # Six selected narrow buildings get a second, reachable exterior level.
    heroes=[p for p in parcels if p['width']==600][:6]
    for number,p in enumerate(heroes):
        x,z,g=p['x'],p['z'],p['ground']
        # Two 200-unit canopy bays support a 400-unit upper side gallery.
        for dz in (300,500):
            add('CS_Wall_01_Overhang',x,g,z+dz,90,group='upper-support')
            add('CS_Roof_Tile_2x2',x-120,g+100,z+dz,group='upper-deck')
        # Solid stepped blocks: 10 rise / 20 going, exact 200-unit total rise.
        # Use measured roof block geometry; its min Y=80 is compensated per step.
        for step in range(1,21):
            add('CS_Roof_Tile_2x2',x-120,g-40*step,z-210+20*step,group='upper-stair',scale=[.5,.5*step,.1])
            for side in (-1,1):
                add('CS_Sidewalk_Guard',x-120+side*50,g+step*10,z-210+step*20,90,group='upper-rail',scale=[.2,1,1])
        for dz in (250,350,450,550):add('CS_Sidewalk_Guard',x-220,g+200,z+dz,90,group='upper-rail')
        for dx in (-170,-70):add('CS_Sidewalk_Guard',x+dx,g+200,z+600,group='upper-rail')
        # Exact upper doorway aligned with the gallery; retain the rest of the shell.
        for r in rows:
            if r['asset']=='CS_Walls_01_Window_With_Bars' and abs(r['x']-x)<.1 and abs(r['z']-(z+400))<.1 and abs(r['y']-(g+200))<.1:
                if r['source_index'] in protected:continue
                changes.append(dict(source_index=r['source_index'],reason='Upper gallery access doorway',before=dict(r)))
                r['asset']='CS_Wall_01_Entry_01';r['replace_asset']=True;r['modified']=True
        # Tent clusters stay selective; preserve the user's original tents separately.
        if number in (1,4):
            for dz,asset in ((340,'Tent1'),(470,'Tent3')):
                add(asset,x-95,g-measured[asset]['min'][1],z+dz,180,group='sheltered-life')
        add('CS_Neon_02',x,g+200,z+300,90,group='upper-sign')
        for py,pz in ((g+110,z+400),(g+245,z+500)):
            add('White Light',x-120,py,pz,group='practical-light')
        # Sparse puddles beside the curb, leaving the crosswalk approaches clear.
        add('Puddle',x-380,g-10+2.05-measured['Puddle']['min'][1],z+350,number*35,group='road-detail')
    # Two service vehicles mid-block; the installed usable vehicle is a utility truck.
    for p in (parcels[2],parcels[26]):
        bx=p['x']+p['width']/2-900;bz=p['z']+p['depth']/2-900
        add('truck',bx+150,p['ground']-8-measured['truck']['min'][1],bz+900,90,group='parked-service')
    return rows,parcels,changes,protected,heroes

def load_scene(path):
    with FpmArchive(path) as f:
        data=f.read('map.ele');bank=parse_map_ent(f.read('map.ent'))
        return data,bank,parse_map_ele(data,bank['entries'])

def build(source,output):
    if output.exists():raise FpmError('Output must be new')
    old=json.loads((ROOT/'gameguru/buildplans/district12-v11-layout.json').read_text())
    measured=json.loads((ROOT/'docs/cybercity-kit-measurements.json').read_text())
    measured.update(json.loads((ROOT/'docs/city-polish-measurements.json').read_text()))
    data,bank,parsed=load_scene(source)
    if parsed['version']!=342:raise FpmError('Expected saved ELE 342')
    rows,parcels,changes,protected,heroes=plan(parsed,old,measured)
    # Route planning considers all additions and the user's own tents/overhang.
    # Expand scaled steps into measured bounds for the route obstacle planner.
    scene=copy.deepcopy(rows); route_measurements=dict(measured)
    for i,r in enumerate(scene):
        if 'scale' in r:
            label=r['asset']+'__'+str(i);b=copy.deepcopy(measured[r['asset']])
            for axis,s in enumerate(r['scale']):b['min'][axis]*=s;b['max'][axis]*=s
            route_measurements[label]=b;r['asset']=label
    extra_rows=extras.plan(parcels,scene,measurements=route_measurements)
    for p in heroes:
        resident=extra_rows[parcels.index(p)*6+5]
        resident.update(x=p['x']-120,y=p['ground']+200,z=p['z']+450,yaw=270,role='upper-resident')
    extras.validate(scene+extra_rows,parcels,route_measurements,city.hero.world_bounds,city.measured_city.intersects)
    rows.extend(extra_rows)
    paths=[e['path'] for e in bank['entries']];templates={}
    for e in parsed['entities'][1:]:
        name=city.key(e['asset'])
        if name not in templates and fabric.safe_template_entity(e,True)[0]:
            templates[name]=fabric.Template(name,e['asset'],e,data[e['record_start_offset']:e['record_end_offset']],str(source),'manual-baseline')
    lib={}
    for name in ('cybercity-dressing-templates-v11.json','city-extra-templates.json','city-polish-templates.json'):
        lib.update(json.loads((ROOT/'gameguru/buildplans'/name).read_text())['templates'])
    for name in sorted({r['asset'] for r in rows}-templates.keys()):
        item=lib[name]
        if item['asset'] not in paths:paths.append(item['asset'])
        raw=bytearray(base64.b64decode(item['raw_base64']));struct.pack_into('<i',raw,4,paths.index(item['asset'])+1)
        entries=parse_map_ent(fabric.serialize_map_ent(paths))['entries']
        e=parse_map_ele(struct.pack('<ii',342,1)+raw,entries)['entities'][0]
        if any(e['scale_xyz'].values()):raw=bytearray(scale_record(bytes(raw),(1,1,1)))
        templates[name]=fabric.Template(name,item['asset'],e,bytes(raw),item.get('source','library'),'exact-authored')
    records=[data[parsed['entities'][0]['record_start_offset']:parsed['entities'][0]['record_end_offset']]]
    for r in rows:
        idx=r.get('source_index')
        if idx and not r.get('modified'):
            e=parsed['entities'][idx-1];raw=data[e['record_start_offset']:e['record_end_offset']]
        else:
            t=templates[r['asset']]
            if idx and not r.get('replace_asset'):
                e=parsed['entities'][idx-1];t=fabric.Template(r['asset'],e['asset'],e,data[e['record_start_offset']:e['record_end_offset']],str(source),'modified-manual')
            raw=_patched_patch_record(t,t.parsed['bankindex'],fabric.Placement(r['asset'],r['x'],r['y'],r['z'],ry=r['yaw']))
            if 'scale' in r:raw=scale_record(raw,r['scale'])
            if r['group']=='extras':
                from fpm_prepare_extras import rewrite
                raw=rewrite(raw,r['name'])
        records.append(raw)
    ele=struct.pack('<ii',342,len(records))+b''.join(records);ent=fabric.serialize_map_ent(paths)
    check=parse_map_ele(ele,parse_map_ent(ent)['entries']);verify_raw_ele_roundtrip(ele,check)
    if not check['fully_traversed']:raise FpmError('Incomplete entity stream')
    for r,e in zip(rows,check['entities'][1:]):
        if city.key(e['asset'])!=r['asset'] or any(abs(e['position'][a]-r[a])>.03 for a in ('x','y','z')):raise FpmError('Saved placement mismatch')
    with FpmArchive(source) as f:
        visuals=f.read('visuals.ini').decode()
        visual_changes={'visuals.PostContrast#':'1.07','visuals.Exposure':'1.18','visuals.EnvProbeBrightness':'1.15','visuals.FogNearest#':'3000','visuals.FogDistance#':'16000'}
        for k,v in visual_changes.items():visuals=re.sub(r'(?m)^'+re.escape(k)+r'=[^\r\n]*',k+'='+v,visuals)
        members=fabric.archive_members_with_replacements(f,{'map.ele':ele,'map.ent':ent,'visuals.ini':visuals.encode()})
    try:
        write_zipcrypto_archive(output,members)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    final_data,final_bank,final=load_scene(output)
    if final_data!=ele or final['entity_count']!=len(records):raise FpmError('Saved archive mismatch')
    report=dict(version=12,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),entity_count=len(records),protected_manual_records=protected,changes=changes,counts=dict(Counter(r['group'] for r in rows)),heroes=[p['name'] for p in heroes],parcels=parcels,placements=rows,visual_changes=visual_changes,native_review='pending')
    output.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n');extras.write_lua(rows,output.with_suffix('.routes.lua'))
    print(json.dumps({k:v for k,v in report.items() if k not in ('placements','parcels','changes','protected_manual_records')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.source,a.output)
