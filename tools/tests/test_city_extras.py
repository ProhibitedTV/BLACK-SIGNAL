import copy
import json
import math
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
        walkers=[r for r in actors if r['route']]
        self.assertEqual(len(walkers),144)
        self.assertEqual(sum(not r['route'] for r in actors),72)
        self.assertEqual(len({r['asset'] for r in actors}),6)
        for r in walkers:
            self.assertGreaterEqual(len(r['route']),3)
            self.assertNotEqual(r['route'][0],r['route'][-1])
            distance=sum(math.dist(a,b) for a,b in zip(r['route'],r['route'][1:]))
            self.assertGreater(distance,400)
            self.assertLessEqual(
                max(math.dist(a,b) for a,b in zip(r['route'],r['route'][1:])),
                extras.MAX_ROUTE_STEP+0.01,
            )
        extras.validate(self.rows,self.parcels,self.measured,city.hero.world_bounds,city.measured_city.intersects)

    def test_road_shortcut_is_rejected(self):
        rows=copy.deepcopy(self.rows)
        actor=next(r for r in rows if r['group']=='extras' and len(r['route'])>1)
        actor['route'][1][0]=actor['bounds'][0]-100
        with self.assertRaises(ValueError):extras.validate(rows,self.parcels,self.measured,city.hero.world_bounds,city.measured_city.intersects)

    @unittest.skipIf(LuaRuntime is None,'Install lupa for the Lua movement simulation')
    def test_actual_lua_movement_uses_native_max_character_pathing(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        routes=lua.execute(extras.render_lua(self.rows))
        lua.globals().test_routes=routes
        lua.execute('''
          package.preload['scriptbank\\\\user\\\\black_signal\\\\bs_city_extra_routes']=function() return test_routes end
          g_Time=0; g_Entity={}; animations={}; native_targets={}; native_started={}; pending_path=nil; pending_count=0
          function CollisionOn(e) end
          function HideEntityAttachment(e) end
          function SetEntityAlwaysActive(e,v) end
          function SetEntityHealthSilent(e,v) end
          function SetEntityMoveSpeed(e,v) g_Entity[e].move_speed=v end
          function SetEntityTurnSpeed(e,v) g_Entity[e].turn_speed=v end
          function StopAnimation(e) end
          function SetAnimationName(e,n) animations[e]=n end
          function SetAnimationSpeed(e,v) end
          function LoopAnimation(e) end
          function GetEntityAnimationNameExist(e,n) return 1 end
          function CharacterControlLimbo(e) error('CharacterControlLimbo must not be used') end
          function CollisionOff(e) error('CollisionOff must not be used') end
          function PositionObject(...) error('PositionObject must not be used') end
          function RotateObject(...) error('RotateObject must not be used') end
          function SetPosition(...) error('SetPosition must not be used') end
          function SetRotation(...) error('SetRotation must not be used') end
          function AISetEntityPosition(...) error('AISetEntityPosition must not be used') end
          function GetEntityPosAng(e)
            local a=g_Entity[e]
            return a.x,a.y,a.z,0,a.yaw or 0,0
          end
          function RDFindPath(sx,sy,sz,tx,ty,tz)
            pending_path={tx,ty,tz}; pending_count=2
          end
          function RDGetPathPointCount() return pending_count end
          function SetEntityPathRotationMode(e,v) g_Entity[e].path_rotation=v end
          function StartMoveAndRotateToXYZ(e,speed,turn,tilt,stop)
            assert(pending_path~=nil,'StartMove called without RDFindPath')
            native_targets[e]={pending_path[1],pending_path[2],pending_path[3]}
            native_started[e]=(native_started[e] or 0)+1
          end
          function MoveAndRotateToXYZ(e,speed,turn,stop)
            if speed<=0 then return 0 end
            local target=native_targets[e]
            assert(target~=nil,'MoveAndRotateToXYZ called before StartMoveAndRotateToXYZ')
            local a=g_Entity[e]
            local dx,dz=target[1]-a.x,target[3]-a.z
            local d=math.sqrt(dx*dx+dz*dz)
            if d>0 then
              local step=math.min(d,math.max(1,speed*12))
              a.x=a.x+dx/d*step
              a.z=a.z+dz/d*step
              a.y=target[2]
            end
            return 1
          end
        ''')
        lua.execute((ROOT/'gameguru/Files/scriptbank/user/black_signal/bs_city_extra.lua').read_text())
        lua.execute('''
          actors_test={}
          for i=1,216 do
            local n=string.format('BS_EXTRA_%03d',i)
            local r=test_routes[n]
            g_Entity[i]={x=r.x,y=r.y,z=r.z,yaw=r.yaw}
            actors_test[i]=r
            bs_city_extra_init_name(i,n)
          end
          for frame=1,5000 do
            g_Time=frame*1000/30
            for i=1,216 do bs_city_extra_main(i) end
          end
          local moved=0
          for i=1,216 do
            local r=actors_test[i]
            local p=g_Entity[i]
            if #r.points>0 then
              local last=r.points[#r.points]
              assert((p.x-last[1])^2+(p.z-last[2])^2<200,'walker did not finish near route endpoint')
              assert((native_started[i] or 0)>0,'walker never started native MAX pathing')
              moved=moved+1
            else
              assert(p.x==r.x and p.z==r.z,'stationary extra drift')
            end
          end
          assert(moved==144,'not every walker used native pathing')

          -- A finished actor must stay at its endpoint instead of wrapping to spawn.
          local x,z=g_Entity[1].x,g_Entity[1].z
          for frame=1,120 do g_Time=g_Time+33;bs_city_extra_main(1) end
          assert((g_Entity[1].x-x)^2+(g_Entity[1].z-z)^2<0.01,'finished walker reset or teleported')

          -- Missing walk clips fail closed to idle instead of sliding or transform-driving.
          function GetEntityAnimationNameExist(e,n) return n=='Walk_Loop' and 0 or 1 end
          local r=actors_test[1]
          g_Entity[1].x=r.x;g_Entity[1].y=r.y;g_Entity[1].z=r.z
          bs_city_extra_init_name(1,'BS_EXTRA_001')
          local sx,sz=g_Entity[1].x,g_Entity[1].z
          for frame=1,60 do g_Time=g_Time+33;bs_city_extra_main(1) end
          assert(g_Entity[1].x==sx and g_Entity[1].z==sz,'missing walk clip caused sliding')
          assert(animations[1]=='Idle')
        ''')

if __name__=='__main__':unittest.main()
