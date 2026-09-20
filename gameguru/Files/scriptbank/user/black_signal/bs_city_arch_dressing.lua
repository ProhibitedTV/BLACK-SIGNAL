-- DESCRIPTION: BLACK SIGNAL architectural dressing pass. Runs after CITY V3 and street DETAIL V1, using seeded Cyberpunk Streets assets to add facade neon, fire escapes, rooftop HVAC and emissive companion pieces without scattering props blindly.

local bs_city_arch_dressing = {}

local MAX_ARCH_DETAILS = 180
local SPAWNS_PER_FRAME = 4
local START_DELAY_MS = 150
local MIN_ANCHOR_SEPARATION = 420

local generated = false
local init_time = 0
local jobs = {}
local spawned = {}
local job_index = 1
local status = "idle"
local last_error = ""
local used_anchor_cells = {}

local stats = {
    templates = 0,
    anchors = 0,
    signs = 0,
    fireescapes = 0,
    rooftop = 0,
    emissives = 0,
    clones = 0
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

local function rotate_local(x, z, yaw)
    local r = math.rad(yaw or 0)
    local c = math.cos(r)
    local s = math.sin(r)
    return (x * c) + (z * s), (-x * s) + (z * c)
end

local function make_footprint(e)
    local x, _, z, _, yaw, _ = pos_ang(e)
    local minx, _, minz, maxx, _, maxz = bounds(e)
    local sx, _, sz = scales(e)
    local local_cx = ((minx + maxx) * 0.5) * sx
    local local_cz = ((minz + maxz) * 0.5) * sz
    local ox, oz = rotate_local(local_cx, local_cz, yaw)
    local hx = math.max(1, math.abs(maxx - minx) * 0.5 * math.abs(sx))
    local hz = math.max(1, math.abs(maxz - minz) * 0.5 * math.abs(sz))
    local r = math.rad(yaw or 0)
    return {
        cx = x + ox, cz = z + oz,
        hx = hx, hz = hz,
        ux = math.cos(r), uz = -math.sin(r),
        vx = math.sin(r), vz = math.cos(r),
        yaw = yaw or 0
    }
end

local function axis_geometry(box)
    if box.hx >= box.hz then
        return box.ux, box.uz, box.vx, box.vz, box.hx, box.hz, box.yaw
    end
    return box.vx, box.vz, box.ux, box.uz, box.hz, box.hx, box.yaw + 90
end

local function entity_vertical_span(e)
    local _, y = pos_ang(e)
    local _, miny, _, _, maxy, _ = bounds(e)
    local _, sy = scales(e)
    local bottom = y + (miny * sy)
    local top = y + (maxy * sy)
    if top < bottom then bottom, top = top, bottom end
    return bottom, top
end

local function distance_sq(ax, az, bx, bz)
    local dx = ax - bx
    local dz = az - bz
    return dx * dx + dz * dz
end

local function site_hash(x, z, salt)
    local xi = math.floor(x / 50)
    local zi = math.floor(z / 50)
    local v = (xi * 73856093) + (zi * 19349663) + ((salt or 0) * 83492791)
    if v < 0 then v = -v end
    return v
end

local function is_pack(path)
    return contains(path, "cyberpunk streets booster pack")
end

local function is_road(path)
    return is_pack(path) and contains(path, "streets and sidewalks\\streets\\")
end

local function is_building_anchor(path)
    if not is_pack(path) then return false end
    if contains(path, "background buildings") and contains(path, "_base") then return true end
    return false
end

local function is_roof_anchor(path)
    if not is_pack(path) then return false end
    return contains(path, "background buildings") and contains(path, "_top.fpe")
end

local function capture_template(t, path, e)
    if not original_entity(e) or not is_pack(path) then return end

    if contains(path, "cs_neon_01.fpe") then t.neon1 = t.neon1 or e end
    if contains(path, "cs_neon_02.fpe") then t.neon2 = t.neon2 or e end
    if contains(path, "cs_neon_03.fpe") then t.neon3 = t.neon3 or e end
    if contains(path, "cs_neon_04.fpe") then t.neon4 = t.neon4 or e end
    if contains(path, "cs_neon_05.fpe") then t.neon5 = t.neon5 or e end
    if contains(path, "cs_neon_06.fpe") then t.neon6 = t.neon6 or e end
    if contains(path, "cs_neon_07.fpe") then t.neon7 = t.neon7 or e end
    if contains(path, "cs_neon_emitter.fpe") then t.neon_emitter = t.neon_emitter or e end

    if contains(path, "cs_fireescape_01.fpe") then t.fireescape1 = t.fireescape1 or e end
    if contains(path, "cs_fireescape_02.fpe") then t.fireescape2 = t.fireescape2 or e end
    if contains(path, "cs_fireescape_ladder.fpe") then t.fireescape_ladder = t.fireescape_ladder or e end

    if contains(path, "cs_aircon_01_stand.fpe") then t.aircon1_stand = t.aircon1_stand or e end
    if contains(path, "cs_aircon_01.fpe") then t.aircon1 = t.aircon1 or e end
    if contains(path, "cs_aircon_02_stand.fpe") then t.aircon2_stand = t.aircon2_stand or e end
    if contains(path, "cs_aircon_02.fpe") then t.aircon2 = t.aircon2 or e end

    if contains(path, "cs_atm_screen.fpe") then t.atm_screen = t.atm_screen or e end
    if contains(path, "cs_bus_stop_neon_sign.fpe") then t.bus_stop_neon = t.bus_stop_neon or e end

    if contains(path, "cs_overpass_01_emission.fpe") then t.overpass_emission = t.overpass_emission or e end
    if contains(path, "cs_overpass_01_emitter.fpe") then t.overpass_emitter = t.overpass_emitter or e end
    if contains(path, "cs_overpass_01.fpe") then t.overpass = t.overpass or e end
end

local function scan_level()
    local t = {}
    local roads = {}
    local anchors = {}
    local roofs = {}
    local atms = {}
    local bus_stops = {}
    local maxe = g_EntityElementMax or 0

    for e = 1, maxe do
        local path = entity_path(e)
        if path ~= "" then
            capture_template(t, path, e)

            if is_road(path) and original_entity(e) then
                roads[#roads + 1] = { e = e, footprint = make_footprint(e) }
            end
            if is_building_anchor(path) then
                anchors[#anchors + 1] = { e = e, footprint = make_footprint(e) }
            end
            if is_roof_anchor(path) then
                roofs[#roofs + 1] = { e = e, footprint = make_footprint(e) }
            end
            if contains(path, "cs_atm.fpe") and not contains(path, "_screen") then
                atms[#atms + 1] = e
            end
            if contains(path, "cs_bus_stop.fpe") and not contains(path, "_neon_sign") then
                bus_stops[#bus_stops + 1] = e
            end
        end
    end

    local template_count = 0
    for _, v in pairs(t) do if v ~= nil then template_count = template_count + 1 end end
    stats.templates = template_count
    stats.anchors = #anchors

    if template_count == 0 then
        status = "no ARCH V1 seed exemplars"
        return nil
    end

    return {
        templates = t,
        roads = roads,
        anchors = anchors,
        roofs = roofs,
        atms = atms,
        bus_stops = bus_stops
    }
end

local function nearest_road(scan, x, z)
    local best = nil
    local best_d = nil
    for i = 1, #scan.roads do
        local r = scan.roads[i]
        local d = distance_sq(x, z, r.footprint.cx, r.footprint.cz)
        if best_d == nil or d < best_d then
            best = r
            best_d = d
        end
    end
    return best
end

local function anchor_cell_free(x, z, salt)
    local cell = math.max(100, MIN_ANCHOR_SEPARATION)
    local key = tostring(math.floor(x / cell)) .. ":" .. tostring(math.floor(z / cell)) .. ":" .. tostring(salt or 0)
    if used_anchor_cells[key] then return false end
    used_anchor_cells[key] = true
    return true
end

local function queue_job(template, x, bottom_y, z, yaw, scale, kind, shadow)
    if template == nil or #jobs >= MAX_ARCH_DETAILS then return false end
    jobs[#jobs + 1] = {
        template = template,
        x = x,
        bottom_y = bottom_y,
        z = z,
        yaw = yaw or 0,
        scale = scale or 100,
        kind = kind or "arch",
        shadow = shadow ~= false,
        exact_y = false
    }
    if kind == "sign" then stats.signs = stats.signs + 1
    elseif kind == "fireescape" then stats.fireescapes = stats.fireescapes + 1
    elseif kind == "rooftop" then stats.rooftop = stats.rooftop + 1
    elseif kind == "emissive" then stats.emissives = stats.emissives + 1 end
    return true
end

local function queue_exact(template, x, y, z, yaw, scale, kind, shadow)
    if template == nil or #jobs >= MAX_ARCH_DETAILS then return false end
    jobs[#jobs + 1] = {
        template = template,
        x = x,
        pivot_y = y,
        z = z,
        yaw = yaw or 0,
        scale = scale or 100,
        kind = kind or "emissive",
        shadow = shadow ~= false,
        exact_y = true
    }
    if kind == "emissive" then stats.emissives = stats.emissives + 1 end
    return true
end

local function neon_choices(t)
    local raw = { t.neon1, t.neon2, t.neon3, t.neon4, t.neon5, t.neon6, t.neon7 }
    local out = {}
    for i = 1, #raw do if raw[i] ~= nil then out[#out + 1] = raw[i] end end
    return out
end

local function fireescape_choices(t)
    local raw = { t.fireescape1, t.fireescape2 }
    local out = {}
    for i = 1, #raw do if raw[i] ~= nil then out[#out + 1] = raw[i] end end
    return out
end

local function plan_facade_dressing(scan)
    local neons = neon_choices(scan.templates)
    local escapes = fireescape_choices(scan.templates)

    for i = 1, #scan.anchors do
        if #jobs >= MAX_ARCH_DETAILS - 8 then return end
        local anchor = scan.anchors[i]
        local fp = anchor.footprint
        local road = nearest_road(scan, fp.cx, fp.cz)
        if road ~= nil then
            local along_x, along_z, normal_x, normal_z, _, half_cross, along_yaw = axis_geometry(fp)
            local to_road_x = road.footprint.cx - fp.cx
            local to_road_z = road.footprint.cz - fp.cz
            local normal_dot = (to_road_x * normal_x) + (to_road_z * normal_z)
            local front_sign = (normal_dot >= 0) and 1 or -1
            local front_nx = normal_x * front_sign
            local front_nz = normal_z * front_sign
            local rear_nx = -front_nx
            local rear_nz = -front_nz
            local facade_offset = half_cross + 18
            local bottom_y, top_y = entity_vertical_span(anchor.e)
            local height = math.max(100, top_y - bottom_y)
            local h = site_hash(fp.cx, fp.cz, i * 71)

            if #neons > 0 and (h % 3) ~= 0 and anchor_cell_free(fp.cx, fp.cz, 1) then
                local template = neons[(h % #neons) + 1]
                local along_shift = ((h % 3) - 1) * math.min(120, math.max(45, fp.hx * 0.25))
                local sx = fp.cx + front_nx * facade_offset + along_x * along_shift
                local sz = fp.cz + front_nz * facade_offset + along_z * along_shift
                local sign_y = bottom_y + math.min(260, math.max(90, height * 0.34))
                local sign_yaw = along_yaw + ((front_sign > 0) and 0 or 180)
                queue_job(template, sx, sign_y, sz, sign_yaw, 100, "sign", true)
            end

            if #escapes > 0 and (h % 5) == 0 and anchor_cell_free(fp.cx, fp.cz, 2) then
                local template = escapes[(h % #escapes) + 1]
                local ex = fp.cx + rear_nx * (half_cross + 14)
                local ez = fp.cz + rear_nz * (half_cross + 14)
                local escape_y = bottom_y + math.min(110, math.max(35, height * 0.12))
                local escape_yaw = along_yaw + ((front_sign > 0) and 180 or 0)
                if queue_job(template, ex, escape_y, ez, escape_yaw, 100, "fireescape", true) then
                    if scan.templates.fireescape_ladder ~= nil and #jobs < MAX_ARCH_DETAILS then
                        queue_job(scan.templates.fireescape_ladder, ex, escape_y, ez, escape_yaw, 100, "fireescape", true)
                    end
                end
            end
        end
    end
end

local function plan_rooftop_hvac(scan)
    local t = scan.templates
    if t.aircon1 == nil and t.aircon2 == nil then return end

    local placed = 0
    for i = 1, #scan.roofs do
        if #jobs >= MAX_ARCH_DETAILS - 4 or placed >= 24 then return end
        local roof = scan.roofs[i]
        local fp = roof.footprint
        local h = site_hash(fp.cx, fp.cz, i * 97)
        if (h % 3) == 0 and anchor_cell_free(fp.cx, fp.cz, 3) then
            local _, roof_top = entity_vertical_span(roof.e)
            local along_x, along_z, _, _, half_len, _, yaw = axis_geometry(fp)
            local offset = math.min(half_len * 0.22, 110)
            local px = fp.cx + along_x * (((h % 2) == 0) and offset or -offset)
            local pz = fp.cz + along_z * (((h % 2) == 0) and offset or -offset)

            local use_second = (h % 2) == 0 and t.aircon2 ~= nil
            local stand = use_second and t.aircon2_stand or t.aircon1_stand
            local unit = use_second and t.aircon2 or t.aircon1
            if unit == nil then unit = t.aircon1 or t.aircon2 end

            if stand ~= nil then
                queue_job(stand, px, roof_top + 2, pz, yaw, 100, "rooftop", true)
                local _, miny, _, _, maxy, _ = bounds(stand)
                local stand_h = math.abs(maxy - miny)
                queue_job(unit, px, roof_top + 2 + stand_h, pz, yaw, 100, "rooftop", true)
            else
                queue_job(unit, px, roof_top + 2, pz, yaw, 100, "rooftop", true)
            end
            placed = placed + 1
        end
    end
end

local function plan_emissive_companions(scan)
    local t = scan.templates

    if t.atm_screen ~= nil then
        for i = 1, #scan.atms do
            if #jobs >= MAX_ARCH_DETAILS - 2 then break end
            local e = scan.atms[i]
            if e ~= t.atm_screen then
                local x, y, z, _, yaw = pos_ang(e)
                queue_exact(t.atm_screen, x, y, z, yaw, 100, "emissive", false)
            end
        end
    end

    if t.bus_stop_neon ~= nil then
        for i = 1, #scan.bus_stops do
            if #jobs >= MAX_ARCH_DETAILS - 2 then break end
            local e = scan.bus_stops[i]
            if e ~= t.bus_stop_neon then
                local x, y, z, _, yaw = pos_ang(e)
                queue_exact(t.bus_stop_neon, x, y, z, yaw, 100, "emissive", false)
            end
        end
    end
end

local function plan_generation()
    status = "scanning architecture kit"
    local scan = scan_level()
    if scan == nil then return false end

    status = "dressing facades"
    plan_facade_dressing(scan)
    status = "dressing rooftops"
    plan_rooftop_hvac(scan)
    status = "pairing emissives"
    plan_emissive_companions(scan)

    if #jobs == 0 then
        status = "ARCH V1 seeds present but produced zero jobs"
        return false
    end

    status = "building architecture 0/" .. tostring(#jobs)
    return true
end

local function spawn_job(job)
    if SpawnNewEntity == nil then
        last_error = "SpawnNewEntity unavailable"
        return false
    end

    local ok, newe = pcall(SpawnNewEntity, job.template)
    if not ok or newe == nil or newe <= 0 then
        last_error = "SpawnNewEntity failed at ARCH job " .. tostring(job_index)
        return false
    end

    local pivot_y = job.pivot_y
    if not job.exact_y then
        local _, miny = bounds(job.template)
        pivot_y = job.bottom_y - (miny * (job.scale / 100.0))
    end

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
        g_UserGlobal["BLACK_SIGNAL_ARCH_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_ARCH_CLONES"] = stats.clones
        g_UserGlobal["BLACK_SIGNAL_ARCH_SIGNS"] = stats.signs
        g_UserGlobal["BLACK_SIGNAL_ARCH_FIREESCAPES"] = stats.fireescapes
        g_UserGlobal["BLACK_SIGNAL_ARCH_ROOFTOP"] = stats.rooftop
        g_UserGlobal["BLACK_SIGNAL_ARCH_EMISSIVES"] = stats.emissives
    end
end

function bs_city_arch_dressing.init()
    generated = false
    init_time = g_Time or 0
    jobs = {}
    spawned = {}
    used_anchor_cells = {}
    job_index = 1
    status = "waiting"
    last_error = ""
    stats = {
        templates = 0, anchors = 0, signs = 0, fireescapes = 0,
        rooftop = 0, emissives = 0, clones = 0
    }
end

function bs_city_arch_dressing.main()
    if generated then return true end
    if (g_EntityElementMax or 0) <= 0 then status = "waiting for entities"; return false end
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
        local ok, result = pcall(spawn_job, jobs[job_index])
        if not ok then
            last_error = tostring(result)
            status = "ERROR spawn: " .. last_error
            return false
        end
        job_index = job_index + 1
        processed = processed + 1
    end

    if job_index > #jobs then
        publish_ready()
        return true
    end

    status = "building architecture " .. tostring(job_index - 1) .. "/" .. tostring(#jobs)
    return false
end

function bs_city_arch_dressing.get_status()
    return status, stats.clones, stats.templates, stats.anchors, stats.signs,
        stats.fireescapes, stats.rooftop, stats.emissives, last_error
end

function bs_city_arch_dressing.quit()
    jobs = {}
    spawned = {}
    used_anchor_cells = {}
    job_index = 1
    generated = false
end

function bs_city_arch_dressing_init(e)
    bs_city_arch_dressing.init()
end

function bs_city_arch_dressing_main(e)
    bs_city_arch_dressing.main()
end

return bs_city_arch_dressing
