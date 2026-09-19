-- DESCRIPTION: BLACK SIGNAL District 12 lived-in city fabric generator. Adds deterministic street walls, alleys, side streets, storefronts and dressing from Cyberpunk Streets entities already present in the level.

local bs_city_fabric = {}

local LEVEL_TOKEN = "black signal - district 12"
local MAX_CLONES = 460
local generated = false
local init_time = 0
local spawned = {}
local rng_state = 31743
local stats = { architecture = 0, storefronts = 0, props = 0, alleys = 0, side_streets = 0 }

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

local function is_original_entity(e)
    if GetEntitySpawnAtStart == nil then return true end
    local ok, state = pcall(GetEntitySpawnAtStart, e)
    if not ok then return true end
    return state ~= 2
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
        if ok and minx ~= nil and maxx ~= nil then
            return minx or -200, miny or 0, minz or -200, maxx or 200, maxy or 400, maxz or 200
        end
    end
    return -200, 0, -80, 200, 400, 80
end

local function template_span(e)
    if e == nil then return 400 end
    local minx, _, minz, maxx, _, maxz = safe_bounds(e)
    return math.max(math.abs(maxx - minx), math.abs(maxz - minz))
end

local function track_entity(e, kind)
    if e ~= nil and e > 0 then
        spawned[#spawned + 1] = e
        if kind ~= nil and stats[kind] ~= nil then
            stats[kind] = stats[kind] + 1
        end
    end
end

local function set_scale(e, sx, sy, sz)
    sx = sx or 100
    sy = sy or sx
    sz = sz or sx

    if ScaleObject ~= nil and g_Entity ~= nil and g_Entity[e] ~= nil then
        local obj = g_Entity[e].obj or 0
        if obj > 0 then
            pcall(ScaleObject, obj, sx, sy, sz)
            return
        end
    end

    if Scale ~= nil then
        pcall(Scale, e, sx)
    end
end

local function spawn_piece(template, x, bottom_y, z, yaw, sx, sy, sz, collision, cast_shadows, kind)
    if template == nil or template <= 0 then return nil, bottom_y end
    if #spawned >= MAX_CLONES then return nil, bottom_y end
    if SpawnNewEntity == nil then return nil, bottom_y end

    local newe = SpawnNewEntity(template)
    if newe == nil or newe <= 0 then return nil, bottom_y end

    local _, miny, _, _, maxy, _ = safe_bounds(template)
    local fy = (sy or sx or 100) / 100.0
    local pivot_y = bottom_y - (miny * fy)

    if ResetPosition ~= nil then pcall(ResetPosition, newe, x, pivot_y, z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, yaw or 0, 0) end
    set_scale(newe, sx or 100, sy or sx or 100, sz or sx or 100)
    if GravityOff ~= nil then pcall(GravityOff, newe) end

    if collision == true then
        if CollisionOn ~= nil then pcall(CollisionOn, newe) end
    else
        if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    end

    if cast_shadows == false and SetEntityCastShadows ~= nil then
        pcall(SetEntityCastShadows, newe, 0)
    end
    if Show ~= nil then pcall(Show, newe) end

    track_entity(newe, kind)
    return newe, pivot_y + (maxy * fy)
end

local function point_for_axis(axis, along, cross)
    if axis == "x" then return along, cross end
    return cross, along
end

local function frontage_yaw(axis, side)
    if axis == "x" then
        if side > 0 then return 180 end
        return 0
    end
    if side > 0 then return 270 end
    return 90
end

local function branch_yaw(axis, row_side)
    if axis == "x" then
        if row_side > 0 then return 270 end
        return 90
    end
    if row_side > 0 then return 180 end
    return 0
end

local function choose_facade(t, index)
    local r = random01()
    if index % 9 == 0 and t.entry ~= nil then return t.entry, "architecture" end
    if r < 0.13 and t.store_neon ~= nil then return t.store_neon, "storefronts" end
    if r < 0.28 and t.store_window ~= nil then return t.store_window, "storefronts" end
    if r < 0.56 and t.window ~= nil then return t.window, "architecture" end
    if r < 0.72 and t.entry ~= nil then return t.entry, "architecture" end
    if t.wall ~= nil then return t.wall, "architecture" end
    return t.corner or t.window or t.store_window, "architecture"
end

local function choose_clutter(t)
    local r = random01()
    if r < 0.28 then return t.trash end
    if r < 0.53 then return t.bottles end
    if r < 0.75 then return t.newspaper1 end
    return t.newspaper2 or t.newspaper1
end

local function spawn_prop(template, x, ground_y, z, yaw, scale)
    if template == nil then return end
    spawn_piece(template, x, ground_y, z, yaw or random_range(-18, 18), scale or 100, scale or 100, scale or 100, false, false, "props")
end

local function build_midrise(t, x, ground_y, z, yaw, scale, floors)
    local base = t.b1_base or t.b3_base or t.b1_floor or t.b3_floor
    local floor = t.b1_floor or t.b3_floor
    local top = t.b1_top or t.b3_top or floor
    if floor == nil then return end

    local _, next_y = spawn_piece(base, x, ground_y, z, yaw, scale, scale, scale, false, true, "architecture")
    local count = floors or random_int(2, 4)
    for i = 1, count do
        if #spawned >= MAX_CLONES - 2 then break end
        _, next_y = spawn_piece(floor, x, next_y, z, yaw, scale, scale, scale, false, true, "architecture")
    end
    spawn_piece(top, x, next_y, z, yaw, scale, scale, scale, false, true, "architecture")
end

local function scan_level()
    local t = {}
    local roads = {}
    local architecture_count = 0
    local minx, maxx = math.huge, -math.huge
    local minz, maxz = math.huge, -math.huge
    local ground_sum, ground_count = 0, 0

    local maxe = g_EntityElementMax or 0
    for e = 1, maxe do
        if g_Entity ~= nil and g_Entity[e] ~= nil and is_original_entity(e) then
            local path = safe_entity_path(e)

            if contains(path, "cs_wall_01.fpe") then t.wall = t.wall or e end
            if contains(path, "cs_walls_01_window_with_bars.fpe") then t.window = t.window or e end
            if contains(path, "cs_wall_01_entry_01.fpe") then t.entry = t.entry or e end
            if contains(path, "cs_wall_corner_01.fpe") then t.corner = t.corner or e end
            if contains(path, "cs_roof_tile_4x4.fpe") then t.roof4 = t.roof4 or e end
            if contains(path, "cs_roof_tile_2x2.fpe") then t.roof2 = t.roof2 or e end
            if contains(path, "cs_store_front_02_corner_with_window.fpe") then t.store_window = t.store_window or e end
            if contains(path, "cs_store_front_02_corner_neon_opposite.fpe") then t.store_neon = t.store_neon or e end
            if contains(path, "cs_trash_can.fpe") then t.trash = t.trash or e end
            if contains(path, "cs_street_lamp.fpe") then t.lamp = t.lamp or e end
            if contains(path, "cs_planter_01.fpe") then t.planter = t.planter or e end
            if contains(path, "cs_bottle_can_cluster_01.fpe") then t.bottles = t.bottles or e end
            if contains(path, "cs_newspaper_01.fpe") then t.newspaper1 = t.newspaper1 or e end
            if contains(path, "cs_newspaper_02.fpe") then t.newspaper2 = t.newspaper2 or e end
            if contains(path, "cs_sidewalk_straight_edge.fpe") then t.sidewalk_edge = t.sidewalk_edge or e end
            if contains(path, "cs_sidewalk_tile_4x4.fpe") then t.sidewalk_tile = t.sidewalk_tile or e end

            if contains(path, "cs_bg_building_01_base.fpe") then t.b1_base = t.b1_base or e end
            if contains(path, "cs_bg_building_01_floor.fpe") then t.b1_floor = t.b1_floor or e end
            if contains(path, "cs_bg_building_01_top.fpe") then t.b1_top = t.b1_top or e end
            if contains(path, "cs_bg_building_03_base.fpe") then t.b3_base = t.b3_base or e end
            if contains(path, "cs_bg_building_03_floor.fpe") then t.b3_floor = t.b3_floor or e end
            if contains(path, "cs_bg_building_03_top.fpe") then t.b3_top = t.b3_top or e end

            if contains(path, "cyberpunk streets booster pack") and
               (contains(path, "background buildings") or contains(path, "\\buildings\\") or
                contains(path, "store fronts") or contains(path, "streets and sidewalks")) then
                local x, y, z = safe_pos_ang(e)
                minx = math.min(minx, x)
                maxx = math.max(maxx, x)
                minz = math.min(minz, z)
                maxz = math.max(maxz, z)
                architecture_count = architecture_count + 1

                if contains(path, "streets and sidewalks\\streets\\") then
                    roads[#roads + 1] = { x = x, y = y, z = z }
                    ground_sum = ground_sum + y
                    ground_count = ground_count + 1
                end
            end
        end
    end

    if architecture_count == 0 or #roads == 0 then return nil end
    if t.wall == nil and t.window == nil and t.store_window == nil then return nil end

    local mean_x, mean_z = 0, 0
    for i = 1, #roads do
        mean_x = mean_x + roads[i].x
        mean_z = mean_z + roads[i].z
    end
    mean_x = mean_x / #roads
    mean_z = mean_z / #roads

    local var_x, var_z = 0, 0
    for i = 1, #roads do
        var_x = var_x + ((roads[i].x - mean_x) * (roads[i].x - mean_x))
        var_z = var_z + ((roads[i].z - mean_z) * (roads[i].z - mean_z))
    end

    local axis = "x"
    if var_z > var_x then axis = "z" end

    local along_min, along_max = math.huge, -math.huge
    local cross_sum = 0
    for i = 1, #roads do
        local along = roads[i].x
        local cross = roads[i].z
        if axis == "z" then
            along = roads[i].z
            cross = roads[i].x
        end
        along_min = math.min(along_min, along)
        along_max = math.max(along_max, along)
        cross_sum = cross_sum + cross
    end

    local ground_y = ground_sum / math.max(ground_count, 1)
    local cross_center = cross_sum / #roads
    local facade_template = t.wall or t.window or t.store_window
    local facade_step = clamp(template_span(facade_template) * 0.92, 280, 520)
    local road_step = 640
    if t.sidewalk_tile ~= nil then
        road_step = clamp(template_span(t.sidewalk_tile) * 1.20, 560, 980)
    end

    if (along_max - along_min) < 4200 then
        local c = (along_max + along_min) * 0.5
        along_min = c - 2400
        along_max = c + 2400
    end

    return {
        templates = t,
        axis = axis,
        along_min = along_min,
        along_max = along_max,
        cross_center = cross_center,
        ground_y = ground_y,
        facade_step = facade_step,
        road_offset = road_step,
        minx = minx,
        maxx = maxx,
        minz = minz,
        maxz = maxz
    }
end

local function is_reserved_slot(index, slots)
    for i = 1, #slots do
        if math.abs(index - slots[i]) <= 1 then return true end
    end
    return false
end

local function dress_frontage_slot(t, axis, side, along, front_cross, ground_y, yaw, index)
    local x, z = point_for_axis(axis, along, front_cross)
    local facade, kind = choose_facade(t, index)
    if facade ~= nil then
        spawn_piece(facade, x, ground_y, z, yaw, 100, 100, 100, true, true, kind)
    end

    local curb_cross = front_cross - (side * random_range(120, 190))
    local px, pz = point_for_axis(axis, along + random_range(-75, 75), curb_cross)

    if index % 4 == 0 and t.lamp ~= nil then
        spawn_prop(t.lamp, px, ground_y, pz, yaw, 100)
    elseif index % 5 == 0 and t.planter ~= nil then
        spawn_prop(t.planter, px, ground_y, pz, yaw, random_range(90, 108))
    elseif random01() < 0.30 then
        spawn_prop(choose_clutter(t), px, ground_y, pz, random_range(0, 360), random_range(88, 108))
    end
end

local function build_main_street_fabric(scan)
    local t = scan.templates
    local axis = scan.axis
    local step = scan.facade_step
    local along_start = scan.along_min - (step * 2)
    local along_end = scan.along_max + (step * 3)
    local module_count = math.floor((along_end - along_start) / step)
    module_count = clamp(module_count, 18, 34)

    local slots = {
        math.floor(module_count * 0.30),
        math.floor(module_count * 0.67)
    }

    local frontage_offset = scan.road_offset + (step * 0.45)
    local back_offset = frontage_offset + (step * 1.65)

    for side = -1, 1, 2 do
        local front_cross = scan.cross_center + (side * frontage_offset)
        local back_cross = scan.cross_center + (side * back_offset)
        local yaw = frontage_yaw(axis, side)

        for i = 0, module_count do
            if #spawned >= MAX_CLONES - 8 then break end
            local along = along_start + (i * step)

            if is_reserved_slot(i, slots) then
                if i == slots[1] or i == slots[2] then
                    stats.alleys = stats.alleys + 1
                    local gap_cross = front_cross + (side * random_range(140, 310))
                    local gx, gz = point_for_axis(axis, along, gap_cross)
                    spawn_prop(choose_clutter(t), gx, scan.ground_y, gz, random_range(0, 360), random_range(90, 108))
                    if t.trash ~= nil and random01() < 0.72 then
                        local tx, tz = point_for_axis(axis, along + random_range(-120, 120), gap_cross + side * 130)
                        spawn_prop(t.trash, tx, scan.ground_y, tz, yaw, 100)
                    end
                end
            else
                dress_frontage_slot(t, axis, side, along, front_cross, scan.ground_y, yaw, i)

                if i % 3 == 1 then
                    local bx, bz = point_for_axis(axis, along + random_range(-step * 0.15, step * 0.15), back_cross)
                    build_midrise(t, bx, scan.ground_y, bz, yaw, random_range(82, 105), random_int(1, 3))
                elseif i % 4 == 2 and t.wall ~= nil then
                    local bx, bz = point_for_axis(axis, along, back_cross)
                    spawn_piece(t.wall, bx, scan.ground_y, bz, yaw, 100, 100, 100, true, true, "architecture")
                end
            end
        end
    end

    return slots, along_start, step, frontage_offset
end

local function build_side_street_wing(scan, slot_index, along_start, step, frontage_offset, side)
    local t = scan.templates
    local axis = scan.axis
    local mouth = along_start + (slot_index * step)
    local branch_length = random_int(5, 7)
    local half_width = step * 1.05
    local branch_start = frontage_offset + (step * 0.80)
    local branch_yaw_left = branch_yaw(axis, -1)
    local branch_yaw_right = branch_yaw(axis, 1)

    stats.side_streets = stats.side_streets + 1

    for j = 0, branch_length do
        if #spawned >= MAX_CLONES - 8 then break end
        local outward = scan.cross_center + side * (branch_start + j * step)

        for row_side = -1, 1, 2 do
            local row_along = mouth + row_side * half_width
            local x, z = point_for_axis(axis, row_along, outward)
            local facade, kind = choose_facade(t, j + (row_side > 0 and 3 or 0))
            local yaw = branch_yaw_left
            if row_side > 0 then yaw = branch_yaw_right end

            if facade ~= nil then
                spawn_piece(facade, x, scan.ground_y, z, yaw, 100, 100, 100, true, true, kind)
            end

            if j % 3 == 1 and random01() < 0.82 then
                local prop_along = row_along - row_side * random_range(100, 170)
                local px, pz = point_for_axis(axis, prop_along, outward + side * random_range(-80, 80))
                local prop = t.planter
                if random01() < 0.58 then prop = choose_clutter(t) end
                spawn_prop(prop, px, scan.ground_y, pz, random_range(0, 360), random_range(90, 105))
            end
        end

        if j == branch_length and t.wall ~= nil then
            local cap_x, cap_z = point_for_axis(axis, mouth, outward + side * step * 0.8)
            spawn_piece(t.wall, cap_x, scan.ground_y, cap_z, frontage_yaw(axis, -side), 100, 100, 100, true, true, "architecture")
        end
    end
end

local function build_service_edges(scan)
    local t = scan.templates
    local axis = scan.axis
    local step = scan.facade_step
    local center_along = (scan.along_min + scan.along_max) * 0.5
    local edge_offset = scan.road_offset + step * 4.0

    for side = -1, 1, 2 do
        local service_cross = scan.cross_center + side * edge_offset
        local yaw = frontage_yaw(axis, -side)
        for i = -5, 5 do
            if #spawned >= MAX_CLONES - 6 then break end
            local along = center_along + i * step * 1.12
            if i ~= 0 and i ~= 1 then
                local x, z = point_for_axis(axis, along, service_cross)
                local facade = t.window or t.wall or t.entry
                if facade ~= nil then
                    spawn_piece(facade, x, scan.ground_y, z, yaw, 100, 100, 100, true, true, "architecture")
                end
                if i % 3 == 0 then
                    local prop = choose_clutter(t)
                    local px, pz = point_for_axis(axis, along + random_range(-80, 80), service_cross - side * 150)
                    spawn_prop(prop, px, scan.ground_y, pz, random_range(0, 360), random_range(90, 106))
                end
            else
                stats.alleys = stats.alleys + 1
            end
        end
    end
end

local function generate_fabric()
    local scan = scan_level()
    if scan == nil then return false end

    local slots, along_start, step, frontage_offset = build_main_street_fabric(scan)

    for s = 1, #slots do
        build_side_street_wing(scan, slots[s], along_start, step, frontage_offset, -1)
        build_side_street_wing(scan, slots[s], along_start, step, frontage_offset, 1)
    end

    build_service_edges(scan)

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_FABRIC_CLONES"] = #spawned
        g_UserGlobal["BLACK_SIGNAL_FABRIC_ARCHITECTURE"] = stats.architecture
        g_UserGlobal["BLACK_SIGNAL_FABRIC_STOREFRONTS"] = stats.storefronts
        g_UserGlobal["BLACK_SIGNAL_FABRIC_PROPS"] = stats.props
        g_UserGlobal["BLACK_SIGNAL_FABRIC_ALLEYS"] = stats.alleys
        g_UserGlobal["BLACK_SIGNAL_FABRIC_SIDE_STREETS"] = stats.side_streets
    end

    return #spawned > 0
end

local function should_run()
    local level = lower(g_LevelFilename or "")
    if level == "" then return false end
    return string.find(level, LEVEL_TOKEN, 1, true) ~= nil
end

function bs_city_fabric.init()
    generated = false
    spawned = {}
    rng_state = 31743
    stats = { architecture = 0, storefronts = 0, props = 0, alleys = 0, side_streets = 0 }
    init_time = g_Time or 0
end

function bs_city_fabric.main()
    if generated then return end
    if not should_run() then return end
    if (g_EntityElementMax or 0) <= 0 then return end

    local now = g_Time or 0
    if now < init_time + 650 then return end

    generated = generate_fabric()
end

function bs_city_fabric.quit()
    if DeleteNewEntity ~= nil then
        for i = #spawned, 1, -1 do
            pcall(DeleteNewEntity, spawned[i])
        end
    end
    spawned = {}
    generated = false
end

function bs_city_fabric_init(e)
    bs_city_fabric.init()
end

function bs_city_fabric_main(e)
    bs_city_fabric.main()
end

return bs_city_fabric
