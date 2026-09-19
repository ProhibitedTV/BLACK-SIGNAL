-- DESCRIPTION: BLACK SIGNAL runtime skyline expander. Builds a closer deterministic tower belt around the District 12 basin from authored Cyberpunk Streets background-building templates.

local bs_city_runtime = {}

local MAX_CLONES = 520
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
    rng_state = (rng_state * 1103515245 + 12345) % 2147483648
    return rng_state / 2147483648
end

local function random_range(a, b)
    return a + ((b - a) * random01())
end

local function random_int(a, b)
    return math.floor(random_range(a, b + 1))
end

local function original_entity(e)
    if GetEntitySpawnAtStart == nil then return true end
    local ok, state = pcall(GetEntitySpawnAtStart, e)
    if not ok then return true end
    return state ~= 2
end

local function entity_path(e)
    if GetEntityFilePath == nil then return "" end
    local ok, value = pcall(GetEntityFilePath, e)
    if not ok or value == nil then return "" end
    return lower(value)
end

local function pos_ang(e)
    if GetEntityPosAng ~= nil then
        local ok, x, y, z, ax, ay, az = pcall(GetEntityPosAng, e)
        if ok then return x or 0, y or 0, z or 0, ax or 0, ay or 0, az or 0 end
    end
    if g_Entity ~= nil and g_Entity[e] ~= nil then
        local ent = g_Entity[e]
        return ent.x or 0, ent.y or 0, ent.z or 0, ent.anglex or 0, ent.angley or 0, ent.anglez or 0
    end
    return 0, 0, 0, 0, 0, 0
end

local function bounds(e)
    if GetEntityColBox ~= nil then
        local ok, minx, miny, minz, maxx, maxy, maxz = pcall(GetEntityColBox, e)
        if ok and miny ~= nil and maxy ~= nil then
            return minx or -200, miny or 0, minz or -200, maxx or 200, maxy or 400, maxz or 200
        end
    end
    return -200, 0, -200, 200, 400, 200
end

local function track(e)
    if e ~= nil and e > 0 then spawned[#spawned + 1] = e end
end

local function spawn_piece(template, x, bottom_y, z, yaw, scale, cast_shadows)
    if template == nil or template <= 0 then return nil, bottom_y end
    if #spawned >= MAX_CLONES then return nil, bottom_y end
    if SpawnNewEntity == nil then return nil, bottom_y end

    local newe = SpawnNewEntity(template)
    if newe == nil or newe <= 0 then return nil, bottom_y end

    scale = scale or 100
    local _, miny, _, _, maxy, _ = bounds(template)
    local factor = scale / 100.0
    local pivot_y = bottom_y - miny * factor

    if ResetPosition ~= nil then pcall(ResetPosition, newe, x, pivot_y, z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, yaw or 0, 0) end
    if Scale ~= nil then pcall(Scale, newe, scale) end
    if GravityOff ~= nil then pcall(GravityOff, newe) end
    if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    if cast_shadows == false and SetEntityCastShadows ~= nil then pcall(SetEntityCastShadows, newe, 0) end
    if Show ~= nil then pcall(Show, newe) end

    track(newe)
    return newe, pivot_y + maxy * factor
end

local function choose_kit(t)
    if random01() < 0.55 and t.b1_floor ~= nil then
        return {
            base = (random01() < 0.30 and t.b1_base2 or t.b1_base) or t.b1_floor,
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

local function build_tower(t, x, ground_y, z, ring)
    if #spawned >= MAX_CLONES - 10 then return end
    local kit = choose_kit(t)
    if kit.floor == nil then return end

    local yaw = random_int(0, 3) * 90
    local scale = random_range(74, 118)
    local floors = random_int(3 + ring, 5 + ring)
    local shadows = ring == 1

    local _, next_y = spawn_piece(kit.base or kit.floor, x, ground_y, z, yaw, scale, shadows)
    if kit.between ~= nil and random01() < 0.22 then
        _, next_y = spawn_piece(kit.between, x, next_y, z, yaw, scale, shadows)
    end
    for i = 1, floors do
        if #spawned >= MAX_CLONES - 2 then break end
        _, next_y = spawn_piece(kit.floor, x, next_y, z, yaw, scale, shadows)
    end
    spawn_piece(kit.top or kit.floor, x, next_y, z, yaw, scale, shadows)
end

local function scan_level()
    local t = {}
    local minx, maxx = math.huge, -math.huge
    local minz, maxz = math.huge, -math.huge
    local ground_sum = 0
    local ground_count = 0
    local count = 0

    local maxe = g_EntityElementMax or 0
    for e = 1, maxe do
        if g_Entity ~= nil and g_Entity[e] ~= nil and original_entity(e) then
            local path = entity_path(e)

            if contains(path, "cs_bg_building_01_base2.fpe") then t.b1_base2 = t.b1_base2 or e end
            if contains(path, "cs_bg_building_01_base.fpe") then t.b1_base = t.b1_base or e end
            if contains(path, "cs_bg_building_01_floor_between.fpe") then t.b1_between = t.b1_between or e end
            if contains(path, "cs_bg_building_01_floor.fpe") then t.b1_floor = t.b1_floor or e end
            if contains(path, "cs_bg_building_01_top.fpe") then t.b1_top = t.b1_top or e end
            if contains(path, "cs_bg_building_03_base.fpe") then t.b3_base = t.b3_base or e end
            if contains(path, "cs_bg_building_03_floor.fpe") then t.b3_floor = t.b3_floor or e end
            if contains(path, "cs_bg_building_03_top.fpe") then t.b3_top = t.b3_top or e end

            if contains(path, "cyberpunk streets booster pack") and
               (contains(path, "background buildings") or contains(path, "\\buildings\\") or contains(path, "store fronts")) then
                local x, _, z = pos_ang(e)
                minx = math.min(minx, x)
                maxx = math.max(maxx, x)
                minz = math.min(minz, z)
                maxz = math.max(maxz, z)
                count = count + 1
            end

            if contains(path, "cyberpunk streets booster pack") and contains(path, "streets and sidewalks\\streets\\") then
                local _, y = pos_ang(e)
                ground_sum = ground_sum + y
                ground_count = ground_count + 1
            end
        end
    end

    if count == 0 then return nil end
    if t.b1_floor == nil and t.b3_floor == nil then return nil end

    return {
        templates = t,
        center_x = (minx + maxx) * 0.5,
        center_z = (minz + maxz) * 0.5,
        half_x = math.max((maxx - minx) * 0.5, 650),
        half_z = math.max((maxz - minz) * 0.5, 650),
        ground_y = ground_sum / math.max(ground_count, 1)
    }
end

local function generate_city()
    local scan = scan_level()
    if scan == nil then return false end

    local ring_counts = { 20, 26, 32 }
    local ring_add_x = { 480, 980, 1550 }
    local ring_add_z = { 440, 900, 1400 }

    for ring = 1, #ring_counts do
        local rx = scan.half_x + ring_add_x[ring]
        local rz = scan.half_z + ring_add_z[ring]
        local count = ring_counts[ring]

        for i = 0, count - 1 do
            if #spawned >= MAX_CLONES - 10 then break end
            local theta = (math.pi * 2.0 * i / count) + random_range(-0.045, 0.045)
            local x = scan.center_x + math.cos(theta) * rx + random_range(-150, 150)
            local z = scan.center_z + math.sin(theta) * rz + random_range(-150, 150)
            build_tower(scan.templates, x, scan.ground_y, z, ring)
        end
    end

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_CITY_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_CITY_CLONES"] = #spawned
    end

    return #spawned > 0
end

function bs_city_runtime.init()
    generated = false
    spawned = {}
    rng_state = 120743
    init_time = g_Time or 0
end

function bs_city_runtime.main()
    if generated then return end
    if (g_EntityElementMax or 0) <= 0 then return end

    -- gameloop.lua exists only inside the BLACK SIGNAL Separate Project Folder;
    -- do not gate generation on Storyboard filename strings.
    local now = g_Time or 0
    if now < init_time + 1050 then return end
    generated = generate_city()
end

function bs_city_runtime.quit()
    if DeleteNewEntity ~= nil then
        for i = #spawned, 1, -1 do pcall(DeleteNewEntity, spawned[i]) end
    end
    spawned = {}
    generated = false
end

function bs_city_runtime_init(e)
    bs_city_runtime.init()
end

function bs_city_runtime_main(e)
    bs_city_runtime.main()
end

return bs_city_runtime
