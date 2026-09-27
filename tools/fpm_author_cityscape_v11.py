"""Populate every District 12 parcel using one editor-saved ELE schema and exact assets."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct

import fpm_author_hero_block as hero
import fpm_author_human_cityscape_v10_5 as human
import fpm_author_measured_city_v10 as measured_city
import fpm_author_road_network_v2 as roads
import fpm_author_road_semantics_v9_2 as semantics
import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, FpmError, parse_map_ele, parse_map_ent
from fpm_dress_cityscape_v11 import dress


def key(path):
    return Path((path or '').replace('\\', '/')).stem


def shell(p):
    """Closed 200-unit facade courses with four corners and a fully tiled roof."""
    rows=[]
    def add(asset,x,y,z,yaw=0):
        rows.append(dict(asset=asset,x=x,y=y,z=z,yaw=yaw,group=p['name']))
    x,z,w,d,y=p['x'],p['z'],p['width'],p['depth'],p['ground']
    for level in range(p['floors']):
        for cx,cz,yaw in ((x,z,0),(x+w,z,270),(x,z+d,90),(x+w,z+d,180)):
            add('CS_Wall_Corner_01',cx,y+level*200,cz,yaw)
        for side,length in ((0,w),(180,w),(90,d),(270,d)):
            for bay in range(200,length,200):
                px,pz=((x+bay,z) if side==0 else (x+bay,z+d) if side==180
                       else (x,z+bay) if side==90 else (x+w,z+bay))
                asset='CS_Walls_01_Window_With_Bars'
                if level==0 or (p['industrial'] and bay%400==0): asset='CS_Wall_01'
                if level==0 and bay==400 and side in (0,180):
                    asset='CS_Wall_01_Entry_04' if p['industrial'] else 'CS_Wall_01_Entry_01'
                add(asset,px,y+level*200,pz,side)
    for dx in range(100,w,200):
        for dz in range(100,d,200):
            add('CS_Roof_Tile_2x2',x+dx,y+p['floors']*200-80,z+dz)
    return rows


def plan(parsed):
    road_entities=[e for e in parsed['entities'] if roads.road_kind(e.get('asset'))]
    junctions=[e for e in road_entities if roads.road_kind(e['asset'])!='straight4']
    xs=sorted(set(round(e['position']['x'],2) for e in junctions))
    zs=sorted(set(round(e['position']['z'],2) for e in junctions))
    if len(xs)!=7 or len(zs)!=7 or any(abs(b-a-1800)>.01 for axis in (xs,zs) for a,b in zip(axis,axis[1:])):
        raise FpmError('Expected the captured seven-by-seven, 1800-unit road grid')
    ground=road_entities[0]['position']['y']
    rows=[]; parcels=[]
    def add(asset,x,y,z,yaw=0,group='pavement',**extras):
        rows.append(dict(asset=asset,x=x,y=y,z=z,yaw=yaw,group=group,**extras))
    # The old corner curves use corner pivots as centered junctions and miss their
    # straight-road endpoints. Square junction aprons meet the exact 300-unit ends.
    for e in road_entities:
        asset=key(e['asset'])
        if roads.road_kind(e['asset'])=='curve': asset='CS_Street_4_Way_2'
        add(asset,**e['position'],yaw=e['rotation_euler']['y'],group='roads')
    for iz,bz in enumerate(zs[:-1]):
        for ix,bx in enumerate(xs[:-1]):
            width=600 if (ix+iz)%4==1 else 800
            depth=600 if (ix*2+iz)%5==2 else 800
            industrial=iz<2 and ix%2==0
            floors=4 if industrial else 6+(ix*3+iz*2)%5
            if iz in (0,5) and not industrial: floors+=2
            p=dict(name=f'Block-{ix+1:02d}-{iz+1:02d}',x=bx+900-width/2,z=bz+900-depth/2,
                   width=width,depth=depth,floors=floors,ground=ground+10,industrial=industrial)
            parcels.append(p); rows.extend(shell(p))
            for dx,dz,yaw in ((300,300,0),(1500,300,270),(300,1500,90),(1500,1500,180)):
                add('CS_Sidewalk_Corner1_DropCurb',bx+dx,ground,bz+dz,yaw)
            for d in (600,800,1000,1200):
                for dx,dz,yaw in ((d,250,0),(d,1550,180),(250,d,90),(1550,d,270)):
                    add('CS_Sidewalk_Straight_Edge',bx+dx,ground,bz+dz,yaw)
            for dx in (500,900,1300):
                for dz in (500,900,1300): add('CS_Sidewalk_Tile_4x4',bx+dx,ground,bz+dz)
            for dz,yaw in ((270,0),(1530,180)):
                add('CS_Street_Lamp',bx+900,ground+10,bz+dz,yaw,group='lamps')
                add('CS_Street_Light_Marker',bx+900,ground+290,bz+dz,None,group='lights',dynamic=True)
    # Retain the manually calibrated markings and interior corner grammar, not old
    # experimental rails, utility poles, unknown records or generic material carriers.
    roles={r:key(spec['path']) for r,spec in fabric.ASSETS.items()}
    roles.update({r:Path(name).stem for r,name in human.ROLE_BASENAMES.items()})
    roles['road_arrow_straight']='CS_Street_Straight_Arrow_Decal'
    for item in semantics.plan_semantic_dressing(parsed):
        if item.role in ('sidewalk_corner','street_lamp','street_dynamic_light'): continue
        x,z=item.x,item.z
        if item.role=='crosswalk':
            # Drop-curb landing center: junction +300 +~49.5. The painted
            # texture occupies local Z=25.78..95.31 (center 60.55), so the
            # decal pivot belongs at +289, not the legacy +200 approach.
            angle=math.radians(item.ry)
            x+=89*math.sin(angle);z+=89*math.cos(angle)
        add(roles[item.role],x,item.y,z,item.ry,group='markings')
    for item in human.plan_human_cityscape(parsed):
        add(roles[item.role],item.x,item.y,item.z,item.ry,group='human-street')
    rows.extend(dress(parcels))
    return rows,parcels


def validate(rows,parcels,measurements):
    if len(parcels)!=36: raise FpmError('Every one of 36 parcels must be populated')
    signatures=[(r['asset'],round(r['x'],2),round(r['y'],2),round(r['z'],2),r['yaw']) for r in rows]
    if len(signatures)!=len(set(signatures)): raise FpmError('Duplicate placement')
    road_boxes=[hero.world_bounds(r,measurements) for r in rows if r['group']=='roads']
    for p in parcels:
        expected=shell(p)
        actual=[r for r in rows if r['group']==p['name']]
        # Exact per-course occupancy catches displaced walls/roofs as well as counts.
        signature=lambda r:(r['asset'],r['x'],r['y'],r['z'],r['yaw'])
        if Counter(map(signature,expected))!=Counter(map(signature,actual)):
            raise FpmError(f"Incomplete or displaced envelope: {p['name']}")
        for r in actual:
            box=hero.world_bounds(r,measurements)
            if any(measured_city.intersects(box,b) for b in road_boxes):
                raise FpmError(f"Road intrusion: {p['name']}")
        # Geometric roof-bottom/wall-top check uses the actual measured pivot offset.
        top=p['ground']+p['floors']*measurements['CS_Wall_01']['size'][1]
        for r in actual:
            if r['asset']=='CS_Roof_Tile_2x2' and abs(r['y']+measurements[r['asset']]['min'][1]-top)>.02:
                raise FpmError('Roof-to-wall seam mismatch')
    if sum(r['asset']=='CS_Sidewalk_Tile_4x4' for r in rows)!=36*9:
        raise FpmError('Incomplete parcel paving')
    byname={p['name']:p for p in parcels}
    for r in rows:
        if not r['group'].startswith('dressing-'):continue
        p=byname[r['parcel']];box=hero.world_bounds(r,measurements)
        if any(measured_city.intersects(box,b) for b in road_boxes):raise FpmError('Dressing road intrusion')
        if r['group'] in ('dressing-facade','dressing-rooftop'):continue
        envelope=(p['x']-20,p['x']+p['width']+20,p['z']-20,p['z']+p['depth']+20)
        if measured_city.intersects(box,envelope):raise FpmError('Dressing inside building')
        if box[0]<p['x']+450 and box[1]>p['x']+350 and (box[2]<p['z'] or box[3]>p['z']+p['depth']):
            raise FpmError('Dressing blocks door corridor')
        if r.get('support')=='ground' and abs(r['y']+measurements[r['asset']]['min'][1]-p['ground'])>1:
            raise FpmError('Dressing ground support mismatch')


def build(reference,output,measurements_path):
    if output.exists() or output.resolve()==reference.resolve(): raise FpmError('Output must be a new path')
    output.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(output.parent).free<500_000_000: raise FpmError('At least 500 MB free required')
    measurements=json.loads(measurements_path.read_text())
    with FpmArchive(reference) as source:
        bank=parse_map_ent(source.read('map.ent')); data=source.read('map.ele')
        parsed=parse_map_ele(data,bank['entries']); verify_raw_ele_roundtrip(data,parsed)
        rows,parcels=plan(parsed);validate(rows,parcels,measurements)
        templates={}
        for e in parsed['entities']:
            name=key(e.get('asset')); dynamic=name=='CS_Street_Light_Marker'
            ok,_=fabric.safe_template_entity(e,dynamic)
            if name and ok and name not in templates:
                templates[name]=fabric.Template(name,e['asset'],e,data[e['record_start_offset']:e['record_end_offset']],str(reference),'same-version-editor-record')
        bank_paths=[e['path'] for e in bank['entries']]
        library_path=Path(__file__).resolve().parents[1]/'gameguru/buildplans/cybercity-dressing-templates-v11.json'
        library=json.loads(library_path.read_text())
        for name in sorted({r['asset'] for r in rows}-templates.keys()):
            if name not in library['templates']:continue
            item=library['templates'][name]
            if item['version']!=parsed['version']:raise FpmError('Dressing template schema mismatch')
            if item['asset'] not in bank_paths:bank_paths.append(item['asset'])
            raw=bytearray(base64.b64decode(item['raw_base64']))
            struct.pack_into('<i',raw,fabric.ELE_BANKINDEX_OFFSET,bank_paths.index(item['asset'])+1)
            entries=parse_map_ent(fabric.serialize_map_ent(bank_paths))['entries']
            e=parse_map_ele(struct.pack('<ii',342,1)+raw,entries)['entities'][0]
            templates[name]=fabric.Template(name,item['asset'],e,bytes(raw),str(library_path),'exact-demo-record-upgraded-334-to-342')
        new_ent=fabric.serialize_map_ent(bank_paths)
        bank=parse_map_ent(new_ent)
        missing={r['asset'] for r in rows}-templates.keys()
        if missing: raise FpmError(f'Missing exact templates: {sorted(missing)}')
        first=parsed['entities'][0]
        if key(first['asset'])!='Player Start': raise FpmError('First record must preserve Player Start/global metadata')
        records=[data[first['record_start_offset']:first['record_end_offset']]]
        for r in rows:
            t=templates[r['asset']]
            records.append(_patched_patch_record(t,t.parsed['bankindex'],fabric.Placement(r['asset'],r['x'],r['y'],r['z'],ry=r['yaw'],rx=t.parsed['rotation_euler']['x'] if r.get('dynamic') else 0,rz=t.parsed['rotation_euler']['z'] if r.get('dynamic') else 0)))
        new_ele=struct.pack('<ii',parsed['version'],len(records))+b''.join(records)
        check=parse_map_ele(new_ele,bank['entries']);verify_raw_ele_roundtrip(new_ele,check)
        for r,e in zip(rows,check['entities'][1:]):
            if key(e['asset'])!=r['asset'] or any(abs(e['position'][a]-r[a])>.02 for a in ('x','y','z')):
                raise FpmError('Serialized placement mismatch')
        before={m['name']:m['sha256'] for m in source.member_manifest()}
        members=fabric.archive_members_with_replacements(source,{'map.ele':new_ele,'map.ent':new_ent})
    try:
        write_zipcrypto_archive(output,members)
        with FpmArchive(output) as result:
            final=parse_map_ele(result.read('map.ele'),parse_map_ent(result.read('map.ent'))['entries'])
            after={m['name']:m['sha256'] for m in result.member_manifest()}
        if final['entity_count']!=len(records) or not final['fully_traversed']: raise FpmError('Final FPM traversal failure')
        if set(k for k in before if before[k]!=after[k])-{'map.ele','map.ent'}: raise FpmError('Unexpected archive mutation')
    except Exception:
        output.unlink(missing_ok=True);raise
    report=dict(version=11,reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                ele_version=parsed['version'],entity_count=final['entity_count'],populated_parcels=len(parcels),
                counts=dict(Counter(r['group'] for r in rows)),assets=dict(Counter(r['asset'] for r in rows)),
                validation='pass',native_review='pending',parcels=parcels,placements=rows)
    output.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('placements','parcels','counts','assets')},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--measurements',type=Path,required=True);a=p.parse_args()
    build(a.reference,a.output,a.measurements)
