-- DESCRIPTION: BLACK SIGNAL street-aware District 12 city generator. Uses the authored Cyberpunk Streets road network as the urban plan and incrementally builds coherent blocks, alleys and curb detail around it.

local bs_city_v2 = {}

local MAX_CLONES = 720
local SPAWNS_PER_FRAME = 3
local START_DELAY_MS = 500

local FRONT_OFFSET = 680
local BACK_OFFSET = 1380
local DEEP_OFFSET = 2050
local CURB_OFFSET = 430
local INTERSECTION_CORNER_OFFSET = 900
local ROAD_CLEARANCE = 430
local EXISTING_CLEARANCE = 560
local PLAYER_CLEARANCE = 850
local MAX_TERRAIN_DELTA = 110
local SITE_CELL = 620

local generated = false
local init_time = 0
local spawned = {}
local jobs = {}
local job_index = 1
local rng_state = 12074317
local status = "idle"
local last_error = ""
local stats = { roads = 0, templates = 0, blocks = 0, clones = 0, planned = 0, failed = 0, alleys = 0 }

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

local function terrain_height(x, z, fallback)
    if GetTerrainHeight ~= nil then
        local ok, value = pcall(GetTerrainHeight, x, z)
        if ok and value ~= nil then return value end
    end
    return fallback or 0
end

local function distance_sq(ax, az, bx, bz)
    local dx = ax - bx
    local dz = az - bz
    return dx * dx + dz * dz
end

local function is_known_road(path)
    return contains(path, "cs_street_straight_4x.fpe") or
           contains(path, "cs_street_t-intersect_3.fpe") or
           contains(path, "cs_street_4_way_2.fpe")
end

local function road_kind(path)
    if contains(path, "cs_street_4_way_2.fpe") then return "4way" end
    if contains(path, "cs_street_t-intersect_3.fpe") then return "t" end
    return "straight"
end

local function is_existing_architecture(path)
    if not contains(path, "cyberpunk streets booster pack") then return false end
    if is_known_road(path) then return false end
    return contains(path, "background buildings") or
           contains(path, "store fronts") or
           contains(path, "\\buildings\\")
end

local function site_hash(x, z, salt)
    local xi = math.floor(x / 100)
    local zi = math.floor(z / 100)
    local value = (xi * 73856093) + (zi * 19349663) + ((salt or 0) * 83492791)
    if value < 0 then value = -value end
    return value
end

local function site_key(x, z)
    local gx = math.floor((x / SITE_CELL) + 0.5)
    local gz = math.floor((z / SITE_CELL) + 0.5)
    return tostring(gx) .. ":" .. tostring(gz)
end

local function road_vectors(yaw)
    local r = math.rad(yaw or 0)
    local fx = math.sin(r)
    local fz = math.cos(r)
    local rx = math.cos(r)
    local rz = -math.sin(r)
    return fx, fz, rx, rz
end

local function scan_level()
    local t = {}
    local roads = {}
    local architecture = {}
    local maxe = g_EntityElementMax or 0

    for e = 1, maxe do
        if original_entity(e) then
            local path = entity_path(e)
            if path ~= "" then
                local x, y, z, _, ay, _ = pos_ang(e)

                if contains(path, "cs_bg_building_01_base2.fpe") then t.b1_base2 = t.b1_base2 or e end
                if contains(path, "cs_bg_building_01_base.fpe") then t.b1_base = t.b1_base or e end
                if contains(path, "cs_bg_building_01_floor_between.fpe") then t.b1_between = t.b1_between or e end
                if contains(path, "cs_bg_building_01_floor.fpe") then t.b1_floor = t.b1_floor or e end
                if contains(path, "cs_bg_building_01_top.fpe") then t.b1_top = t.b1_top or e end
                if contains(path, "cs_bg_building_03_base.fpe") then t.b3_base = t.b3_base or e end
                if contains(path, "cs_bg_building_03_floor.fpe") then t.b3_floor = t.b3_floor or e end
                if contains(path, "cs_bg_building_03_top.fpe") then t.b3_top = t.b3_top or e end

                if contains(path, "cs_street_lamp.fpe") then t.lamp = t.lamp or e end
                if contains(path, "cs_planter_01.fpe") then t.planter = t.planter or e end
                if contains(path, "cs_trash_can.fpe") then t.trash = t.trash or e end
                if contains(path, "cs_bottle_can_cluster_01.fpe") then t.bottles = t.bottles or e end
                if contains(path, "cs_newspaper_01.fpe") then t.paper1 = t.paper1 or e end
                if contains(path, "cs_newspaper_02.fpe") then t.paper2 = t.paper2 or e end

                if is_known_road(path) then
                    roads[#roads + 1] = {
                        x = x, y = y, z = z,
                        yaw = ay or 0,
                        kind = road_kind(path),
                        path = path
                    }
                elseif is_existing_architecture(path) then
                    architecture[#architecture + 1] = { x = x, y = y, z = z, e = e, path = path }
                end
            end
        end
    end

    table.sort(roads, function(a, b)
        if a.x == b.x then
            if a.z == b.z then return a.yaw < b.yaw end
            return a.z < b.z
        end
        return a.x < b.x
    end)

    stats.roads = #roads
    local template_count = 0
    for _, value in pairs(t) do if value ~= nil then template_count = template_count + 1 end end
    stats.templates = template_count

    if t.b1_floor == nil and t.b3_floor == nil then
        status = "no building floor templates"
        return nil
    end
    if #roads == 0 then
        status = "no authored road samples"
        return nil
    end

    return {
        templates = t,
        roads = roads,
        architecture = architecture
    }
end

local function choose_kit(t, hash)
    if (hash % 100) < 58 and t.b1_floor ~= nil then
        return {
            base = (((hash % 7) == 0) and t.b1_base2 or t.b1_base) or t.b1_floor,
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

local function top_after(template, bottom_y, scale)
    if template == nil or template <= 0 then return bottom_y end
    local _, miny, _, _, maxy, _ = bounds(template)
    local factor = (scale or 100) / 100.0
    local pivot_y = bottom_y - (miny * factor)
    return pivot_y + (maxy * factor)
end

local function queue_piece(template, x, bottom_y, z, yaw, scale, collision, shadow)
    if template == nil or template <= 0 then return bottom_y end
    if #jobs >= MAX_CLONES then return bottom_y end
    jobs[#jobs + 1] = {
        template = template,
        x = x,
        bottom_y = bottom_y,
        z = z,
        yaw = yaw or 0,
        scale = scale or 100,
        collision = collision == true,
        shadow = shadow ~= false
    }
    return top_after(template, bottom_y, scale)
end

local function site_clear(scan, x, z, road_y, site_claims)
    local key = site_key(x, z)
    if site_claims[key] then return false, 0, key end

    if g_PlayerPosX ~= nil and g_PlayerPosZ ~= nil then
        if distance_sq(x, z, g_PlayerPosX, g_PlayerPosZ) < (PLAYER_CLEARANCE * PLAYER_CLEARANCE) then
            return false, 0, key
        end
    end

    for i = 1, #scan.roads do
        local r = scan.roads[i]
        if distance_sq(x, z, r.x, r.z) < (ROAD_CLEARANCE * ROAD_CLEARANCE) then
            return false, 0, key
        end
    end

    for i = 1, #scan.architecture do
        local a = scan.architecture[i]
        if distance_sq(x, z, a.x, a.z) < (EXISTING_CLEARANCE * EXISTING_CLEARANCE) then
            return false, 0, key
        end
    end

    local gy = terrain_height(x, z, road_y)
    if math.abs(gy - road_y) > MAX_TERRAIN_DELTA then
        return false, gy, key
    end

    return true, gy, key
end

local function claim_site(scan, sites, site_claims, x, z, road_y, yaw, tier, depth, hash, source_kind)
    local ok, gy, key = site_clear(scan, x, z, road_y, site_claims)
    if not ok then return false end

    site_claims[key] = true
    sites[#sites + 1] = {
        x = x,
        z = z,
        y = gy,
        yaw = yaw,
        tier = tier,
        depth = depth,
        hash = hash,
        source_kind = source_kind
    }
    return true
end

local function collect_sites(scan)
    local front = {}
    local back = {}
    local deep = {}
    local corners = {}
    local site_claims = {}

    for i = 1, #scan.roads do
        local road = scan.roads[i]
        local fx, fz, rx, rz = road_vectors(road.yaw)

        if road.kind == "straight" then
            for side = -1, 1, 2 do
                local h = site_hash(road.x, road.z, side + 7)
                local facing = road.yaw + (side > 0 and -90 or 90)
                local alley = (h % 7) == 0

                local front_x = road.x + (rx * side * FRONT_OFFSET)
                local front_z = road.z + (rz * side * FRONT_OFFSET)
                if alley then
                    stats.alleys = stats.alleys + 1
                else
                    claim_site(scan, front, site_claims, front_x, front_z, road.y, facing, 2 + (h % 2), 1, h, "front")
                end

                -- The second row sits behind the street wall. When the frontage is
                -- intentionally omitted, this mass becomes the visual termination of
                -- a real alley/service corridor instead of a random gap.
                local along_jitter = ((h % 3) - 1) * 115
                local back_x = road.x + (rx * side * BACK_OFFSET) + (fx * along_jitter)
                local back_z = road.z + (rz * side * BACK_OFFSET) + (fz * along_jitter)
                claim_site(scan, back, site_claims, back_x, back_z, road.y, facing, 3 + (h % 3), 2, h + 101, "back")

                -- Sparse third-row towers fill the basin behind the block while still
                -- respecting terrain and the authored street network.
                if (h % 4) == 0 then
                    local deep_x = road.x + (rx * side * DEEP_OFFSET) - (fx * 180)
                    local deep_z = road.z + (rz * side * DEEP_OFFSET) - (fz * 180)
                    claim_site(scan, deep, site_claims, deep_x, deep_z, road.y, facing, 5 + (h % 2), 3, h + 202, "deep")
                end
            end
        else
            -- Intersections get four corner masses, deliberately pulled back from
            -- the carriageway. Adjacent intersection/straight samples collapse into
            -- the same spatial cells, preventing overlapping stacks.
            for side = -1, 1, 2 do
                for along = -1, 1, 2 do
                    local h = site_hash(road.x + side * 31, road.z + along * 37, 19)
                    local x = road.x + (rx * side * INTERSECTION_CORNER_OFFSET) + (fx * along * INTERSECTION_CORNER_OFFSET)
                    local z = road.z + (rz * side * INTERSECTION_CORNER_OFFSET) + (fz * along * INTERSECTION_CORNER_OFFSET)
                    local facing = road.yaw + (side > 0 and -90 or 90)
                    claim_site(scan, corners, site_claims, x, z, road.y, facing, 4 + (h % 2), 2, h, "corner")
                end
            end
        end
    end

    return front, corners, back, deep
end

local function plan_building(scan, site)
    if #jobs >= MAX_CLONES - 12 then return end
    local t = scan.templates
    local kit = choose_kit(t, site.hash)
    if kit.floor == nil then return end

    local scale = 96 + (site.hash % 10)
    if site.depth >= 2 then scale = 100 + (site.hash % 11) end
    local floors = 2 + site.tier + (site.hash % 2)
    local next_y = site.y

    next_y = queue_piece(kit.base or kit.floor, site.x, next_y, site.z, site.yaw, scale, false, site.depth <= 2)
    if kit.between ~= nil and (site.hash % 5) == 0 then
        next_y = queue_piece(kit.between, site.x, next_y, site.z, site.yaw, scale, false, site.depth <= 2)
    end

    for _ = 1, floors do
        if #jobs >= MAX_CLONES - 2 then break end
        next_y = queue_piece(kit.floor, site.x, next_y, site.z, site.yaw, scale, false, site.depth <= 2)
    end
    queue_piece(kit.top or kit.floor, site.x, next_y, site.z, site.yaw, scale, false, site.depth <= 2)
    stats.blocks = stats.blocks + 1
end

local function plan_road_props(scan)
    local t = scan.templates
    local prop_claims = {}

    for i = 1, #scan.roads do
        if #jobs >= MAX_CLONES - 4 then return end
        local road = scan.roads[i]
        if road.kind == "straight" then
            local fx, fz, rx, rz = road_vectors(road.yaw)
            local h = site_hash(road.x, road.z, 41)

            for side = -1, 1, 2 do
                local px = road.x + (rx * side * CURB_OFFSET) + (fx * (((h % 3) - 1) * 90))
                local pz = road.z + (rz * side * CURB_OFFSET) + (fz * (((h % 3) - 1) * 90))
                local key = site_key(px, pz)
                if not prop_claims[key] then
                    prop_claims[key] = true
                    local gy = terrain_height(px, pz, road.y)
                    if math.abs(gy - road.y) <= MAX_TERRAIN_DELTA then
                        if (h % 3) == 0 and t.lamp ~= nil then
                            queue_piece(t.lamp, px, gy, pz, road.yaw, 100, false, false)
                        elseif (h % 5) == 0 and t.planter ~= nil then
                            queue_piece(t.planter, px, gy, pz, road.yaw, 100, false, false)
                        elseif (h % 11) == 0 and t.trash ~= nil then
                            queue_piece(t.trash, px, gy, pz, road.yaw, 100, false, false)
                        end
                    end
                end
            end
        end
    end
end

local function plan_generation()
    status = "scanning roads"
    local scan = scan_level()
    if scan == nil then return false end

    status = "laying out blocks"
    local front, corners, back, deep = collect_sites(scan)

    -- Plan in urban-design order: street wall first, then intersection anchors,
    -- then interior/back-row mass, then sparse deeper towers and curb furniture.
    for i = 1, #front do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(scan, front[i])
    end
    for i = 1, #corners do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(scan, corners[i])
    end
    for i = 1, #back do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(scan, back[i])
    end
    for i = 1, #deep do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(scan, deep[i])
    end
    plan_road_props(scan)

    stats.planned = #jobs
    if #jobs == 0 then
        status = "layout produced zero jobs"
        return false
    end

    status = "building 0/" .. tostring(#jobs)
    return true
end

local function spawn_job(job)
    if job == nil then return false end
    if SpawnNewEntity == nil then
        last_error = "SpawnNewEntity unavailable"
        return false
    end

    local ok, newe = pcall(SpawnNewEntity, job.template)
    if not ok or newe == nil or newe <= 0 then
        stats.failed = stats.failed + 1
        last_error = "SpawnNewEntity failed at job " .. tostring(job_index)
        return false
    end

    local _, miny, _, _, _, _ = bounds(job.template)
    local factor = job.scale / 100.0
    local pivot_y = job.bottom_y - (miny * factor)

    if ResetPosition ~= nil then pcall(ResetPosition, newe, job.x, pivot_y, job.z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, job.yaw, 0) end
    if Scale ~= nil then pcall(Scale, newe, job.scale) end
    if GravityOff ~= nil then pcall(GravityOff, newe) end
    if job.collision then
        if CollisionOn ~= nil then pcall(CollisionOn, newe) end
    else
        if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    end
    if not job.shadow and SetEntityCastShadows ~= nil then pcall(SetEntityCastShadows, newe, 0) end
    if Show ~= nil then pcall(Show, newe) end

    spawned[#spawned + 1] = newe
    stats.clones = #spawned
    return true
end

local function publish_ready()
    generated = true
    status = "ready"
    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_CLONES"] = #spawned
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_ROADS"] = stats.roads
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_TEMPLATES"] = stats.templates
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_BLOCKS"] = stats.blocks
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_ALLEYS"] = stats.alleys
    end
end

function bs_city_v2.init()
    generated = false
    init_time = g_Time or 0
    spawned = {}
    jobs = {}
    job_index = 1
    rng_state = 12074317
    status = "waiting"
    last_error = ""
    stats = { roads = 0, templates = 0, blocks = 0, clones = 0, planned = 0, failed = 0, alleys = 0 }
end

function bs_city_v2.main()
    if generated then return true end
    if (g_EntityElementMax or 0) <= 0 then
        status = "waiting for entities"
        return false
    end
    if (g_Time or 0) < init_time + START_DELAY_MS then return false end

    if #jobs == 0 then
        local ok, planned = pcall(plan_generation)
        if not ok then
            last_error = tostring(planned)
            status = "ERROR planning: " .. last_error
            return false
        end
        if not planned then return false end
    end

    local processed = 0
    while job_index <= #jobs and processed < SPAWNS_PER_FRAME do
        local job = jobs[job_index]
        local ok, err = pcall(spawn_job, job)
        if not ok then
            last_error = tostring(err)
            status = "ERROR spawn: " .. last_error
            return false
        end
        job_index = job_index + 1
        processed = processed + 1
    end

    if job_index > #jobs then
        if #spawned > 0 then
            publish_ready()
            return true
        end
        status = "spawn produced zero clones"
        return false
    end

    status = "building " .. tostring(job_index - 1) .. "/" .. tostring(#jobs)
    return false
end

function bs_city_v2.get_status()
    return status, #spawned, stats.roads, stats.templates, stats.blocks, last_error
end

function bs_city_v2.quit()
    spawned = {}
    jobs = {}
    job_index = 1
    generated = false
end

function bs_city_v2_init(e)
    bs_city_v2.init()
end

function bs_city_v2_main(e)
    bs_city_v2.main()
end

return bs_city_v2
