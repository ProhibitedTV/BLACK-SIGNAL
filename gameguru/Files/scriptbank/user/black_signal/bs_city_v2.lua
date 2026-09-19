-- DESCRIPTION: BLACK SIGNAL robust District 12 city generator. Builds dense city blocks from all level entity indices without relying on g_Entity population state.

local bs_city_v2 = {}

local MAX_CLONES = 900
local generated = false
local init_time = 0
local spawned = {}
local rng_state = 12074317
local status = "idle"
local last_error = ""
local stats = { roads = 0, templates = 0, blocks = 0, clones = 0 }

local function lower(value)
    if value == nil then return "" end
    return string.lower(tostring(value))
end

local function normalize_path(value)
    local p = lower(value)
    p = string.gsub(p, "/", "\\")
    return p
end

local function contains(value, needle)
    return string.find(normalize_path(value), normalize_path(needle), 1, true) ~= nil
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
    return normalize_path(value)
end

local function pos_ang(e)
    if GetEntityPosAng ~= nil then
        local ok, x, y, z, ax, ay, az = pcall(GetEntityPosAng, e)
        if ok and x ~= nil then
            return x or 0, y or 0, z or 0, ax or 0, ay or 0, az or 0
        end
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
        if ok and minx ~= nil and maxx ~= nil and miny ~= nil and maxy ~= nil then
            return minx, miny, minz, maxx, maxy, maxz
        end
    end
    return -200, 0, -200, 200, 400, 200
end

local function is_known_road(path)
    return contains(path, "cs_street_straight_4x.fpe") or
           contains(path, "cs_street_t-intersect_3.fpe") or
           contains(path, "cs_street_4_way_2.fpe")
end

local function is_cyberpunk_architecture(path)
    if not contains(path, "cyberpunk streets booster pack") then return false end
    return contains(path, "background buildings") or
           contains(path, "store fronts") or
           contains(path, "buildings") or
           is_known_road(path)
end

local function safe_scale(e, scale)
    if Scale ~= nil then pcall(Scale, e, scale) end
end

local function spawn_piece(template, x, bottom_y, z, yaw, scale, collision, shadow)
    if template == nil or template <= 0 then return nil, bottom_y end
    if #spawned >= MAX_CLONES then return nil, bottom_y end
    if SpawnNewEntity == nil then return nil, bottom_y end

    local ok, newe = pcall(SpawnNewEntity, template)
    if not ok or newe == nil or newe <= 0 then return nil, bottom_y end

    scale = scale or 100
    local _, miny, _, _, maxy, _ = bounds(template)
    local factor = scale / 100.0
    local pivot_y = bottom_y - (miny * factor)

    if ResetPosition ~= nil then pcall(ResetPosition, newe, x, pivot_y, z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, yaw or 0, 0) end
    safe_scale(newe, scale)
    if GravityOff ~= nil then pcall(GravityOff, newe) end
    if collision then
        if CollisionOn ~= nil then pcall(CollisionOn, newe) end
    else
        if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    end
    if shadow == false and SetEntityCastShadows ~= nil then pcall(SetEntityCastShadows, newe, 0) end
    if Show ~= nil then pcall(Show, newe) end

    spawned[#spawned + 1] = newe
    stats.clones = #spawned
    return newe, pivot_y + (maxy * factor)
end

local function scan_level()
    local t = {}
    local roads = {}
    local architecture = {}
    local ground_sum = 0
    local ground_count = 0
    local maxe = g_EntityElementMax or 0

    for e = 1, maxe do
        if original_entity(e) then
            local path = entity_path(e)
            if path ~= "" then
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
                if contains(path, "cs_store_front_02_corner_with_window.fpe") then t.store_window = t.store_window or e end
                if contains(path, "cs_store_front_02_corner_neon_opposite.fpe") then t.store_neon = t.store_neon or e end
                if contains(path, "cs_street_lamp.fpe") then t.lamp = t.lamp or e end
                if contains(path, "cs_planter_01.fpe") then t.planter = t.planter or e end
                if contains(path, "cs_trash_can.fpe") then t.trash = t.trash or e end

                if is_known_road(path) then
                    roads[#roads + 1] = { x = x, y = y, z = z }
                    ground_sum = ground_sum + y
                    ground_count = ground_count + 1
                end

                if is_cyberpunk_architecture(path) then
                    architecture[#architecture + 1] = { x = x, y = y, z = z, e = e, path = path }
                end
            end
        end
    end

    stats.roads = #roads
    local template_count = 0
    for _, value in pairs(t) do if value ~= nil then template_count = template_count + 1 end end
    stats.templates = template_count

    if t.b1_floor == nil and t.b3_floor == nil then
        status = "no building floor templates"
        return nil
    end

    local samples = roads
    if #samples == 0 then samples = architecture end
    if #samples == 0 then
        status = "no road or architecture samples"
        return nil
    end

    local mean_x, mean_z = 0, 0
    for i = 1, #samples do
        mean_x = mean_x + samples[i].x
        mean_z = mean_z + samples[i].z
    end
    mean_x = mean_x / #samples
    mean_z = mean_z / #samples

    local var_x, var_z = 0, 0
    for i = 1, #samples do
        local dx = samples[i].x - mean_x
        local dz = samples[i].z - mean_z
        var_x = var_x + dx * dx
        var_z = var_z + dz * dz
    end
    local axis = "x"
    if var_z > var_x then axis = "z" end

    -- Player position is the best center for a visibly useful film set. Fall back
    -- to the authored road/architecture centroid if the player globals are absent.
    local center_x = mean_x
    local center_z = mean_z
    if g_PlayerPosX ~= nil and g_PlayerPosZ ~= nil then
        center_x = g_PlayerPosX
        center_z = g_PlayerPosZ
    end

    local ground_y = 0
    if ground_count > 0 then
        ground_y = ground_sum / ground_count
    elseif g_PlayerPosY ~= nil then
        ground_y = g_PlayerPosY - 80
    else
        ground_y = samples[1].y or 0
    end

    return {
        templates = t,
        architecture = architecture,
        axis = axis,
        center_x = center_x,
        center_z = center_z,
        ground_y = ground_y
    }
end

local function choose_kit(t)
    if random01() < 0.58 and t.b1_floor ~= nil then
        return {
            base = (random01() < 0.25 and t.b1_base2 or t.b1_base) or t.b1_floor,
            floor = t.b1_floor,
            between = t.b1_between,
            top = t.b1_top or t.b1_floor
        }
    end
    return {
        base = t.b3_base or t.b1_base or t.b3_floor or t.b1_floor,
        floor = t.b3_floor or t.b1_floor,
        between = nil,
        top = t.b3_top or t.b1_top or t.b3_floor or t.b1_floor
    }
end

local function build_tower(scan, x, z, tier)
    if #spawned >= MAX_CLONES - 12 then return end
    local kit = choose_kit(scan.templates)
    if kit.floor == nil then return end

    local scale = random_range(82, 118)
    local floors = random_int(2, 4) + tier
    local yaw = random_int(0, 3) * 90
    local _, next_y = spawn_piece(kit.base or kit.floor, x, scan.ground_y, z, yaw, scale, false, tier <= 2)

    if kit.between ~= nil and random01() < 0.25 then
        _, next_y = spawn_piece(kit.between, x, next_y, z, yaw, scale, false, tier <= 2)
    end

    for i = 1, floors do
        if #spawned >= MAX_CLONES - 2 then break end
        _, next_y = spawn_piece(kit.floor, x, next_y, z, yaw, scale, false, tier <= 2)
    end
    spawn_piece(kit.top or kit.floor, x, next_y, z, yaw, scale, false, tier <= 2)
end

local function to_world(scan, along, cross)
    if scan.axis == "x" then
        return scan.center_x + along, scan.center_z + cross
    end
    return scan.center_x + cross, scan.center_z + along
end

local function build_dense_grid(scan)
    local t = scan.templates
    local along_step = 780
    local cross_step = 720
    local road_half = 560

    -- 13 blocks long by 8 deep, with the central boulevard and three cross streets
    -- left open. This deliberately fills the visible basin before worrying about
    -- distant skyline shells.
    for side = -1, 1, 2 do
        for band = 1, 4 do
            local cross = side * (road_half + band * cross_step)
            for slot = -6, 6 do
                if #spawned >= MAX_CLONES - 20 then return end

                local cross_street = (slot == -3 or slot == 0 or slot == 3)
                if not cross_street then
                    local along = slot * along_step
                    local x, z = to_world(scan, along + random_range(-80, 80), cross + random_range(-70, 70))
                    local tier = band
                    build_tower(scan, x, z, tier)
                    stats.blocks = stats.blocks + 1

                    -- Secondary mass creates internal alleys/service canyons.
                    if random01() < 0.72 and #spawned < MAX_CLONES - 12 then
                        local ax, az = to_world(scan,
                            along + random_range(230, 330) * (random01() < 0.5 and -1 or 1),
                            cross + side * random_range(180, 260))
                        build_tower(scan, ax, az, math.max(1, tier - 1))
                    end

                    -- Near-boulevard street edge gets storefront/wall fragments.
                    if band == 1 then
                        local frontage_cross = side * (road_half + 130)
                        local fx, fz = to_world(scan, along, frontage_cross)
                        local facade = t.store_window or t.store_neon or t.window or t.entry or t.wall
                        if facade ~= nil then
                            spawn_piece(facade, fx, scan.ground_y, fz, side > 0 and 180 or 0, 100, false, true)
                        end
                        if t.lamp ~= nil and slot % 2 == 0 then
                            local lx, lz = to_world(scan, along + 250, frontage_cross - side * 120)
                            spawn_piece(t.lamp, lx, scan.ground_y, lz, 0, 100, false, false)
                        end
                        if t.planter ~= nil and slot % 3 == 1 then
                            local px, pz = to_world(scan, along - 230, frontage_cross - side * 110)
                            spawn_piece(t.planter, px, scan.ground_y, pz, random_range(0, 360), 100, false, false)
                        end
                    end
                end
            end
        end
    end

    -- Perimeter towers form an urban wall in front of the valley slopes.
    for side = -1, 1, 2 do
        local cross = side * 3850
        for slot = -6, 6 do
            if #spawned >= MAX_CLONES - 14 then break end
            if slot % 2 == 0 then
                local x, z = to_world(scan, slot * 820, cross)
                build_tower(scan, x, z, 5)
            end
        end
    end
end

local function generate()
    status = "scanning"
    local scan = scan_level()
    if scan == nil then return false end

    status = "building"
    build_dense_grid(scan)

    if #spawned > 0 then
        generated = true
        status = "ready"
        if g_UserGlobal ~= nil then
            g_UserGlobal["BLACK_SIGNAL_CITY_V2_READY"] = 1
            g_UserGlobal["BLACK_SIGNAL_CITY_V2_CLONES"] = #spawned
            g_UserGlobal["BLACK_SIGNAL_CITY_V2_ROADS"] = stats.roads
            g_UserGlobal["BLACK_SIGNAL_CITY_V2_TEMPLATES"] = stats.templates
            g_UserGlobal["BLACK_SIGNAL_CITY_V2_BLOCKS"] = stats.blocks
        end
        return true
    end

    status = "spawn produced zero clones"
    return false
end

function bs_city_v2.init()
    generated = false
    init_time = g_Time or 0
    spawned = {}
    rng_state = 12074317
    status = "waiting"
    last_error = ""
    stats = { roads = 0, templates = 0, blocks = 0, clones = 0 }
end

function bs_city_v2.main()
    if generated then return true end
    if (g_EntityElementMax or 0) <= 0 then
        status = "waiting for entities"
        return false
    end
    if (g_Time or 0) < init_time + 500 then return false end

    local ok, result = pcall(generate)
    if not ok then
        last_error = tostring(result)
        status = "ERROR: " .. last_error
        return false
    end
    return result == true
end

function bs_city_v2.get_status()
    return status, #spawned, stats.roads, stats.templates, stats.blocks, last_error
end

function bs_city_v2.quit()
    if DeleteNewEntity ~= nil then
        for i = #spawned, 1, -1 do pcall(DeleteNewEntity, spawned[i]) end
    end
    spawned = {}
    generated = false
end

function bs_city_v2_init(e)
    bs_city_v2.init()
end

function bs_city_v2_main(e)
    bs_city_v2.main()
end

return bs_city_v2
