import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'.black-signal/test-deps'))
import fpm_author_cityscape_v11 as city
import fpm_city_extras as extras
try:
    from lupa import LuaRuntime
except ImportError:
    LuaRuntime=None

class ExtrasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        entities=[dict(record_index=z*7+x+1,asset='CS_Street_4_Way_2.fpe',position=dict(x=x*1800.,y=1208.8,z=z*1800.),rotation_euler=dict(x=0.,y=0.,z=0.)) for z in range(7) for x in range(7)]
        cls.rows,cls.parcels=city.plan(dict(entities=entities))
        cls.measured=json.loads((ROOT/'docs/cybercity-kit-measurements.json').read_text())

    def test_sidewalk_routes_and_distribution(self):
        actors=[r for r in self.rows if r['group']=='extras']
        self.assertEqual(sum(bool(r['route']) for r in actors),144)
        self.assertEqual(sum(not r['route'] for r in actors),72)
        self.assertEqual(len({r['asset'] for r in actors}),6)
        extras.validate(self.rows,self.parcels,self.measured,city.hero.world_bounds,city.measured_city.intersects)

    def test_road_shortcut_is_rejected(self):
        rows=copy.deepcopy(self.rows)
        actor=next(r for r in rows if r['group']=='extras')
        actor['route'][1][0]=actor['bounds'][0]-100
        with self.assertRaises(ValueError):extras.validate(rows,self.parcels,self.measured,city.hero.world_bounds,city.measured_city.intersects)

    @unittest.skipIf(LuaRuntime is None,'Install lupa for the Lua movement simulation')
    def test_actual_lua_movement_ten_minutes(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        routes=lua.execute(extras.render_lua(self.rows))
        lua.globals().test_routes=routes
        lua.execute('''
          package.preload['scriptbank\\\\user\\\\black_signal\\\\bs_city_extra_routes']=function() return test_routes end
          g_Time=0; g_Entity={}; positions={}; rotations={}; animations={}
          function CharacterControlLimbo(e) end
          function CollisionOff(e) end
          function HideEntityAttachment(e) end
          function SetEntityAlwaysActive(e,v) end
          function SetEntityHealthSilent(e,v) end
          function StopAnimation(e) end
          function SetAnimationName(e,n) animations[e]=n end
          function SetAnimationSpeed(e,v) end
          function LoopAnimation(e) end
          function GetEntityAnimationNameExist(e,n) return 1 end
          function SetPosition(e,x,y,z) positions[e]={x,y,z} end
          function SetRotation(e,x,y,z) rotations[e]=y end
          function AISetEntityPosition(e,x,y,z) end
        ''')
        lua.execute((ROOT/'gameguru/Files/scriptbank/user/black_signal/bs_city_extra.lua').read_text())
        lua.execute('''
          actors_test={}
          for i=1,216 do
            local n=string.format('BS_EXTRA_%03d',i)
            g_Entity[i]={obj=i}; actors_test[i]=test_routes[n]
            bs_city_extra_init_name(i,n)
          end
          moved={}
          for frame=1,18000 do
            g_Time=frame*1000/30
            for i=1,216 do
              local r=actors_test[i]
              bs_city_extra_main(i)
              local p=positions[i]
              assert(math.abs(p[2]-r.y)<0.001,'height drift')
              if #r.points>0 then
                local on_route=false
                for k,a in ipairs(r.points) do
                  local b=r.points[k%#r.points+1]
                  local dx,dz=b[1]-a[1],b[2]-a[2]
                  local t=math.max(0,math.min(1,((p[1]-a[1])*dx+(p[3]-a[2])*dz)/(dx*dx+dz*dz)))
                  if (p[1]-a[1]-t*dx)^2+(p[3]-a[2]-t*dz)^2<0.01 then on_route=true;break end
                end
                assert(on_route,'left validated sidewalk corridor')
                if (p[1]-r.x)^2+(p[3]-r.z)^2>10000 then moved[i]=true end
              else
                assert(p[1]==r.x and p[3]==r.z,'stationary extra drift')
              end
            end
          end
          local count=0;for _ in pairs(moved) do count=count+1 end
          assert(count==144,'not every walker moved')
          -- A stalled frame must not teleport an actor along the route.
          local p=positions[1];g_Time=g_Time+60000;bs_city_extra_main(1)
          assert((positions[1][1]-p[1])^2+(positions[1][3]-p[3])^2<=16.01)
          function GetEntityAnimationNameExist(e,n) return n=='Walk_Loop' and 0 or 1 end
          bs_city_extra_init_name(1,'BS_EXTRA_001')
          for frame=1,60 do g_Time=g_Time+33;bs_city_extra_main(1) end
          assert(positions[1][1]==actors_test[1].x and positions[1][3]==actors_test[1].z,'missing walk clip caused sliding')
          assert(animations[1]=='Idle')
        ''')

if __name__=='__main__':unittest.main()
