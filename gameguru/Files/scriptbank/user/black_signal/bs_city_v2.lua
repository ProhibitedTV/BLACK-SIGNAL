-- DESCRIPTION: BLACK SIGNAL collision-aware District 12 city generator. Uses authored roads as the plan, real entity footprints for placement, and incrementally builds coherent blocks without occupying roads or overlapping buildings.

local bs_city_v2 = {}

local MAX_CLONES = 720
local SPAWNS_PER_FRAME = 3
local START_DELAY_MS = 500

local FRONT_OFFSET = 760
local BACK_OFFSET = 1580
local DEEP_OFFSET = 2450
local CURB_OFFSET = 470
local INTERSECTION_CORNER_OFFSET = 1120
local PLAYER_CLEARANCE = 900
local MAX_TERRAIN_DELTA = 120
local MAX_TERRAIN_SPREAD = 85
local SITE_CELL = 540

local ROAD_FOOTPRINT_MARGIN = 160
local BUILDING_FOOTPRINT_MARGIN = 110
local EXISTING_FOOTPRINT_MARGIN = 140
local PROP_ROAD_MARGIN = 30

local generated = false
local init_time = 0
local spawned = {}
local jobs = {}
local job_index = 1
local status = "idle"
local last_error = ""
local stats = {
    roads = 0,
    templates = 0,
    blocks = 0,
    clones = 0,
    planned = 0,
    failed = 0,
    alleys = 0,
    rejected_road = 0,
    rejected_overlap = 0,
    rejected_terrain = 0
}

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
        if ok and minx ~= nil and maxx ~= nil and minz ~= nil and maxz ~= nil then
            return minx, miny or 0, minz, maxx, maxy or 400, maxz
        end
    end
    return -200, 0, -200, 200, 400, 200
end

local function scales(e)
    if GetEntityScales ~= nil then
        local ok, sx, sy, sz = pcall(GetEntityScales, e)
        if ok and sx ~= nil then
            return sx or 1, sy or 1, sz or 1
        end
    end
    return 1, 1, 1
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

local function rotate_local(x, z, yaw)
    local r = math.rad(yaw or 0)
    local c = math.cos(r)
    local s = math.sin(r)
    return (x * c) + (z * s), (-x * s) + (z * c)
end

local function make_obb(cx, cz, hx, hz, yaw, tag)
    local r = math.rad(yaw or 0)
    local c = math.cos(r)
    local s = math.sin(r)
    return {
        cx = cx,
        cz = cz,
        hx = math.max(1, hx or 1),
        hz = math.max(1, hz or 1),
        ux = c,
        uz = -s,
        vx = s,
        vz = c,
        yaw = yaw or 0,
        tag = tag or ""
    }
end

local function footprint_from_entity(e, tag)
    local x, _, z, _, yaw, _ = pos_ang(e)
    local minx, _, minz, maxx, _, maxz = bounds(e)
    local sx, _, sz = scales(e)

    local local_cx = ((minx + maxx) * 0.5) * sx
    local local_cz = ((minz + maxz) * 0.5) * sz
    local world_off_x, world_off_z = rotate_local(local_cx, local_cz, yaw)

    return make_obb(
        x + world_off_x,
        z + world_off_z,
        math.abs(maxx - minx) * 0.5 * math.abs(sx),
        math.abs(maxz - minz) * 0.5 * math.abs(sz),
        yaw,
        tag
    )
end

local function footprint_from_template(template, x, z, yaw, scale_percent, tag)
    local minx, _, minz, maxx, _, maxz = bounds(template)
    local factor = (scale_percent or 100) / 100.0
    local local_cx = ((minx + maxx) * 0.5) * factor
    local local_cz = ((minz + maxz) * 0.5) * factor
    local world_off_x, world_off_z = rotate_local(local_cx, local_cz, yaw)

    return make_obb(
        x + world_off_x,
        z + world_off_z,
        math.abs(maxx - minx) * 0.5 * factor,
        math.abs(maxz - minz) * 0.5 * factor,
        yaw,
        tag
    )
end

local function projected_radius(box, ax, az, margin)
    local m = margin or 0
    local on_u = math.abs((ax * box.ux) + (az * box.uz))
    local on_v = math.abs((ax * box.vx) + (az * box.vz))
    return (box.hx * on_u) + (box.hz * on_v) + m
end

local function separated_on_axis(a, b, ax, az, margin_a, margin_b)
    local dx = b.cx - a.cx
    local dz = b.cz - a.cz
    local distance = math.abs((dx * ax) + (dz * az))
    local ra = projected_radius(a, ax, az, margin_a)
    local rb = projected_radius(b, ax, az, margin_b)
    return distance > (ra + rb)
end

local function obb_overlaps(a, b, margin_a, margin_b)
    if separated_on_axis(a, b, a.ux, a.uz, margin_a, margin_b) then return false end
    if separated_on_axis(a, b, a.vx, a.vz, margin_a, margin_b) then return false end
    if separated_on_axis(a, b, b.ux, b.uz, margin_a, margin_b) then return false end
    if separated_on_axis(a, b, b.vx, b.vz, margin_a, margin_b) then return false end
    return true
end

local function obb_corners(box)
    return {
        { x = box.cx + box.ux * box.hx + box.vx * box.hz, z = box.cz + box.uz * box.hx + box.vz * box.hz },
        { x = box.cx + box.ux * box.hx - box.vx * box.hz, z = box.cz + box.uz * box.hx - box.vz * box.hz },
        { x = box.cx - box.ux * box.hx + box.vx * box.hz, z = box.cz - box.uz * box.hx + box.vz * box.hz },
        { x = box.cx - box.ux * box.hx - box.vx * box.hz, z = box.cz - box.uz * box.hx - box.vz * box.hz }
    }
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
                        e = e,
                        x = x, y = y, z = z,
                        yaw = ay or 0,
                        kind = road_kind(path),
                        path = path,
                        footprint = footprint_from_entity(e, "road")
                    }
                elseif is_existing_architecture(path) then
                    architecture[#architecture + 1] = {
                        e = e, x = x, y = y, z = z,
                        yaw = ay or 0,
                        path = path,
                        footprint = footprint_from_entity(e, "existing")
                    }
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

local function largest_kit_footprint(kit, x, z, yaw, scale)
    local best = nil
    local best_area = -1

    local function consider(template)
        if template == nil or template <= 0 then return end
        local fp = footprint_from_template(template, x, z, yaw, scale, "generated")
        local area = fp.hx * fp.hz
        if area > best_area then
            best = fp
            best_area = area
        end
    end

    consider(kit.base)
    consider(kit.floor)
    consider(kit.between)
    consider(kit.top)
    return best
end

local function footprint_terrain_ok(box, road_y)
    local samples = { { x = box.cx, z = box.cz } }
    local corners = obb_corners(box)
    for i = 1, #corners do samples[#samples + 1] = corners[i] end

    local min_h = nil
    local max_h = nil
    local center_h = terrain_height(box.cx, box.cz, road_y)

    for i = 1, #samples do
        local h = terrain_height(samples[i].x, samples[i].z, center_h)
        if min_h == nil or h < min_h then min_h = h end
        if max_h == nil or h > max_h then max_h = h end
    end

    if math.abs(center_h - road_y) > MAX_TERRAIN_DELTA then
        return false, center_h
    end
    if min_h ~= nil and max_h ~= nil and (max_h - min_h) > MAX_TERRAIN_SPREAD then
        return false, center_h
    end
    return true, center_h
end

local function candidate_plan(scan, x, z, road_y, yaw, tier, depth, hash, source_kind)
    local kit = choose_kit(scan.templates, hash)
    if kit.floor == nil then return nil end

    local scale = 96 + (hash % 10)
    if depth >= 2 then scale = 100 + (hash % 11) end
    local floors = 2 + tier + (hash % 2)
    local footprint = largest_kit_footprint(kit, x, z, yaw, scale)
    if footprint == nil then return nil end

    return {
        x = x, z = z, road_y = road_y, yaw = yaw,
        tier = tier, depth = depth, hash = hash,
        source_kind = source_kind,
        kit = kit, scale = scale, floors = floors,
        footprint = footprint
    }
end

local function site_clear(scan, plan, site_claims, occupied)
    local key = site_key(plan.x, plan.z)
    if site_claims[key] then
        stats.rejected_overlap = stats.rejected_overlap + 1
        return false, key
    end

    if g_PlayerPosX ~= nil and g_PlayerPosZ ~= nil then
        local radius = math.sqrt((plan.footprint.hx * plan.footprint.hx) + (plan.footprint.hz * plan.footprint.hz))
        local clearance = PLAYER_CLEARANCE + radius
        if distance_sq(plan.footprint.cx, plan.footprint.cz, g_PlayerPosX, g_PlayerPosZ) < (clearance * clearance) then
            stats.rejected_overlap = stats.rejected_overlap + 1
            return false, key
        end
    end

    for i = 1, #scan.roads do
        if obb_overlaps(plan.footprint, scan.roads[i].footprint, BUILDING_FOOTPRINT_MARGIN, ROAD_FOOTPRINT_MARGIN) then
            stats.rejected_road = stats.rejected_road + 1
            return false, key
        end
    end

    for i = 1, #occupied do
        if obb_overlaps(plan.footprint, occupied[i], BUILDING_FOOTPRINT_MARGIN, EXISTING_FOOTPRINT_MARGIN) then
            stats.rejected_overlap = stats.rejected_overlap + 1
            return false, key
        end
    end

    local terrain_ok, ground_y = footprint_terrain_ok(plan.footprint, plan.road_y)
    if not terrain_ok then
        stats.rejected_terrain = stats.rejected_terrain + 1
        return false, key
    end

    plan.y = ground_y
    return true, key
end

local function claim_site(scan, sites, site_claims, occupied, x, z, road_y, yaw, tier, depth, hash, source_kind, push_x, push_z)
    local step_x = push_x or 0
    local step_z = push_z or 0

    for attempt = 0, 3 do
        local candidate_x = x + (step_x * attempt * 180)
        local candidate_z = z + (step_z * attempt * 180)
        local plan = candidate_plan(scan, candidate_x, candidate_z, road_y, yaw, tier, depth, hash, source_kind)
        if plan ~= nil then
            local ok, key = site_clear(scan, plan, site_claims, occupied)
            if ok then
                site_claims[key] = true
                occupied[#occupied + 1] = plan.footprint
                sites[#sites + 1] = plan
                return true
            end
        end
    end

    return false
end

local function collect_sites(scan)
    local front = {}
    local back = {}
    local deep = {}
    local corners = {}
    local site_claims = {}
    local occupied = {}

    for i = 1, #scan.architecture do
        occupied[#occupied + 1] = scan.architecture[i].footprint
    end

    for i = 1, #scan.roads do
        local road = scan.roads[i]
        local fx, fz, rx, rz = road_vectors(road.yaw)

        if road.kind == "straight" then
            for side = -1, 1, 2 do
                local h = site_hash(road.x, road.z, side + 7)
                local facing = road.yaw + (side > 0 and -90 or 90)
                local alley = (h % 8) == 0

                local front_x = road.x + (rx * side * FRONT_OFFSET)
                local front_z = road.z + (rz * side * FRONT_OFFSET)
                if alley then
                    stats.alleys = stats.alleys + 1
                else
                    claim_site(scan, front, site_claims, occupied, front_x, front_z, road.y, facing, 2 + (h % 2), 1, h, "front", rx * side, rz * side)
                end

                local along_jitter = ((h % 3) - 1) * 140
                local back_x = road.x + (rx * side * BACK_OFFSET) + (fx * along_jitter)
                local back_z = road.z + (rz * side * BACK_OFFSET) + (fz * along_jitter)
                claim_site(scan, back, site_claims, occupied, back_x, back_z, road.y, facing, 3 + (h % 3), 2, h + 101, "back", rx * side, rz * side)

                if (h % 4) == 0 then
                    local deep_x = road.x + (rx * side * DEEP_OFFSET) - (fx * 220)
                    local deep_z = road.z + (rz * side * DEEP_OFFSET) - (fz * 220)
                    claim_site(scan, deep, site_claims, occupied, deep_x, deep_z, road.y, facing, 5 + (h % 2), 3, h + 202, "deep", rx * side, rz * side)
                end
            end
        else
            for side = -1, 1, 2 do
                for along = -1, 1, 2 do
                    local h = site_hash(road.x + side * 31, road.z + along * 37, 19)
                    local x = road.x + (rx * side * INTERSECTION_CORNER_OFFSET) + (fx * along * INTERSECTION_CORNER_OFFSET)
                    local z = road.z + (rz * side * INTERSECTION_CORNER_OFFSET) + (fz * along * INTERSECTION_CORNER_OFFSET)
                    local facing = road.yaw + (side > 0 and -90 or 90)
                    local push_x = (rx * side) + (fx * along)
                    local push_z = (rz * side) + (fz * along)
                    local length = math.sqrt((push_x * push_x) + (push_z * push_z))
                    if length > 0 then
                        push_x = push_x / length
                        push_z = push_z / length
                    end
                    claim_site(scan, corners, site_claims, occupied, x, z, road.y, facing, 4 + (h % 2), 2, h, "corner", push_x, push_z)
                end
            end
        end
    end

    return front, corners, back, deep
end

local function plan_building(site)
    if #jobs >= MAX_CLONES - 12 then return end
    local kit = site.kit
    if kit == nil or kit.floor == nil then return end

    local next_y = site.y
    next_y = queue_piece(kit.base or kit.floor, site.x, next_y, site.z, site.yaw, site.scale, false, site.depth <= 2)

    if kit.between ~= nil and (site.hash % 5) == 0 then
        next_y = queue_piece(kit.between, site.x, next_y, site.z, site.yaw, site.scale, false, site.depth <= 2)
    end

    for _ = 1, site.floors do
        if #jobs >= MAX_CLONES - 2 then break end
        next_y = queue_piece(kit.floor, site.x, next_y, site.z, site.yaw, site.scale, false, site.depth <= 2)
    end

    queue_piece(kit.top or kit.floor, site.x, next_y, site.z, site.yaw, site.scale, false, site.depth <= 2)
    stats.blocks = stats.blocks + 1
end

local function prop_clear_of_roads(scan, template, x, z, yaw, scale)
    local fp = footprint_from_template(template, x, z, yaw, scale, "prop")
    for i = 1, #scan.roads do
        if obb_overlaps(fp, scan.roads[i].footprint, 0, PROP_ROAD_MARGIN) then
            return false
        end
    end
    return true
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
                        local template = nil
                        if (h % 3) == 0 then template = t.lamp
                        elseif (h % 5) == 0 then template = t.planter
                        elseif (h % 11) == 0 then template = t.trash
                        end

                        if template ~= nil and prop_clear_of_roads(scan, template, px, pz, road.yaw, 100) then
                            queue_piece(template, px, gy, pz, road.yaw, 100, false, false)
                        end
                    end
                end
            end
        end
    end
end

local function plan_generation()
    status = "scanning road footprints"
    local scan = scan_level()
    if scan == nil then return false end

    status = "solving collision-safe blocks"
    local front, corners, back, deep = collect_sites(scan)

    for i = 1, #front do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(front[i])
    end
    for i = 1, #corners do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(corners[i])
    end
    for i = 1, #back do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(back[i])
    end
    for i = 1, #deep do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(deep[i])
    end

    plan_road_props(scan)

    stats.planned = #jobs
    if #jobs == 0 then
        status = "collision solver produced zero jobs"
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
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_REJECTED_ROAD"] = stats.rejected_road
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_REJECTED_OVERLAP"] = stats.rejected_overlap
        g_UserGlobal["BLACK_SIGNAL_CITY_V2_REJECTED_TERRAIN"] = stats.rejected_terrain
    end
end

function bs_city_v2.init()
    generated = false
    init_time = g_Time or 0
    spawned = {}
    jobs = {}
    job_index = 1
    status = "waiting"
    last_error = ""
    stats = {
        roads = 0,
        templates = 0,
        blocks = 0,
        clones = 0,
        planned = 0,
        failed = 0,
        alleys = 0,
        rejected_road = 0,
        rejected_overlap = 0,
        rejected_terrain = 0
    }
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
    local diagnostics =
        "reject road " .. tostring(stats.rejected_road) ..
        " overlap " .. tostring(stats.rejected_overlap) ..
        " terrain " .. tostring(stats.rejected_terrain)
    if last_error ~= "" then diagnostics = last_error end
    return status, #spawned, stats.roads, stats.templates, stats.blocks, diagnostics
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
