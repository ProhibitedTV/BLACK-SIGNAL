-- DESCRIPTION: BLACK SIGNAL modular District 12 city generator. Builds collision-safe parcels from the authored road network, then assembles varied buildings from snap-friendly Cyberpunk Streets modules and stacked background-building cores.

local bs_city_v3 = {}

local MAX_CLONES = 850
local MAX_BUILDINGS = 28
local SPAWNS_PER_FRAME = 4
local START_DELAY_MS = 500

local SIDEWALK_BUFFER = 230
local ALLEY_GAP = 260
local OUTWARD_RETRY_STEP = 220
local OUTWARD_RETRIES = 5
local PLAYER_CLEARANCE = 850
local ROAD_MARGIN = 110
local PARCEL_MARGIN = 90
local EXISTING_MARGIN = 120
local MAX_TERRAIN_DELTA = 120
local MAX_TERRAIN_SPREAD = 90

local generated = false
local init_time = 0
local spawned = {}
local jobs = {}
local job_index = 1
local status = "idle"
local last_error = ""
local accepted_buildings = {}
local alley_anchors = {}

local stats = {
    roads = 0,
    templates = 0,
    parcels = 0,
    buildings = 0,
    modular = 0,
    towers = 0,
    floors = 0,
    alleys = 0,
    clones = 0,
    planned = 0,
    failed = 0,
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
    local xi = math.floor(x / 100)
    local zi = math.floor(z / 100)
    local value = (xi * 73856093) + (zi * 19349663) + ((salt or 0) * 83492791)
    if value < 0 then value = -value end
    return value
end

local function rotate_local(x, z, yaw)
    local r = math.rad(yaw or 0)
    local c = math.cos(r)
    local s = math.sin(r)
    return (x * c) + (z * s), (-x * s) + (z * c)
end

local function local_to_world(cx, cz, yaw, lx, lz)
    local dx, dz = rotate_local(lx, lz, yaw)
    return cx + dx, cz + dz
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
    local distance = math.abs((dx * ax) + (dz * az))
    return distance > (projected_radius(a, ax, az, margin_a) + projected_radius(b, ax, az, margin_b))
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

local function is_road(path)
    return contains(path, "cyberpunk streets booster pack\\streets and sidewalks\\streets\\") and contains(path, ".fpe")
end

local function is_straight_road(path)
    return contains(path, "cs_street_straight_4x.fpe") or contains(path, "cs_street_straight_2x.fpe")
end

local function is_existing_architecture(path)
    if not contains(path, "cyberpunk streets booster pack") then return false end
    if is_road(path) then return false end
    return contains(path, "background buildings") or contains(path, "store fronts") or contains(path, "\\buildings\\")
end

local function template_metrics(template)
    if template == nil or template <= 0 then return 400, 400, 400 end
    local minx, miny, minz, maxx, maxy, maxz = bounds(template)
    return math.max(1, math.abs(maxx - minx)), math.max(1, math.abs(maxy - miny)), math.max(1, math.abs(maxz - minz))
end

local function scan_level()
    local t = { kits = {} }
    local roads = {}
    local architecture = {}
    local maxe = g_EntityElementMax or 0

    local kit1 = {}
    local kit3 = {}
    local kit4 = {}

    for e = 1, maxe do
        if original_entity(e) then
            local path = entity_path(e)
            if path ~= "" then
                local x, y, z, _, yaw, _ = pos_ang(e)

                if contains(path, "cs_bg_building_01_base2.fpe") then kit1.base2 = kit1.base2 or e end
                if contains(path, "cs_bg_building_01_base.fpe") then kit1.base = kit1.base or e end
                if contains(path, "cs_bg_building_01_floor_between.fpe") then kit1.between = kit1.between or e end
                if contains(path, "cs_bg_building_01_floor.fpe") then kit1.floor = kit1.floor or e end
                if contains(path, "cs_bg_building_01_top.fpe") then kit1.top = kit1.top or e end

                if contains(path, "cs_bg_building_03_base.fpe") then kit3.base = kit3.base or e end
                if contains(path, "cs_bg_building_03_floor.fpe") then kit3.floor = kit3.floor or e end
                if contains(path, "cs_bg_building_03_top.fpe") then kit3.top = kit3.top or e end

                if contains(path, "cs_bg_building_04_base2.fpe") then kit4.base2 = kit4.base2 or e end
                if contains(path, "cs_bg_building_04_base.fpe") then kit4.base = kit4.base or e end
                if contains(path, "cs_bg_building_04_floor.fpe") then kit4.floor = kit4.floor or e end
                if contains(path, "cs_bg_building_04_top.fpe") then kit4.top = kit4.top or e end

                if contains(path, "cs_wall_corner_01.fpe") then t.wall_corner = t.wall_corner or e end
                if contains(path, "cs_walls_01_window_with_bars.fpe") then t.window = t.window or e end
                if contains(path, "cs_wall_01_entry_01.fpe") then t.entry1 = t.entry1 or e end
                if contains(path, "cs_wall_01_entry_04.fpe") then t.entry4 = t.entry4 or e end
                if contains(path, "cs_wall_01_overhang_corner.fpe") then t.overhang_corner = t.overhang_corner or e end
                if contains(path, "cs_wall_01_overhang.fpe") then t.overhang = t.overhang or e end
                if contains(path, "cs_wall_01.fpe") then t.wall = t.wall or e end
                if contains(path, "cs_roof_tile_4x4.fpe") then t.roof4 = t.roof4 or e end
                if contains(path, "cs_roof_tile_2x2.fpe") then t.roof2 = t.roof2 or e end
                if contains(path, "cs_store_front_02_corner_with_window.fpe") then t.store_window = t.store_window or e end
                if contains(path, "cs_store_front_02_corner_neon_opposite.fpe") then t.store_neon = t.store_neon or e end
                if contains(path, "cs_street_lamp.fpe") then t.lamp = t.lamp or e end
                if contains(path, "cs_planter_01.fpe") then t.planter = t.planter or e end
                if contains(path, "cs_trash_can.fpe") then t.trash = t.trash or e end
                if contains(path, "cs_bottle_can_cluster_01.fpe") then t.bottles = t.bottles or e end
                if contains(path, "cs_newspaper_01.fpe") then t.paper1 = t.paper1 or e end
                if contains(path, "cs_newspaper_02.fpe") then t.paper2 = t.paper2 or e end

                if is_road(path) then
                    roads[#roads + 1] = {
                        e = e, x = x, y = y, z = z, yaw = yaw or 0,
                        path = path,
                        straight = is_straight_road(path),
                        footprint = footprint_from_entity(e, "road")
                    }
                elseif is_existing_architecture(path) then
                    architecture[#architecture + 1] = {
                        e = e, x = x, y = y, z = z, yaw = yaw or 0,
                        path = path,
                        footprint = footprint_from_entity(e, "existing")
                    }
                end
            end
        end
    end

    if kit1.floor ~= nil then t.kits[#t.kits + 1] = kit1 end
    if kit3.floor ~= nil then t.kits[#t.kits + 1] = kit3 end
    if kit4.floor ~= nil then t.kits[#t.kits + 1] = kit4 end

    stats.roads = #roads
    local template_count = #t.kits
    for key, value in pairs(t) do
        if key ~= "kits" and value ~= nil then template_count = template_count + 1 end
    end
    stats.templates = template_count

    if #roads == 0 then status = "no authored roads"; return nil end
    if #t.kits == 0 then status = "no background building kits"; return nil end
    if t.wall == nil and t.window == nil then status = "no modular wall templates"; return nil end

    table.sort(roads, function(a, b)
        if a.x == b.x then
            if a.z == b.z then return a.yaw < b.yaw end
            return a.z < b.z
        end
        return a.x < b.x
    end)

    return { templates = t, roads = roads, architecture = architecture }
end

local function choose_kit(t, hash)
    if #t.kits == 0 then return nil end
    return t.kits[(hash % #t.kits) + 1]
end

local function largest_kit_footprint(kit, yaw, scale)
    local best = nil
    local best_area = -1
    local function consider(template)
        if template == nil then return end
        local fp = footprint_from_template(template, 0, 0, yaw, scale, "kit")
        local area = fp.hx * fp.hz
        if area > best_area then best = fp; best_area = area end
    end
    consider(kit.base2)
    consider(kit.base)
    consider(kit.floor)
    consider(kit.between)
    consider(kit.top)
    return best
end

local function floor_height(template, scale)
    local _, miny, _, _, maxy, _ = bounds(template)
    return math.abs(maxy - miny) * ((scale or 100) / 100.0)
end

local function choose_style(scan, hash, depth)
    local t = scan.templates
    local archetypes = { "shopblock", "midrise", "slab", "industrial", "needle", "corporate" }
    local name = archetypes[(hash % #archetypes) + 1]
    if depth >= 2 and (hash % 3) ~= 0 then name = ((hash % 2) == 0) and "needle" or "corporate" end

    local style = { name = name, hash = hash, kit = choose_kit(t, hash) }
    if name == "shopblock" then
        style.bays = 3 + (hash % 2); style.floors = 4 + (hash % 3); style.facade_floors = 4
        style.podium_scale = 98 + (hash % 8); style.upper_scale = 94 + (hash % 5); style.overhang = true
    elseif name == "midrise" then
        style.bays = 3 + (hash % 2); style.floors = 7 + (hash % 4); style.facade_floors = 4
        style.podium_scale = 100 + (hash % 6); style.upper_scale = 90 + (hash % 7); style.overhang = (hash % 2) == 0
    elseif name == "slab" then
        style.bays = 4 + (hash % 2); style.floors = 8 + (hash % 5); style.facade_floors = 4
        style.podium_scale = 102 + (hash % 7); style.upper_scale = 90 + (hash % 6); style.overhang = true
    elseif name == "industrial" then
        style.bays = 4; style.floors = 5 + (hash % 3); style.facade_floors = 3
        style.podium_scale = 105 + (hash % 8); style.upper_scale = 100; style.overhang = (hash % 2) == 0
    elseif name == "needle" then
        style.bays = 2 + (hash % 2); style.floors = 12 + (hash % 7); style.facade_floors = 3
        style.podium_scale = 96 + (hash % 5); style.upper_scale = 80 + (hash % 10); style.overhang = true
    else
        style.bays = 3; style.floors = 15 + (hash % 8); style.facade_floors = 2
        style.podium_scale = 100 + (hash % 5); style.upper_scale = 84 + (hash % 10); style.overhang = false
    end
    style.facade_floors = math.min(style.facade_floors, style.floors)
    return style
end

local function style_dimensions(scan, style, yaw)
    local t = scan.templates
    local wall_template = t.wall or t.window
    local wx, _, wz = template_metrics(wall_template)
    local module_span = math.max(wx, wz)
    local kit_fp = largest_kit_footprint(style.kit, yaw, style.podium_scale)
    if kit_fp == nil then return nil end

    local core_width = kit_fp.hx * 2
    local core_depth = kit_fp.hz * 2
    local facade_width = module_span * style.bays
    local width = math.max(core_width, facade_width) + 60
    local depth = math.max(core_depth, module_span * 1.65) + 60
    return width, depth, module_span
end

local function road_geometry(road)
    local fp = road.footprint
    if fp.hx >= fp.hz then
        return fp.ux, fp.uz, fp.vx, fp.vz, fp.hx, fp.hz, road.yaw
    end
    return fp.vx, fp.vz, fp.ux, fp.uz, fp.hz, fp.hx, road.yaw + 90
end

local function terrain_ok(box, road_y)
    local samples = { { x = box.cx, z = box.cz } }
    local corners = obb_corners(box)
    for i = 1, #corners do samples[#samples + 1] = corners[i] end
    local min_h, max_h = nil, nil
    local center_h = terrain_height(box.cx, box.cz, road_y)
    for i = 1, #samples do
        local h = terrain_height(samples[i].x, samples[i].z, center_h)
        if min_h == nil or h < min_h then min_h = h end
        if max_h == nil or h > max_h then max_h = h end
    end
    if math.abs(center_h - road_y) > MAX_TERRAIN_DELTA then return false, center_h end
    if min_h ~= nil and max_h ~= nil and (max_h - min_h) > MAX_TERRAIN_SPREAD then return false, center_h end
    return true, center_h
end

local function parcel_clear(scan, plan, occupied)
    if g_PlayerPosX ~= nil and g_PlayerPosZ ~= nil then
        local dx = plan.footprint.cx - g_PlayerPosX
        local dz = plan.footprint.cz - g_PlayerPosZ
        local radius = math.sqrt(plan.footprint.hx * plan.footprint.hx + plan.footprint.hz * plan.footprint.hz)
        if (dx * dx + dz * dz) < ((PLAYER_CLEARANCE + radius) * (PLAYER_CLEARANCE + radius)) then
            stats.rejected_overlap = stats.rejected_overlap + 1
            return false
        end
    end

    for i = 1, #scan.roads do
        if obb_overlaps(plan.footprint, scan.roads[i].footprint, PARCEL_MARGIN, ROAD_MARGIN) then
            stats.rejected_road = stats.rejected_road + 1
            return false
        end
    end

    for i = 1, #occupied do
        if obb_overlaps(plan.footprint, occupied[i], PARCEL_MARGIN, EXISTING_MARGIN) then
            stats.rejected_overlap = stats.rejected_overlap + 1
            return false
        end
    end

    local ok, ground_y = terrain_ok(plan.footprint, plan.road_y)
    if not ok then stats.rejected_terrain = stats.rejected_terrain + 1; return false end
    plan.y = ground_y
    return true
end

local function make_plan(scan, x, z, road_y, yaw, side, hash, depth, outward_x, outward_z)
    local style = choose_style(scan, hash, depth)
    local width, parcel_depth, module_span = style_dimensions(scan, style, yaw)
    if width == nil then return nil end
    return {
        x = x, z = z, road_y = road_y, yaw = yaw, side = side,
        hash = hash, depth = depth, style = style,
        width = width, parcel_depth = parcel_depth, module_span = module_span,
        outward_x = outward_x, outward_z = outward_z,
        footprint = make_obb(x, z, width * 0.5, parcel_depth * 0.5, yaw, "parcel")
    }
end

local function accept_plan(scan, base_plan, occupied)
    for attempt = 0, OUTWARD_RETRIES do
        local shift = OUTWARD_RETRY_STEP * attempt
        local x = base_plan.x + base_plan.outward_x * shift
        local z = base_plan.z + base_plan.outward_z * shift
        local plan = make_plan(scan, x, z, base_plan.road_y, base_plan.yaw, base_plan.side, base_plan.hash, base_plan.depth, base_plan.outward_x, base_plan.outward_z)
        if plan ~= nil and parcel_clear(scan, plan, occupied) then
            occupied[#occupied + 1] = plan.footprint
            accepted_buildings[#accepted_buildings + 1] = plan
            stats.parcels = stats.parcels + 1
            return plan
        end
    end
    return nil
end

local function collect_parcels(scan)
    local occupied = {}
    for i = 1, #scan.architecture do occupied[#occupied + 1] = scan.architecture[i].footprint end

    for i = 1, #scan.roads do
        if #accepted_buildings >= MAX_BUILDINGS then break end
        local road = scan.roads[i]
        if road.straight then
            local along_x, along_z, normal_x, normal_z, half_len, half_cross, building_yaw = road_geometry(road)
            local slot_offsets = { 0 }
            if half_len > 1100 then
                slot_offsets = { -math.min(half_len * 0.43, 720), math.min(half_len * 0.43, 720) }
            end

            for slot_index = 1, #slot_offsets do
                for side = -1, 1, 2 do
                    if #accepted_buildings >= MAX_BUILDINGS then break end
                    local along_offset = slot_offsets[slot_index]
                    local anchor_x = road.footprint.cx + along_x * along_offset
                    local anchor_z = road.footprint.cz + along_z * along_offset
                    local h = site_hash(anchor_x, anchor_z, (side * 17) + slot_index)

                    local style = choose_style(scan, h, 1)
                    local width, depth = style_dimensions(scan, style, building_yaw)
                    if width ~= nil then
                        local is_alley = (h % 7) == 0
                        local outward_x = normal_x * side
                        local outward_z = normal_z * side
                        local distance = half_cross + SIDEWALK_BUFFER + (depth * 0.5)
                        local x = anchor_x + outward_x * distance
                        local z = anchor_z + outward_z * distance

                        if is_alley then
                            stats.alleys = stats.alleys + 1
                            alley_anchors[#alley_anchors + 1] = {
                                x = x, z = z, y = road.y,
                                yaw = building_yaw, side = side,
                                outward_x = outward_x, outward_z = outward_z,
                                anchor_x = anchor_x, anchor_z = anchor_z
                            }
                        else
                            local base_plan = make_plan(scan, x, z, road.y, building_yaw, side, h, 1, outward_x, outward_z)
                            local front = nil
                            if base_plan ~= nil then front = accept_plan(scan, base_plan, occupied) end

                            if front ~= nil and #accepted_buildings < MAX_BUILDINGS and (h % 3) ~= 0 then
                                local back_hash = h + 911
                                local back_style = choose_style(scan, back_hash, 2)
                                local back_width, back_depth = style_dimensions(scan, back_style, building_yaw)
                                if back_width ~= nil then
                                    local back_distance = (front.parcel_depth * 0.5) + ALLEY_GAP + (back_depth * 0.5)
                                    local bx = front.x + outward_x * back_distance
                                    local bz = front.z + outward_z * back_distance
                                    local back_plan = make_plan(scan, bx, bz, road.y, building_yaw, side, back_hash, 2, outward_x, outward_z)
                                    if back_plan ~= nil then accept_plan(scan, back_plan, occupied) end
                                end
                            end
                        end
                    end
                end
            end
        end
    end
end

local function top_after(template, bottom_y, scale)
    if template == nil or template <= 0 then return bottom_y end
    local _, miny, _, _, maxy, _ = bounds(template)
    return bottom_y + math.abs(maxy - miny) * ((scale or 100) / 100.0)
end

local function queue_piece(template, x, bottom_y, z, yaw, scale, shadow)
    if template == nil or template <= 0 then return bottom_y end
    if #jobs >= MAX_CLONES then return bottom_y end
    jobs[#jobs + 1] = {
        template = template,
        x = x, bottom_y = bottom_y, z = z,
        yaw = yaw or 0, scale = scale or 100,
        shadow = shadow ~= false
    }
    return top_after(template, bottom_y, scale)
end

local function estimate_building_cost(plan)
    local style = plan.style
    local facade = style.bays * style.facade_floors
    local accent = math.floor(style.facade_floors * 1.5)
    return style.floors + 3 + facade + accent + 5
end

local function ground_module(t, plan, bay)
    local center_bay = math.floor((plan.style.bays + 1) / 2)
    if bay == center_bay then
        if (plan.hash % 2) == 0 and t.entry4 ~= nil then return t.entry4 end
        if t.entry1 ~= nil then return t.entry1 end
    end
    if (bay == 1 or bay == plan.style.bays) and (plan.hash % 4) == 0 and t.store_neon ~= nil then
        return t.store_neon
    end
    if t.window ~= nil and (bay + plan.hash) % 3 ~= 0 then return t.window end
    return t.wall or t.window
end

local function upper_module(t, plan, floor_index, bay)
    if t.window ~= nil and ((floor_index + bay + plan.hash) % 4) ~= 0 then return t.window end
    return t.wall or t.window
end

local function plan_facade(scan, plan, facade_top_y)
    local t = scan.templates
    local wall_template = t.wall or t.window
    if wall_template == nil then return end
    local wx, wh, wz = template_metrics(wall_template)
    local module_span = math.max(wx, wz)
    local side = plan.side
    local front_lz = -side * (plan.parcel_depth * 0.5 + math.min(wx, wz) * 0.15)
    local front_yaw = plan.yaw + ((side > 0) and 180 or 0)
    local facade_floors = plan.style.facade_floors

    for floor_index = 0, facade_floors - 1 do
        local bottom_y = plan.y + (wh * floor_index)
        if bottom_y > facade_top_y then break end
        for bay = 1, plan.style.bays do
            local lx = (bay - ((plan.style.bays + 1) * 0.5)) * module_span
            local x, z = local_to_world(plan.x, plan.z, plan.yaw, lx, front_lz)
            local template = nil
            if floor_index == 0 then template = ground_module(t, plan, bay)
            else template = upper_module(t, plan, floor_index, bay) end
            queue_piece(template, x, bottom_y, z, front_yaw, 100, true)
        end

        if plan.style.overhang and floor_index > 0 and (floor_index == 1 or ((floor_index + plan.hash) % 3) == 0) and t.overhang ~= nil then
            local x, z = local_to_world(plan.x, plan.z, plan.yaw, 0, front_lz - side * 35)
            queue_piece(t.overhang, x, bottom_y, z, front_yaw, 100, true)
        end

        if t.wall_corner ~= nil and floor_index < 3 then
            local half_width = plan.width * 0.5
            local left_x, left_z = local_to_world(plan.x, plan.z, plan.yaw, -half_width, front_lz)
            local right_x, right_z = local_to_world(plan.x, plan.z, plan.yaw, half_width, front_lz)
            queue_piece(t.wall_corner, left_x, bottom_y, left_z, front_yaw, 100, true)
            queue_piece(t.wall_corner, right_x, bottom_y, right_z, front_yaw + 90, 100, true)
        end
    end
end

local function plan_roof(scan, plan, roof_y)
    local t = scan.templates
    local roof = t.roof4 or t.roof2
    if roof == nil then return end
    local rx, _, rz = template_metrics(roof)
    local span = math.max(rx, rz)
    if span <= 0 then return end
    local fit = math.min(plan.width, plan.parcel_depth) / span
    local scale = math.floor(math.max(65, math.min(135, fit * 100)))
    queue_piece(roof, plan.x, roof_y, plan.z, plan.yaw, scale, false)
end

local function plan_building(scan, plan)
    if stats.buildings >= MAX_BUILDINGS then return end
    local estimate = estimate_building_cost(plan)
    if #jobs + estimate >= MAX_CLONES then return end

    local style = plan.style
    local kit = style.kit
    if kit == nil or kit.floor == nil then return end

    local next_y = plan.y
    local base = (((plan.hash % 5) == 0) and kit.base2 or kit.base) or kit.floor
    next_y = queue_piece(base, plan.x, next_y, plan.z, plan.yaw, style.podium_scale, true)

    local podium_floors = math.min(style.floors, 2 + (plan.hash % 2))
    for floor_index = 1, style.floors do
        local scale = (floor_index <= podium_floors) and style.podium_scale or style.upper_scale
        if floor_index == podium_floors + 1 and kit.between ~= nil then
            next_y = queue_piece(kit.between, plan.x, next_y, plan.z, plan.yaw, scale, true)
        end
        next_y = queue_piece(kit.floor, plan.x, next_y, plan.z, plan.yaw, scale, plan.depth <= 1)
    end

    local roof_y = next_y
    next_y = queue_piece(kit.top or kit.floor, plan.x, next_y, plan.z, plan.yaw, style.upper_scale, plan.depth <= 1)

    if plan.depth == 1 then
        plan_facade(scan, plan, roof_y)
        plan_roof(scan, plan, next_y)
        stats.modular = stats.modular + 1
    else
        if (plan.hash % 4) == 0 then plan_roof(scan, plan, next_y) end
        stats.towers = stats.towers + 1
    end

    stats.buildings = stats.buildings + 1
    stats.floors = stats.floors + style.floors
end

local function prop_clear(scan, template, x, z, yaw)
    if template == nil then return false end
    local fp = footprint_from_template(template, x, z, yaw, 100, "prop")
    for i = 1, #scan.roads do
        if obb_overlaps(fp, scan.roads[i].footprint, 0, 20) then return false end
    end
    for i = 1, #accepted_buildings do
        if obb_overlaps(fp, accepted_buildings[i].footprint, 0, 10) then return false end
    end
    return true
end

local function plan_street_life(scan)
    local t = scan.templates
    for i = 1, #accepted_buildings do
        if #jobs >= MAX_CLONES - 4 then return end
        local b = accepted_buildings[i]
        if b.depth == 1 and (i % 2) == 0 then
            local curb_distance = (b.parcel_depth * 0.5) + 145
            local px = b.x - b.outward_x * curb_distance
            local pz = b.z - b.outward_z * curb_distance
            local template = nil
            if (b.hash % 5) == 0 then template = t.planter
            elseif (b.hash % 7) == 0 then template = t.trash
            else template = t.lamp end
            if template ~= nil and prop_clear(scan, template, px, pz, b.yaw) then
                queue_piece(template, px, terrain_height(px, pz, b.y), pz, b.yaw, 100, false)
            end
        end
    end

    for i = 1, #alley_anchors do
        if #jobs >= MAX_CLONES - 3 then return end
        local a = alley_anchors[i]
        local clutter = ((i % 2) == 0) and (t.bottles or t.paper1) or (t.paper2 or t.trash)
        if clutter ~= nil then
            local px = a.anchor_x + a.outward_x * 520
            local pz = a.anchor_z + a.outward_z * 520
            if prop_clear(scan, clutter, px, pz, a.yaw) then
                queue_piece(clutter, px, terrain_height(px, pz, a.y), pz, a.yaw, 100, false)
            end
        end
    end
end

local function plan_generation()
    status = "scanning modular kit"
    local scan = scan_level()
    if scan == nil then return false end

    status = "zoning parcels"
    collect_parcels(scan)
    if #accepted_buildings == 0 then status = "no valid parcels"; return false end

    status = "assembling buildings"
    table.sort(accepted_buildings, function(a, b)
        if a.depth == b.depth then return a.hash < b.hash end
        return a.depth < b.depth
    end)

    for i = 1, #accepted_buildings do
        if #jobs >= MAX_CLONES - 12 then break end
        plan_building(scan, accepted_buildings[i])
    end
    plan_street_life(scan)

    stats.planned = #jobs
    if #jobs == 0 then status = "assembly produced zero jobs"; return false end
    status = "building 0/" .. tostring(#jobs)
    return true
end

local function spawn_job(job)
    if SpawnNewEntity == nil then last_error = "SpawnNewEntity unavailable"; return false end
    local ok, newe = pcall(SpawnNewEntity, job.template)
    if not ok or newe == nil or newe <= 0 then
        stats.failed = stats.failed + 1
        last_error = "SpawnNewEntity failed at job " .. tostring(job_index)
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
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_READY"] = 1
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_CLONES"] = stats.clones
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_BUILDINGS"] = stats.buildings
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_MODULAR"] = stats.modular
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_TOWERS"] = stats.towers
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_FLOORS"] = stats.floors
        g_UserGlobal["BLACK_SIGNAL_CITY_V3_ALLEYS"] = stats.alleys
    end
end

function bs_city_v3.init()
    generated = false
    init_time = g_Time or 0
    spawned = {}
    jobs = {}
    job_index = 1
    status = "waiting"
    last_error = ""
    accepted_buildings = {}
    alley_anchors = {}
    stats = {
        roads = 0, templates = 0, parcels = 0, buildings = 0, modular = 0, towers = 0,
        floors = 0, alleys = 0, clones = 0, planned = 0, failed = 0,
        rejected_road = 0, rejected_overlap = 0, rejected_terrain = 0
    }
end

function bs_city_v3.main()
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
    status = "building " .. tostring(job_index - 1) .. "/" .. tostring(#jobs)
    return false
end

function bs_city_v3.get_status()
    return status, stats.clones, stats.roads, stats.templates, stats.buildings, stats.modular,
        stats.towers, stats.floors, stats.alleys, stats.rejected_road,
        stats.rejected_overlap, stats.rejected_terrain, last_error
end

function bs_city_v3.quit()
    spawned = {}
    jobs = {}
    accepted_buildings = {}
    alley_anchors = {}
    job_index = 1
    generated = false
end

function bs_city_v3_init(e)
    bs_city_v3.init()
end

function bs_city_v3_main(e)
    bs_city_v3.main()
end

return bs_city_v3
