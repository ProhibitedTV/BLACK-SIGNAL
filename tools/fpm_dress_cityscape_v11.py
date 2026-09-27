"""Measured commercial frontages, delivery yards and pavement furniture."""

def dress(parcels):
    rows=[]
    for i,p in enumerate(parcels):
        x,z,w,d,y=p['x'],p['z'],p['width'],p['depth'],p['ground']
        def add(asset,dx,dy,dz,yaw=0,zone='service',support=None):
            rows.append(dict(asset=asset,x=x+dx,y=y+dy,z=z+dz,yaw=yaw,
                group='dressing-'+zone,parcel=p['name'],support=support))
        for bay in range(200,w,200):
            asset='CS_Store_Front_01_Entrance' if bay==400 else ('CS_Store_Front_01_Blue' if i%3==0 else 'CS_Store_Front_01')
            add(asset,bay,0,-24,zone='facade')
        add('CS_Store_Front_01_Sign',400,145,-24,zone='facade')
        add('CS_Wall_01_NeonDecor_01_Sign_02_Computers',200,0,0,zone='facade')
        add('CS_Neon_01' if i%2 else 'CS_Neon_02',200,200,0,zone='facade')
        # Matched pivots retain the separate luminous screen and shelter graphics.
        add('CS_ATM',90,0,-36,zone='retail',support='ground')
        add('CS_ATM_Screen',90,0,-36,zone='facade')
        # Shop displays/deliveries leave the entry bay and through-route clear.
        for j in range(3):
            add('CS_Box_01',175+j*38,0,-74,zone='products',support='ground')
            add('CS_Box_02',175+j*38,10.44,-74,zone='products')
            add('CS_Can_01' if j%2 else 'CS_Can_03',175+j*38,21.2,-74,zone='products')
        add('CS_Bench',w-100,0,-120,180,zone='furniture',support='ground')
        add('CS_Trash_Can',w-30,0,-120,zone='furniture',support='ground')
        # Rear doors are at x+400. Service pockets stay on either side.
        add('CS_Dumpster_Closed',140,0,d+65,180,support='ground')
        if p['industrial']:add('CS_Dumpster_Closed',w-90,0,d+65,180,support='ground')
        for j in range(3):
            add('CS_Trashbag_0'+str(j+1),225+j*33,0,d+57+(j%2)*25,j*70,support='ground')
        add('CS_Cardboard',140,0,d+115,20,support='ground')
        add('CS_Bottle_Can_Cluster_01',240,0,d+110,40,support='ground')
        add('CS_Newspaper_01',315,0,d+105,15,support='ground')
        add('CS_Newspaper_02',w-100,0,d+100,120,support='ground')
        for j in range(3):add('CS_Box_02',w+65,0,150+j*35,j*20,support='ground')
        # Roof units and their stands share a pivot; stand bottom is local Y=58.
        for dx in (180,w-100):
            for asset in ('CS_AirCon_01','CS_AirCon_01_Stand'):
                add(asset,dx,p['floors']*200+20-58,d-160,zone='rooftop')
        if i%6==2:
            add('CS_Bus_Stop',w+25,0,d/2,270,zone='transit',support='ground')
            add('CS_Bus_Stop_Neon_Sign',w+25,0,d/2,270,zone='facade')
            add('CS_Bench',w+58,0,d/2,270,zone='transit',support='ground')
        add('CS_Fireplug',w+70,0,65,zone='furniture',support='ground')
    return rows
