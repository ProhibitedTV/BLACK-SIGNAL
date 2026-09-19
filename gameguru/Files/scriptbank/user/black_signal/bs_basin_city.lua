-- DESCRIPTION: BLACK SIGNAL dense basin city generator. Fills the playable valley with deterministic blocks, mid-rises, storefront edges and perimeter towers using Cyberpunk Streets entities already authored in District 12.

local bs_basin_city = {}

local MAX_CLONES = 780
local generated = false
local init_time = 0
local spawned = {}
local rng_state = 7430317
local stats = { blocks = 0, buildings = 0, facades = 0, props = 0, towers = 0 }

local function lower(value)
    if value == nil then return "" end
    return string.lower(tostring(value))
end

local function contains(value, needle)
    return string.find(lower(value), lower(needle), 1, true) ~= nil
end

local function clamp(value, lo, hi)
    if value < lo then return lo end
    if value > hi then return hi end
    return value
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

local function span(e)
    if e == nil then return 500 end
    local minx, _, minz, maxx, _, maxz = bounds(e)
    return math.max(math.abs(maxx - minx), math.abs(maxz - minz))
end

local function track(e, kind)
    if e == nil or e <= 0 then return end
    spawned[#spawned + 1] = e
    if kind ~= nil and stats[kind] ~= nil then stats[kind] = stats[kind] + 1 end
end

local function spawn_piece(template, x, bottom_y, z, yaw, scale, collision, shadow, kind)
    if template == nil or template <= 0 then return nil, bottom_y end
    if #spawned >= MAX_CLONES then return nil, bottom_y end
    if SpawnNewEntity == nil then return nil, bottom_y end

    local newe = SpawnNewEntity(template)
    if newe == nil or newe <= 0 then return nil, bottom_y end

    scale = scale or 100
    local _, miny, _, _, maxy, _ = bounds(template)
    local factor = scale / 100.0
    local pivot_y = bottom_y - (miny * factor)

    if ResetPosition ~= nil then pcall(ResetPosition, newe, x, pivot_y, z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, yaw or 0, 0) end
    if Scale ~= nil then pcall(Scale, newe, scale) end
    if GravityOff ~= nil then pcall(GravityOff, newe) end

    if collision == true then
        if CollisionOn ~= nil then pcall(CollisionOn, newe) end
    else
        if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    end

    if shadow == false and SetEntityCastShadows ~= nil then pcall(SetEntityCastShadows, newe, 0) end
    if Show ~= nil then pcall(Show, newe) end

    track(newe, kind)
    return newe, pivot_y + (maxy * factor)
end

local function to_world(axis, along, cross)
    if axis == "x" then return along, cross end
    return cross, along
end

local function facing_yaw(axis, side)
    if axis == "x" then
        if side > 0 then return 180 end
        return 0
    end
    if side > 0 then return 270 end
    return 90
end

local function scan_level()
    local t = {}
    local roads = {}
    local originals = {}
    local ground_sum = 0
    local ground_count = 0

    local maxe = g_EntityElementMax or 0
    for e = 1, maxe do
        if g_Entity ~= nil and g_Entity[e] ~= nil and original_entity(e) then
            local path = entity_path(e)
            local x, y, z = pos_ang(e)

            if contains(path, "cs_bg_building_01_base2.fpe") then t.b1_base2 = t.b1_base2 or e end
            if contains(path, "cs_bg_building_01_base.fpe") then t.b1_base = t.b1_base or e end
            if contains(path, "cs_bg_building_01_floor_between.fpe") then t.b1_between = t.b1_between or e end
            if contains(path, "cs_bg_building_01_floor.fpe") then t.b1_floor = t.b1_floor or e end
            if contains(path, "cs_bg_building_01_top.fpe") then t.b1_top = t.b1_top or e end
            if contains(path, "cs_bg_building_03_base.fpe") then t.b3_base = t.b3_base or e end
            if contains(path, "cs_bg_building_03_floor.fpe") then t.b3_floor = t.b3_floor or e end
            if contains(path, "cs_bg_building_03_top.fpe") then t.b3_top = t.b3_top or e end

            if contains(path, "cs_wall_01.fpe") then t.wall = t.wall or e end
            if contains(path, "cs_walls_01_window_with_bars.fpe") then t.window = t.window or e end
            if contains(path, "cs_wall_01_entry_01.fpe") then t.entry = t.entry or e end
            if contains(path, "cs_wall_corner_01.fpe") then t.corner = t.corner or e end
            if contains(path, "cs_store_front_02_corner_with_window.fpe") then t.store_window = t.store_window or e end
            if contains(path, "cs_store_front_02_corner_neon_opposite.fpe") then t.store_neon = t.store_neon or e end

            if contains(path, "cs_street_lamp.fpe") then t.lamp = t.lamp or e end
            if contains(path, "cs_planter_01.fpe") then t.planter = t.planter or e end
            if contains(path, "cs_trash_can.fpe") then t.trash = t.trash or e end
            if contains(path, "cs_bottle_can_cluster_01.fpe") then t.bottles = t.bottles or e end
            if contains(path, "cs_newspaper_01.fpe") then t.paper1 = t.paper1 or e end
            if contains(path, "cs_newspaper_02.fpe") then t.paper2 = t.paper2 or e end

            if contains(path, "cyberpunk streets booster pack") and
               (contains(path, "background buildings") or contains(path, "\\buildings\\") or contains(path, "store fronts")) then
                originals[#originals + 1] = { x = x, z = z }
            end

            if contains(path, "cyberpunk streets booster pack") and contains(path, "streets and sidewalks\\streets\\") then
                roads[#roads + 1] = { x = x, y = y, z = z }
                ground_sum = ground_sum + y
                ground_count = ground_count + 1
            end
        end
    end

    if #roads == 0 then return nil end
    if t.b1_floor == nil and t.b3_floor == nil then return nil end

    local mean_x = 0
    local mean_z = 0
    for i = 1, #roads do
        mean_x = mean_x + roads[i].x
        mean_z = mean_z + roads[i].z
    end
    mean_x = mean_x / #roads
    mean_z = mean_z / #roads

    local var_x = 0
    local var_z = 0
    for i = 1, #roads do
        var_x = var_x + ((roads[i].x - mean_x) * (roads[i].x - mean_x))
        var_z = var_z + ((roads[i].z - mean_z) * (roads[i].z - mean_z))
    end

    local axis = "x"
    if var_z > var_x then axis = "z" end

    local center_along = mean_x
    local center_cross = mean_z
    if axis == "z" then
        center_along = mean_z
        center_cross = mean_x
    end

    local building_template = t.b1_floor or t.b3_floor
    local building_span = clamp(span(building_template), 420, 900)
    local block_step = clamp(building_span * 1.18, 720, 920)
    local road_half = clamp(block_step * 0.72, 520, 720)

    return {
        templates = t,
        roads = roads,
        originals = originals,
        axis = axis,
        center_along = center_along,
        center_cross = center_cross,
        ground_y = ground_sum / math.max(ground_count, 1),
        block_step = block_step,
        road_half = road_half
    }
end

local function near_original(scan, x, z, radius)
    local r2 = radius * radius
    for i = 1, #scan.originals do
        local dx = x - scan.originals[i].x
        local dz = z - scan.originals[i].z
        if (dx * dx + dz * dz) < r2 then return true end
    end
    return false
end

local function choose_building(t)
    if random01() < 0.55 and t.b1_floor ~= nil then
        return {
            base = (random01() < 0.28 and t.b1_base2 or t.b1_base) or t.b1_floor,
            floor = t.b1_floor,
            top = t.b1_top or t.b1_floor,
            between = t.b1_between
        }
    end
    return {
        base = t.b3_base or t.b1_base or t.b3_floor,
        floor = t.b3_floor or t.b1_floor,
        top = t.b3_top or t.b1_top or t.b3_floor or t.b1_floor,
        between = nil
    }
end

local function build_building(scan, x, z, band, tower)
    if #spawned >= MAX_CLONES - 8 then return end
    local t = scan.templates
    local kit = choose_building(t)
    if kit.floor == nil then return end

    local yaw = random_int(0, 3) * 90
    local scale = random_range(78, 110)
    local floors = random_int(2, 4) + math.max(0, band - 1)
    if tower then
        scale = random_range(88, 122)
        floors = random_int(5, 8)
    end

    local _, next_y = spawn_piece(kit.base or kit.floor, x, scan.ground_y, z, yaw, scale, false, true, "buildings")
    if kit.between ~= nil and random01() < 0.24 and not tower then
        _, next_y = spawn_piece(kit.between, x, next_y, z, yaw, scale, false, true, "buildings")
    end

    for i = 1, floors do
        if #spawned >= MAX_CLONES - 2 then break end
        _, next_y = spawn_piece(kit.floor, x, next_y, z, yaw, scale, false, band <= 2, "buildings")
    end
    spawn_piece(kit.top or kit.floor, x, next_y, z, yaw, scale, false, band <= 2, "buildings")

    if tower then stats.towers = stats.towers + 1 end
end

local function choose_facade(t, index)
    local r = random01()
    if index % 7 == 0 and t.store_neon ~= nil then return t.store_neon end
    if r < 0.27 and t.store_window ~= nil then return t.store_window end
    if r < 0.50 and t.window ~= nil then return t.window end
    if r < 0.70 and t.entry ~= nil then return t.entry end
    return t.wall or t.corner or t.store_window
end

local function choose_prop(t)
    local r = random01()
    if r < 0.22 then return t.trash end
    if r < 0.43 then return t.planter end
    if r < 0.65 then return t.bottles end
    if r < 0.83 then return t.paper1 end
    return t.paper2 or t.paper1
end

local function build_frontage(scan, along, side, slot)
    local t = scan.templates
    local step = scan.block_step
    local front_cross = scan.center_cross + side * (scan.road_half + step * 0.08)
    local yaw = facing_yaw(scan.axis, side)

    for offset = -1, 1 do
        local fa = along + offset * step * 0.26
        local x, z = to_world(scan.axis, fa, front_cross)
        local facade = choose_facade(t, slot + offset)
        if facade ~= nil and not near_original(scan, x, z, step * 0.28) then
            spawn_piece(facade, x, scan.ground_y, z, yaw, 100, false, true, "facades")
        end
    end

    if t.lamp ~= nil and slot % 2 == 0 then
        local lx, lz = to_world(scan.axis, along + step * 0.34, front_cross - side * step * 0.18)
        spawn_piece(t.lamp, lx, scan.ground_y, lz, yaw, 100, false, false, "props")
    end

    if random01() < 0.82 then
        local px, pz = to_world(scan.axis, along - step * 0.28, front_cross - side * step * 0.14)
        local prop = choose_prop(t)
        if prop ~= nil then spawn_piece(prop, px, scan.ground_y, pz, random_range(0, 360), random_range(88, 106), false, false, "props") end
    end
end

local function is_cross_street(slot)
    return slot == -3 or slot == 0 or slot == 3
end

local function build_basin_grid(scan)
    local step = scan.block_step
    local along_slots = 6
    local cross_bands = 3

    for side = -1, 1, 2 do
        for band = 1, cross_bands do
            local cross = scan.center_cross + side * (scan.road_half + (band - 0.35) * step)

            for slot = -along_slots, along_slots do
                if #spawned >= MAX_CLONES - 14 then return end

                local along = scan.center_along + slot * step
                local x, z = to_world(scan.axis, along, cross)

                -- Three broad cross streets cut through the urban mass. They are
                -- intentionally left open rather than filled with road meshes so the
                -- existing valley floor reads as asphalt/service paving without risking
                -- mismatched Cyberpunk Streets dimensions.
                if not is_cross_street(slot) then
                    local radius = step * 0.42
                    if not near_original(scan, x, z, radius) then
                        stats.blocks = stats.blocks + 1
                        local tower = (band == cross_bands and (math.abs(slot) % 2 == 0))
                        build_building(scan, x + random_range(-70, 70), z + random_range(-70, 70), band, tower)

                        -- A second mass in most blocks creates a narrow internal alley
                        -- instead of the single-building-on-a-pad look.
                        if random01() < 0.76 and #spawned < MAX_CLONES - 10 then
                            local da = random_range(step * 0.24, step * 0.34)
                            if random01() < 0.5 then da = -da end
                            local dc = side * random_range(step * 0.18, step * 0.28)
                            local ax, az = to_world(scan.axis, along + da, cross + dc)
                            if not near_original(scan, ax, az, step * 0.28) then
                                build_building(scan, ax, az, math.max(1, band - 1), false)
                            end
                        end
                    end

                    if band == 1 then build_frontage(scan, along, side, slot) end
                else
                    -- Dress cross-street mouths without closing the corridor.
                    if band == 1 then
                        local edge_cross = scan.center_cross + side * (scan.road_half + step * 0.48)
                        local ex, ez = to_world(scan.axis, along + side * step * 0.16, edge_cross)
                        local prop = choose_prop(scan.templates)
                        if prop ~= nil then spawn_piece(prop, ex, scan.ground_y, ez, random_range(0, 360), 100, false, false, "props") end
                    end
                end
            end
        end
    end
end

local function build_end_caps(scan)
    local step = scan.block_step
    local end_distance = step * 7.1

    for end_side = -1, 1, 2 do
        local along = scan.center_along + end_side * end_distance
        for cross_slot = -3, 3 do
            if #spawned >= MAX_CLONES - 10 then return end
            if cross_slot ~= 0 then
                local cross = scan.center_cross + cross_slot * step * 0.74
                local x, z = to_world(scan.axis, along, cross)
                build_building(scan, x, z, 3, true)
            end
        end
    end
end

local function generate()
    local scan = scan_level()
    if scan == nil then return false end

    build_basin_grid(scan)
    build_end_caps(scan)

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_BASIN_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_BASIN_CLONES"] = #spawned
        g_UserGlobal["BLACK_SIGNAL_BASIN_BLOCKS"] = stats.blocks
        g_UserGlobal["BLACK_SIGNAL_BASIN_BUILDINGS"] = stats.buildings
        g_UserGlobal["BLACK_SIGNAL_BASIN_FACADES"] = stats.facades
        g_UserGlobal["BLACK_SIGNAL_BASIN_PROPS"] = stats.props
        g_UserGlobal["BLACK_SIGNAL_BASIN_TOWERS"] = stats.towers
    end

    return #spawned > 0
end

function bs_basin_city.init()
    generated = false
    spawned = {}
    rng_state = 7430317
    stats = { blocks = 0, buildings = 0, facades = 0, props = 0, towers = 0 }
    init_time = g_Time or 0
end

function bs_basin_city.main()
    if generated then return end
    if (g_EntityElementMax or 0) <= 0 then return end

    -- This module intentionally has no level-name gate. gameloop.lua is deployed
    -- only inside the BLACK SIGNAL Separate Project Folder, so relying on
    -- g_LevelFilename here only made runtime generation fragile across Storyboard
    -- naming changes.
    local now = g_Time or 0
    if now < init_time + 450 then return end

    generated = generate()
end

function bs_basin_city.quit()
    if DeleteNewEntity ~= nil then
        for i = #spawned, 1, -1 do pcall(DeleteNewEntity, spawned[i]) end
    end
    spawned = {}
    generated = false
end

function bs_basin_city_init(e)
    bs_basin_city.init()
end

function bs_basin_city_main(e)
    bs_basin_city.main()
end

return bs_basin_city
