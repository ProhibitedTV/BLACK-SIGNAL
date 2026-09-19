-- DESCRIPTION: BLACK SIGNAL street-detail pass. After CITY V3 builds the district, this pass dresses authored sidewalks and service edges with deterministic, collision-aware cyberpunk street furniture.

local bs_city_details = {}

local MAX_DETAILS = 360
local SPAWNS_PER_FRAME = 6
local START_DELAY_MS = 150
local ROAD_MARGIN = 12
local BUILDING_MARGIN = 18
local DETAIL_MARGIN = 14
local MAX_TERRAIN_DELTA = 70

local generated = false
local init_time = 0
local jobs = {}
local spawned = {}
local occupied = {}
local job_index = 1
local status = "idle"
local last_error = ""

local stats = {
    roads = 0,
    sidewalks = 0,
    templates = 0,
    clones = 0,
    rails = 0,
    posts = 0,
    benches = 0,
    stops = 0,
    lamps = 0,
    planters = 0,
    service = 0,
    clutter = 0,
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

local function make_obb(cx, cz, hx, hz, yaw, tag)
    local r = math.rad(yaw or 0)
    local c = math.cos(r)
    local s = math.sin(r)
    return {
        cx = cx, cz = cz,
        hx = math.max(1, hx or 1), hz = math.max(1, hz or 1),
        ux = c, uz = -s,
        vx = s, vz = c,
        yaw = yaw or 0, tag = tag or ""
    }
end

local function footprint_from_entity(e, tag)
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
        yaw, tag
    )
end

local function footprint_from_template(template, x, z, yaw, scale_percent, tag)
    local minx, _, minz, maxx, _, maxz = bounds(template)
    local f = (scale_percent or 100) / 100.0
    local local_cx = ((minx + maxx) * 0.5) * f
    local local_cz = ((minz + maxz) * 0.5) * f
    local ox, oz = rotate_local(local_cx, local_cz, yaw)
    return make_obb(
        x + ox, z + oz,
        math.abs(maxx - minx) * 0.5 * f,
        math.abs(maxz - minz) * 0.5 * f,
        yaw, tag
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

    if contains(path, "cs_street_lamp.fpe") then t.lamp = t.lamp or e end
    if contains(path, "cs_planter_01.fpe") then t.planter = t.planter or e end
    if contains(path, "cs_trash_can.fpe") then t.trash = t.trash or e end
    if contains(path, "cs_bottle_can_cluster_01.fpe") then t.bottles = t.bottles or e end
    if contains(path, "cs_newspaper_cluster") then t.paper_cluster = t.paper_cluster or e end
    if contains(path, "cs_newspaper_01.fpe") then t.paper1 = t.paper1 or e end
    if contains(path, "cs_newspaper_02.fpe") then t.paper2 = t.paper2 or e end

    if contains(path, "cs_bench.fpe") then t.bench = t.bench or e end
    if contains(path, "cs_bus_stop.fpe") then t.bus_stop = t.bus_stop or e end
    if contains(path, "cs_bus_stop_neon_sign.fpe") then t.bus_stop_neon = t.bus_stop_neon or e end
    if contains(path, "cs_atm.fpe") then t.atm = t.atm or e end
    if contains(path, "cs_dumpster_closed.fpe") then t.dumpster = t.dumpster or e end
    if contains(path, "cs_fireplug.fpe") then t.fireplug = t.fireplug or e end
    if contains(path, "cs_cardboard.fpe") then t.cardboard = t.cardboard or e end
    if contains(path, "cs_box_01.fpe") then t.box1 = t.box1 or e end
    if contains(path, "cs_box_02.fpe") then t.box2 = t.box2 or e end
    if contains(path, "cs_aircon_01_stand.fpe") then t.aircon_stand = t.aircon_stand or e end
    if contains(path, "cs_aircon_01.fpe") then t.aircon = t.aircon or e end

    -- The DLC contains multiple curb/parking protection pieces. Their precise
    -- filenames differ by pack revision, so classify by semantics rather than
    -- hard-coding one spelling. This activates automatically when an exemplar is
    -- present in the level's seed set.
    if (contains(path, "parking") and contains(path, "post")) or contains(path, "bollard") then
        t.parking_post = t.parking_post or e
    end
    if (contains(path, "rail") and not contains(path, "fireescape")) or
       (contains(path, "parking") and contains(path, "barrier")) then
        t.rail = t.rail or e
    end
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
                    roads[#roads + 1] = { e = e, footprint = footprint_from_entity(e, "road") }
                elseif is_sidewalk(path) then
                    sidewalks[#sidewalks + 1] = { e = e, footprint = footprint_from_entity(e, "sidewalk") }
                end
            end

            -- Include runtime-generated CITY V3 building pieces in blockers so
            -- detail never appears inside a finished facade or tower base.
            if is_building(path) then
                buildings[#buildings + 1] = { e = e, footprint = footprint_from_entity(e, "building") }
            end
        end
    end

    local template_count = 0
    for _, v in pairs(t) do if v ~= nil then template_count = template_count + 1 end end
    stats.templates = template_count
    stats.roads = #roads
    stats.sidewalks = #sidewalks

    if #roads == 0 then status = "no authored roads"; return nil end
    if #sidewalks == 0 then status = "no authored sidewalks"; return nil end
    if t.lamp == nil and t.planter == nil and t.trash == nil and t.rail == nil and t.parking_post == nil then
        status = "no street-detail exemplars"
        return nil
    end

    return { templates = t, roads = roads, sidewalks = sidewalks, buildings = buildings }
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

local function top_after(template, bottom_y, scale)
    local _, miny, _, _, maxy, _ = bounds(template)
    return bottom_y + math.abs(maxy - miny) * ((scale or 100) / 100.0)
end

local function prop_clear(scan, template, x, z, yaw, scale)
    if template == nil then return false, nil end
    local fp = footprint_from_template(template, x, z, yaw, scale or 100, "detail")

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

local function queue_detail(scan, template, x, z, yaw, scale, kind, shadow, fallback_y)
    if template == nil or #jobs >= MAX_DETAILS then return false end
    local ground_y = terrain_height(x, z, fallback_y or 0)
    if fallback_y ~= nil and math.abs(ground_y - fallback_y) > MAX_TERRAIN_DELTA then
        stats.rejected_terrain = stats.rejected_terrain + 1
        return false
    end

    local clear, fp = prop_clear(scan, template, x, z, yaw, scale or 100)
    if not clear then return false end

    occupied[#occupied + 1] = fp
    jobs[#jobs + 1] = {
        template = template,
        x = x, bottom_y = ground_y, z = z,
        yaw = yaw or 0, scale = scale or 100,
        shadow = shadow ~= false,
        kind = kind or "detail"
    }

    if kind == "rail" then stats.rails = stats.rails + 1
    elseif kind == "post" then stats.posts = stats.posts + 1
    elseif kind == "bench" then stats.benches = stats.benches + 1
    elseif kind == "stop" then stats.stops = stats.stops + 1
    elseif kind == "lamp" then stats.lamps = stats.lamps + 1
    elseif kind == "planter" then stats.planters = stats.planters + 1
    elseif kind == "service" then stats.service = stats.service + 1
    elseif kind == "clutter" then stats.clutter = stats.clutter + 1 end
    return true
end

local function place_sidewalk_details(scan)
    local t = scan.templates

    for i = 1, #scan.sidewalks do
        if #jobs >= MAX_DETAILS - 8 then return end
        local sidewalk = scan.sidewalks[i]
        local fp = sidewalk.footprint
        local along_x, along_z, normal_x, normal_z, half_len, half_cross, along_yaw = axis_geometry(fp)
        if half_len > 90 and half_cross > 20 then
            local road = nearest_road(scan, fp.cx, fp.cz)
            if road ~= nil then
                local to_road_x = road.footprint.cx - fp.cx
                local to_road_z = road.footprint.cz - fp.cz
                local dot = (to_road_x * normal_x) + (to_road_z * normal_z)
                local curb_sign = (dot >= 0) and 1 or -1
                local curb_nx = normal_x * curb_sign
                local curb_nz = normal_z * curb_sign
                local outer_nx = -curb_nx
                local outer_nz = -curb_nz
                local curb_offset = math.max(15, half_cross * 0.58)
                local outer_offset = math.max(20, half_cross * 0.28)

                local anchors = { 0 }
                if half_len > 330 then
                    local spread = math.min(half_len * 0.42, 360)
                    anchors = { -spread, spread }
                end

                for a = 1, #anchors do
                    if #jobs >= MAX_DETAILS - 8 then return end
                    local along = anchors[a]
                    local ax = fp.cx + along_x * along
                    local az = fp.cz + along_z * along
                    local h = site_hash(ax, az, i * 17 + a)

                    local curb_x = ax + curb_nx * curb_offset
                    local curb_z = az + curb_nz * curb_offset
                    local outer_x = ax + outer_nx * outer_offset
                    local outer_z = az + outer_nz * outer_offset

                    -- Protected curb runs: use railing when the level contains a
                    -- Cyberpunk Streets railing/barrier exemplar. Otherwise the
                    -- same slot is available for parking posts/bollards.
                    if t.rail ~= nil and (h % 5) == 0 then
                        queue_detail(scan, t.rail, curb_x, curb_z, along_yaw, 100, "rail", true, road.footprint.cy)
                    elseif t.parking_post ~= nil and (h % 3) == 0 then
                        local post_span = math.min(90, math.max(35, half_len * 0.08))
                        queue_detail(scan, t.parking_post,
                            curb_x - along_x * post_span, curb_z - along_z * post_span,
                            along_yaw, 100, "post", true, nil)
                        queue_detail(scan, t.parking_post,
                            curb_x + along_x * post_span, curb_z + along_z * post_span,
                            along_yaw, 100, "post", true, nil)
                    elseif t.fireplug ~= nil and (h % 11) == 0 then
                        queue_detail(scan, t.fireplug, curb_x, curb_z, along_yaw, 100, "post", true, nil)
                    end

                    -- Pedestrian-side furniture stays on the building/outer side of
                    -- the pavement, leaving the center of the sidewalk readable.
                    if t.bus_stop ~= nil and half_len > 420 and (h % 19) == 0 then
                        queue_detail(scan, t.bus_stop, outer_x, outer_z, along_yaw, 100, "stop", true, nil)
                    elseif t.bench ~= nil and (h % 9) == 0 then
                        queue_detail(scan, t.bench, outer_x, outer_z, along_yaw, 100, "bench", true, nil)
                    elseif t.planter ~= nil and (h % 5) == 0 then
                        queue_detail(scan, t.planter, outer_x, outer_z, along_yaw, 100, "planter", true, nil)
                    elseif t.lamp ~= nil and (h % 3) == 0 then
                        queue_detail(scan, t.lamp, outer_x, outer_z, along_yaw, 100, "lamp", true, nil)
                    end

                    if t.atm ~= nil and (h % 23) == 0 then
                        local atm_x = ax + outer_nx * math.max(45, half_cross * 0.65)
                        local atm_z = az + outer_nz * math.max(45, half_cross * 0.65)
                        queue_detail(scan, t.atm, atm_x, atm_z, along_yaw + 180, 100, "service", true, nil)
                    end
                end
            end
        end
    end
end

local function place_service_details(scan)
    local t = scan.templates
    if t.dumpster == nil and t.aircon_stand == nil and t.trash == nil then return end

    local placed = 0
    for i = 1, #scan.buildings do
        if #jobs >= MAX_DETAILS - 6 or placed >= 28 then return end
        local b = scan.buildings[i]
        local fp = b.footprint
        local road = nearest_road(scan, fp.cx, fp.cz)
        if road ~= nil then
            local dx = fp.cx - road.footprint.cx
            local dz = fp.cz - road.footprint.cz
            local len = math.sqrt(dx * dx + dz * dz)
            if len > 1 then
                dx = dx / len
                dz = dz / len
                local h = site_hash(fp.cx, fp.cz, i * 31)
                if (h % 7) == 0 then
                    local radius = math.max(fp.hx, fp.hz)
                    local px = fp.cx + dx * (radius + 110)
                    local pz = fp.cz + dz * (radius + 110)
                    local template = t.dumpster or t.aircon_stand or t.trash
                    if queue_detail(scan, template, px, pz, fp.yaw, 100, "service", true, nil) then
                        placed = placed + 1

                        if template == t.aircon_stand and t.aircon ~= nil and #jobs < MAX_DETAILS then
                            -- Air-conditioner and stand are an intentional vertical
                            -- assembly, so the upper unit shares the stand footprint.
                            local bottom_y = terrain_height(px, pz, 0)
                            local air_y = top_after(t.aircon_stand, bottom_y, 100)
                            jobs[#jobs + 1] = {
                                template = t.aircon, x = px, bottom_y = air_y, z = pz,
                                yaw = fp.yaw, scale = 100, shadow = true, kind = "service"
                            }
                            stats.service = stats.service + 1
                        elseif (h % 2) == 0 then
                            local clutter = t.box1 or t.box2 or t.cardboard or t.bottles
                            if clutter ~= nil then
                                local cx = px + dz * 85
                                local cz = pz - dx * 85
                                queue_detail(scan, clutter, cx, cz, fp.yaw, 100, "clutter", false, nil)
                            end
                        end
                    end
                end
            end
        end
    end
end

local function place_small_clutter(scan)
    local t = scan.templates
    local choices = { t.paper_cluster, t.paper1, t.paper2, t.bottles, t.cardboard }
    local valid = {}
    for i = 1, #choices do if choices[i] ~= nil then valid[#valid + 1] = choices[i] end end
    if #valid == 0 then return end

    for i = 1, #scan.sidewalks do
        if #jobs >= MAX_DETAILS - 2 then return end
        if (i % 5) == 0 then
            local fp = scan.sidewalks[i].footprint
            local along_x, along_z, normal_x, normal_z, half_len, half_cross, yaw = axis_geometry(fp)
            local road = nearest_road(scan, fp.cx, fp.cz)
            if road ~= nil then
                local tx = road.footprint.cx - fp.cx
                local tz = road.footprint.cz - fp.cz
                local sign = (((tx * normal_x) + (tz * normal_z)) >= 0) and -1 or 1
                local h = site_hash(fp.cx, fp.cz, i * 47)
                local along = ((h % 3) - 1) * math.min(half_len * 0.35, 180)
                local px = fp.cx + along_x * along + normal_x * sign * math.max(25, half_cross * 0.35)
                local pz = fp.cz + along_z * along + normal_z * sign * math.max(25, half_cross * 0.35)
                local template = valid[(h % #valid) + 1]
                queue_detail(scan, template, px, pz, yaw + (h % 40) - 20, 100, "clutter", false, nil)
            end
        end
    end
end

local function plan_generation()
    status = "scanning street kit"
    local scan = scan_level()
    if scan == nil then return false end

    status = "dressing sidewalks"
    place_sidewalk_details(scan)
    status = "dressing service edges"
    place_service_details(scan)
    status = "placing lived-in clutter"
    place_small_clutter(scan)

    if #jobs == 0 then status = "detail planner produced zero jobs"; return false end
    status = "building details 0/" .. tostring(#jobs)
    return true
end

local function spawn_job(job)
    if SpawnNewEntity == nil then last_error = "SpawnNewEntity unavailable"; return false end
    local ok, newe = pcall(SpawnNewEntity, job.template)
    if not ok or newe == nil or newe <= 0 then
        last_error = "SpawnNewEntity failed at detail job " .. tostring(job_index)
        return false
    end

    local _, miny, _, _, _, _ = bounds(job.template)
    local pivot_y = job.bottom_y - (miny * (job.scale / 100.0))
    if ResetPosition ~= nil then pcall(ResetPosition, newe, job.x, pivot_y, job.z) end
    if ResetRotation ~= nil then pcall(ResetRotation, newe, 0, job.yaw, 0) end
    if Scale ~= nil then pcall(Scale, newe, job.scale) end
    if GravityOff ~= nil then pcall(GravityOff, newe) end
    if CollisionOff ~= nil then pcall(CollisionOff, newe) end
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
        g_UserGlobal["BLACK_SIGNAL_DETAILS_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_DETAILS_CLONES"] = stats.clones
        g_UserGlobal["BLACK_SIGNAL_DETAILS_RAILS"] = stats.rails
        g_UserGlobal["BLACK_SIGNAL_DETAILS_POSTS"] = stats.posts
        g_UserGlobal["BLACK_SIGNAL_DETAILS_SERVICE"] = stats.service
    end
end

function bs_city_details.init()
    generated = false
    init_time = g_Time or 0
    jobs = {}
    spawned = {}
    occupied = {}
    job_index = 1
    status = "waiting"
    last_error = ""
    stats = {
        roads = 0, sidewalks = 0, templates = 0, clones = 0,
        rails = 0, posts = 0, benches = 0, stops = 0,
        lamps = 0, planters = 0, service = 0, clutter = 0,
        rejected_road = 0, rejected_overlap = 0, rejected_terrain = 0
    }
end

function bs_city_details.main()
    if generated then return true end
    if (g_EntityElementMax or 0) <= 0 then status = "waiting for entities"; return false end
    if (g_Time or 0) < init_time + START_DELAY_MS then return false end

    if #jobs == 0 then
        local ok, planned = pcall(plan_generation)
        if not ok then last_error = tostring(planned); status = "ERROR planning: " .. last_error; return false end
        if not planned then return false end
    end

    local processed = 0
    while job_index <= #jobs and processed < SPAWNS_PER_FRAME do
        local ok, err = pcall(spawn_job, jobs[job_index])
        if not ok then last_error = tostring(err); status = "ERROR spawn: " .. last_error; return false end
        job_index = job_index + 1
        processed = processed + 1
    end

    if job_index > #jobs then publish_ready(); return true end
    status = "building details " .. tostring(job_index - 1) .. "/" .. tostring(#jobs)
    return false
end

function bs_city_details.get_status()
    return status, stats.clones, stats.roads, stats.sidewalks, stats.templates,
        stats.rails, stats.posts, stats.benches, stats.stops, stats.lamps,
        stats.planters, stats.service, stats.clutter,
        stats.rejected_road, stats.rejected_overlap, stats.rejected_terrain, last_error
end

function bs_city_details.quit()
    jobs = {}
    spawned = {}
    occupied = {}
    job_index = 1
    generated = false
end

function bs_city_details_init(e)
    bs_city_details.init()
end

function bs_city_details_main(e)
    bs_city_details.main()
end

return bs_city_details
