-- DESCRIPTION: Background civilian following a prevalidated sidewalk-only film route.
-- Movement deliberately uses GameGuru MAX's native character pathing API.  Native
-- review showed that manually writing entity/object transforms fights the MAX
-- character controller and produces a short walk/snap-back loop.
local routes = require "scriptbank\\user\\black_signal\\bs_city_extra_routes"
local actors = {}

local ARRIVE_DISTANCE = 12
local STOP_DISTANCE = 5
local TURN_SPEED = 100

local function animation(e,s,name)
    if s.animation == name then return end
    if GetEntityAnimationNameExist(e,name) <= 0 then
        name = "Idle"
        s.disabled = true -- Never slide a character whose walk clip is absent.
    end
    StopAnimation(e)
    SetAnimationName(e,name)
    SetAnimationSpeed(e,0.85)
    LoopAnimation(e)
    s.animation = name
end

local function stop_native(e,s)
    if s.path_started then
        MoveAndRotateToXYZ(e,0,0,0)
    end
    s.path_started = false
end

local function begin_segment(e,s)
    local r=s.route
    local p=r.points[s.next]
    if not p then
        s.finished=true
        stop_native(e,s)
        return false
    end

    local ex,ey,ez=GetEntityPosAng(e)
    RDFindPath(ex,ey,ez,p[1],r.y,p[2])
    local count=RDGetPathPointCount()
    if not count or count<=0 then
        -- Fail closed.  A background extra that cannot obtain a native MAX path
        -- should idle where it is, not fall back to transform writes that can
        -- fight the character controller or cut across the road.
        s.disabled=true
        stop_native(e,s)
        return false
    end

    SetEntityPathRotationMode(e,1)
    StartMoveAndRotateToXYZ(e,s.native_speed,TURN_SPEED,0,STOP_DISTANCE)
    s.path_started=true
    return true
end

local function distance_to_target(e,s)
    local p=s.route.points[s.next]
    if not p then return 0 end
    local x,y,z=GetEntityPosAng(e)
    local dx,dz=p[1]-x,p[2]-z
    return math.sqrt(dx*dx+dz*dz)
end

-- GameGuru MAX supplies the placed entity name through the _init_name callback,
-- which binds each actor to its generated BS_EXTRA_* route.
function bs_city_extra_init(e)
    actors[e] = nil
end

function bs_city_extra_init_name(e,name)
    local r=routes[name]
    if not r then return end

    local move_speed=math.max(65,math.min(90,math.floor((r.speed or 36)*2.2)))
    actors[e]={
        route=r,
        next=2,
        finished=#r.points<=1,
        disabled=false,
        path_started=false,
        native_speed=move_speed/100,
        animation=nil,
    }

    -- Keep the native character controller alive.  The stock MAX npc_control
    -- script uses this same RDFindPath -> StartMoveAndRotateToXYZ ->
    -- MoveAndRotateToXYZ movement stack; do not put these actors in Limbo and do
    -- not directly PositionObject/SetPosition them.
    CollisionOn(e)
    HideEntityAttachment(e)
    SetEntityHealthSilent(e,999999)
    SetEntityAlwaysActive(e,1)
    SetEntityMoveSpeed(e,move_speed)
    SetEntityTurnSpeed(e,TURN_SPEED)

    if #r.points>1 then
        animation(e,actors[e],"Walk_Loop")
        if not actors[e].disabled then begin_segment(e,actors[e]) end
    else
        animation(e,actors[e],"Idle")
    end
end

function bs_city_extra_main(e)
    local s=actors[e]
    if not s then return end

    local moving=not s.disabled and not s.finished and #s.route.points>1
    if moving then
        if not s.path_started then
            moving=begin_segment(e,s)
        end
        if moving and s.path_started then
            -- Let MAX own both the entity transform and character controller.
            -- This is intentionally the same movement API family used by the
            -- stock MAX NPC patrol implementation.
            MoveAndRotateToXYZ(e,s.native_speed,TURN_SPEED,STOP_DISTANCE)
            if distance_to_target(e,s)<=ARRIVE_DISTANCE then
                stop_native(e,s)
                if s.next>=#s.route.points then
                    s.finished=true
                    moving=false
                else
                    s.next=s.next+1
                    moving=begin_segment(e,s)
                end
            end
        end
    else
        stop_native(e,s)
    end

    animation(e,s,moving and "Walk_Loop" or "Idle")
end

function bs_city_extra_exit(e)
    local s=actors[e]
    if s then stop_native(e,s) end
    actors[e]=nil
end
