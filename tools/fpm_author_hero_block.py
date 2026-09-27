"""Build a separate four-parcel calibration backlot from measured Cyber City modules.

Uses whole, same-version donor records, never partial donor building clusters.
Keeps the donor terrain/environment; replaces entity placements in a NEW FPM.
This is a geometric candidate, not a declaration of native visual acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct

import fpm_author_street_fabric as fabric
from fpm_author_street_fabric_compat import _patched_patch_record
from fpm_clone_entity import verify_raw_ele_roundtrip, write_zipcrypto_archive
from fpm_inspect import FpmArchive, parse_map_ele, parse_map_ent

ORIGIN = (-25125.0, 1208.8, 6670.0)
PARCELS = [
    dict(name="Vale Exchange", x=-1300, z=500, width=800, depth=800, floors=6),
    dict(name="Municipal Annex", x=500, z=500, width=800, depth=800, floors=8),
    dict(name="Service Works", x=-1300, z=-1300, width=800, depth=600, floors=4),
    dict(name="Signal House", x=500, z=-1300, width=600, depth=800, floors=10),
]


def plan() -> list[dict]:
    out = []

    def add(asset, x, y, z, yaw=0, group="street"):
        out.append(dict(asset=asset, x=x, y=y, z=z, yaw=yaw, group=group))

    # One central junction, four surrounding blocks. Outer road ends are set boundaries.
    for x in (-1800, 0, 1800):
        for z in (-1800, 0, 1800):
            add("CS_Street_4_Way_2", x, 0, z)
    for line in (-1800, 0, 1800):
        for start in (-1800, 0):
            for delta in (500, 900, 1300):
                add("CS_Street_Straight_4X", start+delta, 0, line, 90)
                add("CS_Street_Straight_4X", line, 0, start+delta)

    # Repeat the measured, donor-authored curb/tile relationship for each full parcel.
    for bx in (-1800, 0):
        for bz in (-1800, 0):
            for dx, dz, yaw in ((300,300,0),(1500,300,270),(300,1500,90),(1500,1500,180)):
                add("CS_Sidewalk_Corner1_DropCurb", bx+dx, 0, bz+dz, yaw, "sidewalk")
            for d in (600,800,1000,1200):
                for dx,dz,yaw in ((d,250,0),(d,1550,180),(250,d,90),(1550,d,270)):
                    add("CS_Sidewalk_Straight_Edge", bx+dx, 0, bz+dz, yaw, "sidewalk")
            for dx in (500,900,1300):
                for dz in (500,900,1300):
                    add("CS_Sidewalk_Tile_4x4", bx+dx, 0, bz+dz, 0, "sidewalk")
            # Furniture only in the curb strip, away from the drop curbs and entries.
            for dx,dz,yaw in ((700,270,0),(1100,1530,180),(270,1100,90),(1530,700,270)):
                add("CS_Street_Lamp", bx+dx, 10, bz+dz, yaw, "furniture")

    for p in PARCELS:
        x,z,w,d,floors = (p[k] for k in ("x","z","width","depth","floors"))
        group = p["name"]
        for floor in range(floors):
            y = 10 + floor*200
            for cx,cz,yaw in ((x,z,0),(x+w,z,270),(x,z+d,90),(x+w,z+d,180)):
                add("CS_Wall_Corner_01",cx,y,cz,yaw,group)
            for side, length in ((0,w),(180,w),(90,d),(270,d)):
                for bay in range(200,length,200):
                    px,pz = ((x+bay,z) if side==0 else (x+bay,z+d) if side==180
                             else (x,z+bay) if side==90 else (x+w,z+bay))
                    asset = "CS_Walls_01_Window_With_Bars"
                    if floor==0 or (group=="Service Works" and bay%400==0):
                        asset = "CS_Wall_01"
                    if floor==0 and bay==400 and side in (0,180):
                        asset = "CS_Wall_01_Entry_04" if group=="Service Works" else "CS_Wall_01_Entry_01"
                    add(asset,px,y,pz,side,group)
        # Roof tile bottom is local Y=80. Seat it exactly on the last wall course.
        for dx in range(100,w,200):
            for dz in range(100,d,200):
                add("CS_Roof_Tile_2x2",x+dx,10+floors*200-80,z+dz,0,group)
    return out


def world_bounds(row, measured):
    b = measured[row["asset"]]
    angle=math.radians(row["yaw"]); c,s=math.cos(angle),math.sin(angle)
    pts=[(row["x"]+x*c+z*s,row["z"]-x*s+z*c)
         for x in (b["min"][0],b["max"][0]) for z in (b["min"][2],b["max"][2])]
    return (min(p[0] for p in pts),max(p[0] for p in pts),
            min(p[1] for p in pts),max(p[1] for p in pts))


def validate(rows, measured):
    # Fail closed when installed kit dimensions change.
    for name,size in {"CS_Wall_01":(200,200,30),"CS_Wall_Corner_01":(120,200,120),
                      "CS_Roof_Tile_2x2":(200,20,200),"CS_Street_Straight_4X":(400,0,400),
                      "CS_Street_4_Way_2":(600,0,600)}.items():
        if any(abs(a-b)>.02 for a,b in zip(measured[name]["size"],size)):
            raise ValueError(f"Uncalibrated dimensions: {name}")
    signatures=[(r['asset'],r['x'],r['y'],r['z'],r['yaw']) for r in rows]
    if len(set(signatures))!=len(rows):
        raise ValueError("Duplicate placements")
    roads=[world_bounds(r,measured) for r in rows if r['group']=='street']
    for p in PARCELS:
        shell=[r for r in rows if r['group']==p['name']]
        for r in shell:
            x0,x1,z0,z1=world_bounds(r,measured)
            if any(min(x1,b)-max(x0,a)>.01 and min(z1,d)-max(z0,c)>.01 for a,b,c,d in roads):
                raise ValueError(f"Building intersects road: {p['name']}")
        counts=Counter(r['asset'] for r in shell)
        expected_walls=p['floors']*(2*(p['width']//200-1)+2*(p['depth']//200-1))
        if counts['CS_Wall_Corner_01']!=p['floors']*4:
            raise ValueError("Incomplete corner courses")
        if sum(v for k,v in counts.items() if k.startswith('CS_Wall') and k!='CS_Wall_Corner_01')!=expected_walls:
            raise ValueError("Incomplete wall courses")
        if counts['CS_Roof_Tile_2x2']!=p['width']*p['depth']//40000:
            raise ValueError("Incomplete roof")
        roof_bottom=min(r['y']+measured[r['asset']]['min'][1] for r in shell if r['asset'].startswith('CS_Roof'))
        if abs(roof_bottom-(10+p['floors']*200))>.02:
            raise ValueError("Floating roof")


def build(donor: Path, output: Path, measured: dict) -> dict:
    if output.resolve()==donor.resolve() or output.exists():
        raise ValueError("Candidate output must be new; existing maps are never overwritten")
    output.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(output.parent).free < donor.stat().st_size * 2 + 10_000_000:
        raise OSError("Insufficient free disk space for a verified candidate; free at least 100 MB")
    rows=plan(); validate(rows,measured)
    with FpmArchive(donor) as source:
        ent=parse_map_ent(source.read('map.ent')); data=source.read('map.ele')
        parsed=parse_map_ele(data,ent['entries']); verify_raw_ele_roundtrip(data,parsed)
        templates={}
        for e in parsed['entities']:
            name=Path((e.get('asset') or '').replace('\\','/')).stem
            if name in measured and name not in templates:
                safe,_=fabric.safe_template_entity(e,False)
                if safe and e['profile_scale']==100 and all(abs(v)<.001 for v in e['scale_xyz'].values()):
                    templates[name]=fabric.Template(name,e['asset'],e,data[e['record_start_offset']:e['record_end_offset']],str(donor),'exact-donor')
        missing={r['asset'] for r in rows}-templates.keys()
        if missing: raise ValueError(f"Missing unscaled safe donor templates: {sorted(missing)}")
        # Preserve record 1's global group metadata while moving the Player Start.
        player=parsed['entities'][0]
        if not (player.get('asset') or '').lower().endswith('player start.fpe'):
            raise ValueError('Record 1 is not Player Start')
        ox,oy,oz=ORIGIN
        t=fabric.Template('player',player['asset'],player,data[player['record_start_offset']:player['record_end_offset']],str(donor),'original')
        records=[_patched_patch_record(t,player['bankindex'],fabric.Placement('player',ox,oy+12,oz-1300,ry=0))]
        for r in rows:
            t=templates[r['asset']]
            records.append(_patched_patch_record(t,t.parsed['bankindex'],fabric.Placement(r['asset'],ox+r['x'],oy+r['y'],oz+r['z'],ry=r['yaw'])))
        new_data=struct.pack('<ii',parsed['version'],len(records))+b''.join(records)
        check=parse_map_ele(new_data,ent['entries']); verify_raw_ele_roundtrip(new_data,check)
        if check['entity_count']!=len(records) or check['trailing_bytes']!=0:
            raise ValueError('Invalid generated entity stream')
        manifest={m['name']:m['sha256'] for m in source.member_manifest()}
        members=fabric.archive_members_with_replacements(source,{'map.ele':new_data})
    # Failed writes must not leave a partial file that looks like a playable map.
    try:
        write_zipcrypto_archive(output,members)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    with FpmArchive(output) as result:
        after={m['name']:m['sha256'] for m in result.member_manifest()}
        reparsed=parse_map_ele(result.read('map.ele'),parse_map_ent(result.read('map.ent'))['entries'])
    changed=[k for k in manifest if manifest[k]!=after.get(k)]
    if changed!=['map.ele'] or not reparsed['fully_traversed']:
        raise ValueError(f'Archive verification failed: {changed}')
    return dict(donor=str(donor.resolve()),output=str(output.resolve()),
                output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                entity_count=len(records),ele_version=parsed['version'],changed_members=changed,
                geometry_checks='pass',native_visual_review='pending - MAX window capture unavailable',
                origin=ORIGIN,parcels=PARCELS,counts=dict(Counter(r['group'] for r in rows)),placements=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--donor',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--measurements',type=Path,required=True)
    args=parser.parse_args()
    report=build(args.donor,args.output,json.loads(args.measurements.read_text()))
    args.output.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='placements'},indent=2))
