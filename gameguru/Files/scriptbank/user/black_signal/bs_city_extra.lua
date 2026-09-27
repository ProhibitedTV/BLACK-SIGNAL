-- DESCRIPTION: Background civilian following a prevalidated sidewalk-only film route.
-- No combat AI or navmesh shortcuts. Routes are generated with the saved FPM.
local routes = require "scriptbank\\user\\black_signal\\bs_city_extra_routes"
local actors = {}
local atan2 = math.atan2 or function(y,x) return math.atan(y,x) end

local function animation(e,s,name)
    if s.animation == name then return end
    if GetEntityAnimationNameExist(e,name) <= 0 then
        name = "Idle"
        s.disabled = true -- Never slide a character whose walk clip is absent.
    end
    StopAnimation(e)
    SetAnimationName(e,name)
    SetAnimationSpeed(e,1)
    LoopAnimation(e)
    s.animation = name
end

function bs_city_extra_init_name(e,name)
    local r=routes[name]
    if not r then return end
    actors[e]={route=r,x=r.x,z=r.z,yaw=r.yaw,next=2,last=g_Time or 0,wait=0}
    CharacterControlLimbo(e)
    CollisionOff(e) -- Cinematic extras cannot be pushed off their pavement route.
    HideEntityAttachment(e)
    SetEntityHealthSilent(e,999999)
    SetEntityAlwaysActive(e,1)
    animation(e,actors[e],#r.points>0 and "Walk_Loop" or "Idle")
end

function bs_city_extra_main(e)
    local s=actors[e]
    if not s then return end
    local now=g_Time or 0
    local dt=math.max(0,math.min((now-s.last)/1000,0.1))
    s.last=now
    local r=s.route
    CharacterControlLimbo(e)
    local moving=#r.points>0 and not s.disabled
    if s.wait>0 then
        s.wait=math.max(0,s.wait-dt)
        moving=false
    elseif moving then
        local p=r.points[s.next]
        local dx,dz=p[1]-s.x,p[2]-s.z
        local distance=math.sqrt(dx*dx+dz*dz)
        if distance<=r.speed*dt then
            s.x,s.z=p[1],p[2]
            local previous=r.points[(s.next-2)%#r.points+1]
            local segment=math.sqrt((p[1]-previous[1])^2+(p[2]-previous[2])^2)
            s.next=s.next%#r.points+1
            s.wait=segment>200 and r.pause or 0
            moving=s.wait==0
        else
            s.x=s.x+dx/distance*r.speed*dt
            s.z=s.z+dz/distance*r.speed*dt
            local target=math.deg(atan2(dx,dz))%360
            local turn=(target-s.yaw+180)%360-180
            s.yaw=(s.yaw+math.max(-180*dt,math.min(180*dt,turn)))%360
        end
    end
    animation(e,s,moving and "Walk_Loop" or "Idle")
    SetPosition(e,s.x,r.y,s.z)
    SetRotation(e,0,s.yaw,0)
    AISetEntityPosition(g_Entity[e].obj,s.x,r.y,s.z)
end

function bs_city_extra_exit(e)
    actors[e]=nil
end
