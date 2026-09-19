-- DESCRIPTION: BLACK SIGNAL runtime District 12 city expander. Clones only entities already present in the loaded level.

local bs_city_runtime = {}

local LEVEL_TOKEN = "black signal - district 12"
local MAX_CLONES = 620
local generated = false
local init_time = 0
local spawned = {}
local rng_state = 120743

local function lower(value)
    if value == nil then return "" end
    return string.lower(tostring(value))
end

local function contains(value, needle)
    return string.find(lower(value), lower(needle), 1, true) ~= nil
end

local function random01()
    -- Deterministic LCG so the skyline is identical on every take.
    rng_state = (rng_state * 1103515245 + 12345) % 2147483648
    return rng_state / 2147483648
end

local function random_range(a, b)
    return a + ((b - a) * random01())
end

local function random_int(a, b)
    return math.floor(random_range(a, b + 1))
end

local function safe_entity_path(e)
    if GetEntityFilePath == nil then return "" end
    local ok, value = pcall(GetEntityFilePath, e)
    if not ok or value == nil then return "" end
    return lower(value)
end

local function safe_pos_ang(e)
    if GetEntityPosAng ~= nil then
        local ok, x, y, z, ax, ay, az = pcall(GetEntityPosAng, e)
        if ok then
            return x or 0, y or 0, z or 0, ax or 0, ay or 0, az or 0
        end
    end
    if g_Entity ~= nil and g_Entity[e] ~= nil then
        local ent = g_Entity[e]
        return ent.x or 0, ent.y or 0, ent.z or 0, ent.anglex or 0, ent.angley or 0, ent.anglez or 0
    end
    return 0, 0, 0, 0, 0, 0
end

local function safe_bounds(e)
    if GetEntityColBox ~= nil then
        local ok, minx, miny, minz, maxx, maxy, maxz = pcall(GetEntityColBox, e)
        if ok and miny ~= nil and maxy ~= nil then
            return minx or -200, miny or 0, minz or -200, maxx or 200, maxy or 400, maxz or 200
        end
    end
    return -200, 0, -200, 200, 400, 200
end

local function track_entity(e)
    if e ~= nil and e > 0 then
        spawned[#spawned + 1] = e
    end
end

local function set_scale(e, sx, sy, sz)
    if Scale ~= nil then
        pcall(Scale, e, sx)
    end
    if ScaleObject ~= nil and g_Entity ~= nil and g_Entity[e] ~= nil then
        local obj = g_Entity[e].obj or 0
        if obj > 0 then
            pcall(ScaleObject, obj, sx, sy, sz)
        end
    end
end

local function spawn_piece(template, x, bottom_y, z, yaw, sx, sy, sz, cast_shadows)
    if template == nil or template <= 0 then return nil, bottom_y end
    if #spawned >= MAX_CLONES then return nil, bottom_y end
    if SpawnNewEntity == nil then return nil, bottom_y end

    local newe = SpawnNewEntity(template)
    if newe == nil or newe <= 0 then return nil, bottom_y end

    local _, miny, _, _, maxy, _ = safe_bounds(template)
    local fy = (sy or 100) / 100.0
    local pivot_y = bottom_y - (miny * fy)

    if ResetPosition ~= nil then pcall(ResetPosition, newe, x, pivot_y, z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, yaw, 0) end
    set_scale(newe, sx or 100, sy or sx or 100, sz or sx or 100)
    if GravityOff ~= nil then pcall(GravityOff, newe) end
    if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    if cast_shadows == false and SetEntityCastShadows ~= nil then
        pcall(SetEntityCastShadows, newe, 0)
    end
    if Show ~= nil then pcall(Show, newe) end

    track_entity(newe)
    local top_y = pivot_y + (maxy * fy)
    return newe, top_y
end

local function choose_template_pair(t)
    if random01() < 0.52 and t.b1_floor ~= nil then
        return {
            base = (random01() < 0.35 and t.b1_base2 or t.b1_base) or t.b1_floor,
            floor = t.b1_floor,
            between = t.b1_between,
            top = t.b1_top or t.b1_floor
        }
    end
    return {
        base = t.b3_base or t.b1_base or t.b3_floor,
        floor = t.b3_floor or t.b1_floor,
        between = nil,
        top = t.b3_top or t.b1_top or t.b3_floor or t.b1_floor
    }
end

local function build_tower(t, x, ground_y, z, ring_index)
    if #spawned >= MAX_CLONES - 4 then return end

    local kit = choose_template_pair(t)
    if kit.floor == nil then return end

    local yaw = random_int(0, 3) * 90
    local width_scale = random_range(78, 142)
    if ring_index >= 3 then
        width_scale = random_range(72, 165)
    end

    local floor_stretch = random_range(185, 330) + (ring_index * random_range(28, 62))
    local cast_shadows = ring_index <= 1

    local _, next_y = spawn_piece(kit.base, x, ground_y, z, yaw,
        width_scale, width_scale, width_scale, cast_shadows)

    if kit.between ~= nil and random01() < 0.28 then
        _, next_y = spawn_piece(kit.between, x, next_y, z, yaw,
            width_scale, width_scale, width_scale, cast_shadows)
    end

    _, next_y = spawn_piece(kit.floor, x, next_y, z, yaw,
        width_scale, floor_stretch, width_scale, cast_shadows)

    spawn_piece(kit.top, x, next_y, z, yaw,
        width_scale, width_scale, width_scale, cast_shadows)
end

local function scan_level()
    local templates = {}
    local minx, maxx = math.huge, -math.huge
    local minz, maxz = math.huge, -math.huge
    local ground_sum, ground_count = 0, 0
    local architecture_count = 0

    local maxe = g_EntityElementMax or 0
    for e = 1, maxe do
        if g_Entity ~= nil and g_Entity[e] ~= nil then
            local path = safe_entity_path(e)

            if contains(path, "cs_bg_building_01_base2.fpe") then templates.b1_base2 = templates.b1_base2 or e end
            if contains(path, "cs_bg_building_01_base.fpe") then templates.b1_base = templates.b1_base or e end
            if contains(path, "cs_bg_building_01_floor_between.fpe") then templates.b1_between = templates.b1_between or e end
            if contains(path, "cs_bg_building_01_floor.fpe") then templates.b1_floor = templates.b1_floor or e end
            if contains(path, "cs_bg_building_01_top.fpe") then templates.b1_top = templates.b1_top or e end
            if contains(path, "cs_bg_building_03_base.fpe") then templates.b3_base = templates.b3_base or e end
            if contains(path, "cs_bg_building_03_floor.fpe") then templates.b3_floor = templates.b3_floor or e end
            if contains(path, "cs_bg_building_03_top.fpe") then templates.b3_top = templates.b3_top or e end
            if contains(path, "cs_street_straight_4x.fpe") then templates.road = templates.road or e end

            if contains(path, "cyberpunk streets booster pack") and
               (contains(path, "background buildings") or contains(path, "\\buildings\\") or
                contains(path, "store fronts") or contains(path, "streets and sidewalks")) then
                local x, y, z = safe_pos_ang(e)
                minx = math.min(minx, x)
                maxx = math.max(maxx, x)
                minz = math.min(minz, z)
                maxz = math.max(maxz, z)
                architecture_count = architecture_count + 1

                if contains(path, "streets and sidewalks\\streets") then
                    ground_sum = ground_sum + y
                    ground_count = ground_count + 1
                end
            end
        end
    end

    if architecture_count == 0 then
        return nil
    end

    local ground_y = 0
    if ground_count > 0 then
        ground_y = ground_sum / ground_count
    elseif templates.b1_base ~= nil then
        local _, y = safe_pos_ang(templates.b1_base)
        ground_y = y
    elseif templates.b3_base ~= nil then
        local _, y = safe_pos_ang(templates.b3_base)
        ground_y = y
    end

    return {
        templates = templates,
        minx = minx,
        maxx = maxx,
        minz = minz,
        maxz = maxz,
        ground_y = ground_y
    }
end

local function generate_city()
    local scan = scan_level()
    if scan == nil then return false end

    local t = scan.templates
    if t.b1_floor == nil and t.b3_floor == nil then
        return false
    end

    local center_x = (scan.minx + scan.maxx) * 0.5
    local center_z = (scan.minz + scan.maxz) * 0.5
    local half_x = math.max((scan.maxx - scan.minx) * 0.5, 1800)
    local half_z = math.max((scan.maxz - scan.minz) * 0.5, 1800)

    -- Four deterministic skyline shells. They deliberately begin outside the
    -- authored city so Arrival Boulevard remains hand-directable while the
    -- horizon becomes a much larger metropolis in every direction.
    local ring_counts = { 22, 28, 34, 40 }
    for ring = 1, #ring_counts do
        local rx = half_x + 1200 + (ring * 1500)
        local rz = half_z + 1200 + (ring * 1350)
        local count = ring_counts[ring]

        for i = 0, count - 1 do
            if #spawned >= MAX_CLONES - 4 then break end
            local theta = (math.pi * 2.0 * i / count) + random_range(-0.055, 0.055)
            local jitter_x = random_range(-420, 420)
            local jitter_z = random_range(-420, 420)
            local x = center_x + (math.cos(theta) * rx) + jitter_x
            local z = center_z + (math.sin(theta) * rz) + jitter_z
            build_tower(t, x, scan.ground_y, z, ring)
        end
    end

    -- Corner infill gives the city mass between the authored district and the
    -- first skyline shell while preserving long central sightlines.
    for sx = -1, 1, 2 do
        for sz = -1, 1, 2 do
            for i = 1, 7 do
                if #spawned >= MAX_CLONES - 4 then break end
                local x = center_x + sx * (half_x + 650 + random_range(0, 2100))
                local z = center_z + sz * (half_z + 650 + random_range(0, 2100))
                build_tower(t, x, scan.ground_y, z, random_int(1, 2))
            end
        end
    end

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_CITY_CLONES"] = #spawned
    end

    return #spawned > 0
end

local function should_run()
    local level = lower(g_LevelFilename or "")
    if level == "" then return false end
    return string.find(level, LEVEL_TOKEN, 1, true) ~= nil
end

function bs_city_runtime.init()
    generated = false
    spawned = {}
    rng_state = 120743
    init_time = g_Time or 0
end

function bs_city_runtime.main()
    if generated then return end
    if not should_run() then return end
    if (g_EntityElementMax or 0) <= 0 then return end

    -- Let MAX finish publishing entity/object state before cloning from it.
    local now = g_Time or 0
    if now < init_time + 750 then return end

    generated = generate_city()
end

function bs_city_runtime.quit()
    if DeleteNewEntity ~= nil then
        for i = #spawned, 1, -1 do
            pcall(DeleteNewEntity, spawned[i])
        end
    end
    spawned = {}
    generated = false
end

-- Behaviour-style aliases keep this module valid if it is ever assigned to a
-- marker manually, and satisfy BLACK SIGNAL's Dynamic Lua validation rules.
function bs_city_runtime_init(e)
    bs_city_runtime.init()
end

function bs_city_runtime_main(e)
    bs_city_runtime.main()
end

return bs_city_runtime
