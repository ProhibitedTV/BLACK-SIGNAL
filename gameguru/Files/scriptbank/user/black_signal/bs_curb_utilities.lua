-- DESCRIPTION: BLACK SIGNAL curb-utility pass. Uses exact Cyberpunk Streets sidewalk assets discovered by the pack audit to create coherent curb guards, plastic dividers, sidewalk lighting, planters and sparse utility poles after DETAIL V1.

local bs_curb_utilities = {}

local MAX_DETAILS = 220
local SPAWNS_PER_FRAME = 5
local START_DELAY_MS = 150
local ROAD_MARGIN = 10
local BUILDING_MARGIN = 24
local DETAIL_MARGIN = 10
local MAX_TERRAIN_DELTA = 60

local generated = false
local init_time = 0
local jobs = {}
local spawned = {}
local occupied = {}
local job_index = 1
local status = "idle"
local last_error = ""
local stats = {}

local function reset_stats()
    stats = {
        sidewalks = 0, roads = 0, templates = 0, clones = 0,
        guards = 0, dividers = 0, lights = 0, planters = 0, poles = 0,
        rejected_road = 0, rejected_overlap = 0, rejected_terrain = 0
    }
end

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
        if ok and x ~= nil then return x or 0, y or 0, z or 0, ax or 0, ay or 0, az or 0 end
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
            return minx, miny or 0, minz, maxx, maxy or 200, maxz
        end
    end
    return -50, 0, -50, 50, 100, 50
end

local function scales(e)
    if GetEntityScales ~= nil then
        local ok, sx, sy, sz = pcall(GetEntityScales, e)
        if ok and sx ~= nil then return sx or 1, sy or 1, sz or 1 end
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

local function site_hash(x, z, salt)
    local xi = math.floor(x / 50)
    local zi = math.floor(z / 50)
    local v = (xi * 73856093) + (zi * 19349663) + ((salt or 0) * 83492791)
    if v < 0 then v = -v end
    return v
end

local function rotate_local(x, z, yaw)
    local r = math.rad(yaw or 0)
    local c = math.cos(r)
    local s = math.sin(r)
    return (x * c) + (z * s), (-x * s) + (z * c)
end

local function make_obb(cx, cz, hx, hz, yaw)
    local r = math.rad(yaw or 0)
    return {
        cx = cx, cz = cz,
        hx = math.max(1, hx or 1), hz = math.max(1, hz or 1),
        ux = math.cos(r), uz = -math.sin(r),
        vx = math.sin(r), vz = math.cos(r),
        yaw = yaw or 0
    }
end

local function footprint_from_entity(e)
    local x, _, z, _, yaw, _ = pos_ang(e)
    local minx, _, minz, maxx, _, maxz = bounds(e)
    local sx, _, sz = scales(e)
    local local_cx = ((minx + maxx) * 0.5) * sx
    local local_cz = ((minz + maxz) * 0.5) * sz
    local ox, oz = rotate_local(local_cx, local_cz, yaw)
    return make_obb(
        x + ox, z + oz,
        math.abs(maxx - minx) * 0.5 * math.abs(sx),
        math.abs(maxz - minz) * 0.5 * math.abs(sz),
        yaw
    )
end

local function footprint_from_template(template, x, z, yaw, scale_percent)
    local minx, _, minz, maxx, _, maxz = bounds(template)
    local f = (scale_percent or 100) / 100.0
    local local_cx = ((minx + maxx) * 0.5) * f
    local local_cz = ((minz + maxz) * 0.5) * f
    local ox, oz = rotate_local(local_cx, local_cz, yaw)
    return make_obb(
        x + ox, z + oz,
        math.abs(maxx - minx) * 0.5 * f,
        math.abs(maxz - minz) * 0.5 * f,
        yaw
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
    local d = math.abs((dx * ax) + (dz * az))
    return d > (projected_radius(a, ax, az, margin_a) + projected_radius(b, ax, az, margin_b))
end

local function obb_overlaps(a, b, margin_a, margin_b)
    if separated_on_axis(a, b, a.ux, a.uz, margin_a, margin_b) then return false end
    if separated_on_axis(a, b, a.vx, a.vz, margin_a, margin_b) then return false end
    if separated_on_axis(a, b, b.ux, b.uz, margin_a, margin_b) then return false end
    if separated_on_axis(a, b, b.vx, b.vz, margin_a, margin_b) then return false end
    return true
end

local function axis_geometry(box)
    if box.hx >= box.hz then
        return box.ux, box.uz, box.vx, box.vz, box.hx, box.hz, box.yaw
    end
    return box.vx, box.vz, box.ux, box.uz, box.hz, box.hx, box.yaw + 90
end

local function distance_sq(ax, az, bx, bz)
    local dx = ax - bx
    local dz = az - bz
    return dx * dx + dz * dz
end

local function is_pack(path)
    return contains(path, "cyberpunk streets booster pack")
end

local function is_road(path)
    return is_pack(path) and contains(path, "streets and sidewalks\\streets\\")
end

local function is_sidewalk(path)
    return is_pack(path) and contains(path, "streets and sidewalks\\sidewalks\\")
end

local function is_building(path)
    if not is_pack(path) then return false end
    if is_road(path) or is_sidewalk(path) then return false end
    return contains(path, "background buildings") or contains(path, "\\buildings\\") or contains(path, "store fronts")
end

local function capture_template(t, path, e)
    if not is_pack(path) then return end
    if contains(path, "cs_plastic_divider_1.fpe") then t.divider = t.divider or e end
    if contains(path, "cs_sidewalk_guard.fpe") then t.guard = t.guard or e end
    if contains(path, "cs_sidewalk_light.fpe") then t.sidewalk_light = t.sidewalk_light or e end
    if contains(path, "cs_sidewalk_planter.fpe") then t.sidewalk_planter = t.sidewalk_planter or e end
    if contains(path, "cs_street_electrical_pole_01.fpe") then t.utility_pole = t.utility_pole or e end
end

local function scan_level()
    local t = {}
    local roads = {}
    local sidewalks = {}
    local buildings = {}
    local maxe = g_EntityElementMax or 0

    for e = 1, maxe do
        local path = entity_path(e)
        if path ~= "" then
            if original_entity(e) then
                capture_template(t, path, e)
                if is_road(path) then
                    roads[#roads + 1] = { footprint = footprint_from_entity(e) }
                elseif is_sidewalk(path) then
                    sidewalks[#sidewalks + 1] = { footprint = footprint_from_entity(e) }
                end
            end
            if is_building(path) then
                buildings[#buildings + 1] = { footprint = footprint_from_entity(e) }
            end
        end
    end

    local template_count = 0
    for _, value in pairs(t) do if value ~= nil then template_count = template_count + 1 end end
    stats.templates = template_count
    stats.roads = #roads
    stats.sidewalks = #sidewalks

    if #roads == 0 or #sidewalks == 0 then
        status = "skipped: no authored road/sidewalk geometry"
        generated = true
        return nil, true
    end
    if template_count == 0 then
        status = "skipped: curb utility exemplars not seeded"
        generated = true
        return nil, true
    end

    return { templates = t, roads = roads, sidewalks = sidewalks, buildings = buildings }, false
end

local function nearest_road(scan, x, z)
    local best = nil
    local best_d = nil
    for i = 1, #scan.roads do
        local r = scan.roads[i]
        local d = distance_sq(x, z, r.footprint.cx, r.footprint.cz)
        if best_d == nil or d < best_d then best = r; best_d = d end
    end
    return best
end

local function prop_clear(scan, template, x, z, yaw, scale)
    local fp = footprint_from_template(template, x, z, yaw, scale or 100)
    for i = 1, #scan.roads do
        if obb_overlaps(fp, scan.roads[i].footprint, DETAIL_MARGIN, ROAD_MARGIN) then
            stats.rejected_road = stats.rejected_road + 1
            return false, fp
        end
    end
    for i = 1, #scan.buildings do
        if obb_overlaps(fp, scan.buildings[i].footprint, DETAIL_MARGIN, BUILDING_MARGIN) then
            stats.rejected_overlap = stats.rejected_overlap + 1
            return false, fp
        end
    end
    for i = 1, #occupied do
        if obb_overlaps(fp, occupied[i], DETAIL_MARGIN, DETAIL_MARGIN) then
            stats.rejected_overlap = stats.rejected_overlap + 1
            return false, fp
        end
    end
    return true, fp
end

local function queue_detail(scan, template, x, z, yaw, kind, fallback_y)
    if template == nil or #jobs >= MAX_DETAILS then return false end
    local ground_y = terrain_height(x, z, fallback_y or 0)
    if fallback_y ~= nil and math.abs(ground_y - fallback_y) > MAX_TERRAIN_DELTA then
        stats.rejected_terrain = stats.rejected_terrain + 1
        return false
    end

    local clear, fp = prop_clear(scan, template, x, z, yaw, 100)
    if not clear then return false end

    occupied[#occupied + 1] = fp
    jobs[#jobs + 1] = { template = template, x = x, bottom_y = ground_y, z = z, yaw = yaw or 0, scale = 100 }

    if kind == "guard" then stats.guards = stats.guards + 1
    elseif kind == "divider" then stats.dividers = stats.dividers + 1
    elseif kind == "light" then stats.lights = stats.lights + 1
    elseif kind == "planter" then stats.planters = stats.planters + 1
    elseif kind == "pole" then stats.poles = stats.poles + 1 end
    return true
end

local function place_curb_utilities(scan)
    local t = scan.templates

    for i = 1, #scan.sidewalks do
        if #jobs >= MAX_DETAILS - 8 then return end
        local fp = scan.sidewalks[i].footprint
        local along_x, along_z, normal_x, normal_z, half_len, half_cross, yaw = axis_geometry(fp)
        if half_len > 110 and half_cross > 24 then
            local road = nearest_road(scan, fp.cx, fp.cz)
            if road ~= nil then
                local tx = road.footprint.cx - fp.cx
                local tz = road.footprint.cz - fp.cz
                local dot = (tx * normal_x) + (tz * normal_z)
                local curb_sign = (dot >= 0) and 1 or -1
                local curb_nx = normal_x * curb_sign
                local curb_nz = normal_z * curb_sign
                local outer_nx = -curb_nx
                local outer_nz = -curb_nz
                local curb_offset = math.max(18, half_cross * 0.62)
                local outer_offset = math.max(28, half_cross * 0.40)

                local anchors = { 0 }
                if half_len > 360 then
                    local spread = math.min(half_len * 0.43, 390)
                    anchors = { -spread, 0, spread }
                end

                for a = 1, #anchors do
                    if #jobs >= MAX_DETAILS - 6 then return end
                    local along = anchors[a]
                    local ax = fp.cx + along_x * along
                    local az = fp.cz + along_z * along
                    local h = site_hash(ax, az, i * 41 + a)
                    local curb_x = ax + curb_nx * curb_offset
                    local curb_z = az + curb_nz * curb_offset
                    local outer_x = ax + outer_nx * outer_offset
                    local outer_z = az + outer_nz * outer_offset

                    -- Exact curb-protection assets discovered by the installed-pack scan.
                    if t.guard ~= nil and (h % 4) == 0 then
                        queue_detail(scan, t.guard, curb_x, curb_z, yaw, "guard", nil)
                    elseif t.divider ~= nil and (h % 3) == 0 then
                        queue_detail(scan, t.divider, curb_x, curb_z, yaw, "divider", nil)
                    end

                    -- Outer sidewalk zone: readable lighting/greenery instead of random scatter.
                    if t.sidewalk_light ~= nil and (h % 4) == 1 then
                        queue_detail(scan, t.sidewalk_light, outer_x, outer_z, yaw, "light", nil)
                    elseif t.sidewalk_planter ~= nil and (h % 5) == 2 then
                        queue_detail(scan, t.sidewalk_planter, outer_x, outer_z, yaw, "planter", nil)
                    end

                    -- Pole wire meshes remain deferred until their length/origin are visually verified.
                    if t.utility_pole ~= nil and half_len > 420 and (h % 23) == 0 then
                        local pole_x = ax + outer_nx * math.max(45, half_cross * 0.72)
                        local pole_z = az + outer_nz * math.max(45, half_cross * 0.72)
                        queue_detail(scan, t.utility_pole, pole_x, pole_z, yaw, "pole", nil)
                    end
                end
            end
        end
    end
end

local function plan_generation()
    status = "scanning curb utility kit"
    local scan, skipped = scan_level()
    if skipped then return true end
    if scan == nil then return false end

    status = "planning curb utilities"
    place_curb_utilities(scan)
    if #jobs == 0 then
        status = "skipped: no valid curb utility sites"
        generated = true
        return true
    end

    status = "building curb utilities 0/" .. tostring(#jobs)
    return true
end

local function spawn_job(job)
    if SpawnNewEntity == nil then last_error = "SpawnNewEntity unavailable"; return false end
    local ok, newe = pcall(SpawnNewEntity, job.template)
    if not ok or newe == nil or newe <= 0 then
        last_error = "SpawnNewEntity failed at curb job " .. tostring(job_index)
        return false
    end

    local _, miny = bounds(job.template)
    local pivot_y = job.bottom_y - (miny * (job.scale / 100.0))
    if ResetPosition ~= nil then pcall(ResetPosition, newe, job.x, pivot_y, job.z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, job.yaw, 0) end
    if Scale ~= nil then pcall(Scale, newe, job.scale) end
    if GravityOff ~= nil then pcall(GravityOff, newe) end
    if CollisionOff ~= nil then pcall(CollisionOff, newe) end
    if Show ~= nil then pcall(Show, newe) end

    spawned[#spawned + 1] = newe
    stats.clones = #spawned
    return true
end

local function publish_ready()
    generated = true
    status = "ready"
    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_CURB_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_CURB_CLONES"] = stats.clones
        g_UserGlobal["BLACK_SIGNAL_CURB_GUARDS"] = stats.guards
        g_UserGlobal["BLACK_SIGNAL_CURB_DIVIDERS"] = stats.dividers
        g_UserGlobal["BLACK_SIGNAL_CURB_POLES"] = stats.poles
    end
end

function bs_curb_utilities.init()
    generated = false
    init_time = g_Time or 0
    jobs = {}
    spawned = {}
    occupied = {}
    job_index = 1
    status = "waiting"
    last_error = ""
    reset_stats()
end

function bs_curb_utilities.main()
    if generated then return true end
    if (g_EntityElementMax or 0) <= 0 then status = "waiting for entities"; return false end
    if (g_Time or 0) < init_time + START_DELAY_MS then return false end

    if #jobs == 0 then
        local ok, planned = pcall(plan_generation)
        if not ok then last_error = tostring(planned); status = "ERROR planning: " .. last_error; return false end
        if not planned then return false end
        if generated then return true end
    end

    local processed = 0
    while job_index <= #jobs and processed < SPAWNS_PER_FRAME do
        local ok, err = pcall(spawn_job, jobs[job_index])
        if not ok then last_error = tostring(err); status = "ERROR spawn: " .. last_error; return false end
        job_index = job_index + 1
        processed = processed + 1
    end

    if job_index > #jobs then publish_ready(); return true end
    status = "building curb utilities " .. tostring(job_index - 1) .. "/" .. tostring(#jobs)
    return false
end

function bs_curb_utilities.get_status()
    return status, stats.clones, stats.roads, stats.sidewalks, stats.templates,
        stats.guards, stats.dividers, stats.lights, stats.planters, stats.poles,
        stats.rejected_road, stats.rejected_overlap, stats.rejected_terrain, last_error
end

function bs_curb_utilities.quit()
    jobs = {}
    spawned = {}
    occupied = {}
    job_index = 1
    generated = false
end

function bs_curb_utilities_init(e)
    bs_curb_utilities.init()
end

function bs_curb_utilities_main(e)
    bs_curb_utilities.main()
end

return bs_curb_utilities
