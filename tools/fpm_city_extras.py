"""Deterministic, sidewalk-only film extras; no road-crossing navmesh routes."""
import math
import heapq
import json
from pathlib import Path

SCRIPT=r'user\black_signal\bs_city_extra.lua'
ASSETS=[f'{sex} {n}' for sex in ('female','male') for n in (1,2,3)]
RADIUS=18

def obstacles(rows,measurements,world_bounds,ground):
    out=[]
    for r in rows:
        if r['group']=='extras' or r['asset'] not in measurements or r['yaw'] is None:continue
        if r['group'] in ('pavement','markings','lights') or r['group']=='dressing-rooftop':continue
        m=measurements[r['asset']]
        if r['y']+m['min'][1]>=ground+80 or r['y']+m['max'][1]<ground+.1:continue
        out.append((r,world_bounds(r,measurements)))
    return out

def block_route(p,rows,measurements):
    from fpm_author_hero_block import world_bounds
    bx=p['x']+p['width']/2-900;bz=p['z']+p['depth']/2-900
    obs=[b for _,b in obstacles(rows,measurements,world_bounds,p['ground']) if b[1]>=bx+300 and b[0]<=bx+1500 and b[3]>=bz+300 and b[2]<=bz+1500]
    obs.append((p['x']-20,p['x']+p['width']+20,p['z']-20,p['z']+p['depth']+20))
    free=set()
    margin=RADIUS+5
    for ix in range(59):
        for iz in range(59):
            x,z=bx+320+ix*20,bz+320+iz*20
            if not any(a-margin<x<b+margin and c-margin<z<d+margin for a,b,c,d in obs):free.add((ix,iz))
    anchors=[(29,1),(57,29),(29,57),(1,29)]
    def clear_line(a,b):
        ax,az=bx+320+a[0]*20,bz+320+a[1]*20
        dx,dz=(b[0]-a[0])*20,(b[1]-a[1])*20
        for left,right,low,high in obs:
            t0,t1=0.,1.
            for origin,delta,lo,hi in ((ax,dx,left-margin,right+margin),(az,dz,low-margin,high+margin)):
                if abs(delta)<1e-9:
                    if origin<lo or origin>hi:t0,t1=1.,0.;break
                else:
                    v0,v1=sorted(((lo-origin)/delta,(hi-origin)/delta))
                    t0=max(t0,v0);t1=min(t1,v1)
                    if t0>t1:break
            if t0<=t1:return False
        return True
    route=[]
    for start,goal in zip(anchors,anchors[1:]+anchors[:1]):
        if start not in free or goal not in free:raise ValueError('Blocked sidewalk anchor')
        todo=[(0,start)];cost={start:0};prev={}
        while todo:
            _,at=heapq.heappop(todo)
            if at==goal:break
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt=(at[0]+dx,at[1]+dz)
                if nxt not in free or (at[0]+dx,at[1]) not in free or (at[0],at[1]+dz) not in free:continue
                score=cost[at]+math.hypot(dx,dz)
                if score<cost.get(nxt,float('inf')):
                    cost[nxt]=score;prev[nxt]=at
                    heapq.heappush(todo,(score+math.dist(nxt,goal),nxt))
        if goal not in cost:raise ValueError('No sidewalk-only route around block')
        segment=[goal]
        while segment[-1]!=start:segment.append(prev[segment[-1]])
        segment.reverse()
        smooth=[segment[0]];at=0
        while at<len(segment)-1:
            far=len(segment)-1
            while far>at+1 and not clear_line(segment[at],segment[far]):far-=1
            if not clear_line(segment[at],segment[far]):raise ValueError('Unsafe sidewalk smoothing segment')
            smooth.append(segment[far]);at=far
        route.extend(smooth[:-1])
    # Remove collinear intermediate grid points; all resulting segments follow
    # the same checked corridor. Every corner remains inside the paved parcel.
    compact=[]
    for i,b in enumerate(route):
        a,c=route[i-1],route[(i+1)%len(route)]
        if (b[0]-a[0])*(c[1]-b[1])!=(b[1]-a[1])*(c[0]-b[0]):compact.append(b)
    return [[bx+320+x*20,bz+320+z*20] for x,z in compact]

def plan(parcels,scene,measurements=None):
    rows=[]
    measured=measurements or json.loads((Path(__file__).resolve().parents[1]/'docs/cybercity-kit-measurements.json').read_text())
    for i,p in enumerate(parcels):
        bx=p['x']+p['width']/2-900;bz=p['z']+p['depth']/2-900
        # Chamfered corners avoid the corner planters. These routes never join
        # another block, cross a road, or invoke unconstrained navmesh steering.
        route=block_route(p,scene,measured)
        if i%2:route.reverse()
        for j in range(6):
            walking=j<4
            phase=len(route)*j//4
            points=route[phase:]+route[:phase] if walking else []
            x,z=points[0] if walking else ((p['x']+320,p['z']-100) if j==4 else (p['x']-100,p['z']+p['depth']/2))
            yaw=math.degrees(math.atan2(points[1][0]-x,points[1][1]-z))%360 if walking else (0 if j==4 else 90)
            rows.append(dict(asset=ASSETS[(i*5+j)%6],x=x,y=p['ground'],z=z,yaw=yaw,
                group='extras',parcel=p['name'],name=f'BS_EXTRA_{len(rows)+1:03d}',
                route=points,speed=32+(i%5)*2,pause=1+(i%3),role='walker' if walking else 'shopper',
                bounds=[bx+300,bx+1500,bz+300,bz+1500]))
    return rows

def samples(row):
    points=row['route']
    if not points:return [(row['x'],row['z'])]
    out=[]
    for a,b in zip(points,points[1:]+points[:1]):
        count=max(1,math.ceil(math.dist(a,b)/5))
        out.extend((a[0]+(b[0]-a[0])*k/count,a[1]+(b[1]-a[1])*k/count) for k in range(count+1))
    return out

def validate(rows,parcels,measurements,world_bounds,intersects):
    extras=[r for r in rows if r['group']=='extras']
    if len(extras)!=216:raise ValueError('Expected 216 background extras')
    obstacles=[]
    for r in rows:
        if r['group']=='extras' or r['asset'] not in measurements or r['yaw'] is None:continue
        if r['group'] in ('pavement','markings','lights') or r['group'].startswith('dressing-facade') or r['group']=='dressing-rooftop':continue
        obstacles.append((r,world_bounds(r,measurements)))
    byname={p['name']:p for p in parcels}
    for r in extras:
        p=byname[r['parcel']];lo,hi,bottom,top=r['bounds']
        envelope=(p['x']-20,p['x']+p['width']+20,p['z']-20,p['z']+p['depth']+20)
        local=[(o,b) for o,b in obstacles if b[1]>=lo and b[0]<=hi and b[3]>=bottom and b[2]<=top]
        for x,z in samples(r):
            box=(x-RADIUS,x+RADIUS,z-RADIUS,z+RADIUS)
            if box[0]<lo or box[1]>hi or box[2]<bottom or box[3]>top:raise ValueError('Extra leaves paved sidewalk')
            if intersects(box,envelope):raise ValueError('Extra enters building')
            for o,b in local:
                # Ignore geometry above the head and props entirely below feet.
                m=measurements[o['asset']]
                if o['y']+m['min'][1]>=r['y']+80 or o['y']+m['max'][1]<r['y']+.1:continue
                if intersects(box,b):raise ValueError(f"Extra route collision: {r['name']} at {x,z} / {o['asset']} at {b}")

def render_lua(rows):
    lines=['-- Generated from the validated saved city layout.','return {']
    for r in rows:
        if r['group']!='extras':continue
        pts=','.join('{'+f'{x:.4f},{z:.4f}'+'}' for x,z in r['route'])
        lines.append(f'  ["{r["name"]}"]={{x={r["x"]:.4f},y={r["y"]:.4f},z={r["z"]:.4f},yaw={r["yaw"]:.4f},speed={r["speed"]},pause={r["pause"]},points={{{pts}}}}},')
    lines.append('}')
    return '\n'.join(lines)+'\n'

def write_lua(rows,path):
    Path(path).write_text(render_lua(rows))
