-- DESCRIPTION: BLACK SIGNAL runtime-aware gameloop. Preserves stock MAX player-health logic, builds District 12 through CITY V3, then runs street DETAIL V1 and architectural ARCH V1 dressing passes.

module_cameraoverride = require "scriptbank\\ai\\module_cameraoverride"

local cityv3_ok, cityv3_result = pcall(require, "scriptbank\\user\\black_signal\\bs_city_v3")
local bs_city_v3 = nil
local cityv3_load_error = ""
if cityv3_ok then
    bs_city_v3 = cityv3_result
else
    cityv3_load_error = tostring(cityv3_result)
end

local details_ok, details_result = pcall(require, "scriptbank\\user\\black_signal\\bs_city_details")
local bs_city_details = nil
local details_load_error = ""
if details_ok then
    bs_city_details = details_result
else
    details_load_error = tostring(details_result)
end

local arch_ok, arch_result = pcall(require, "scriptbank\\user\\black_signal\\bs_city_arch_dressing")
local bs_city_arch_dressing = nil
local arch_load_error = ""
if arch_ok then
    bs_city_arch_dressing = arch_result
else
    arch_load_error = tostring(arch_result)
end

gameloop_RegenTickTime = 0

local gameloop = {}
local runtime_started = false
local details_started = false
local arch_started = false
local runtime_start_time = 0
local runtime_ready_time = 0
local runtime_error = ""

local function lower(value)
    if value == nil then return "" end
    return string.lower(tostring(value))
end

local function is_black_signal_level()
    local level = lower(g_LevelFilename or "")
    if level == "" then return false end
    if string.find(level, "district 12", 1, true) ~= nil then return true end
    if string.find(level, "black signal", 1, true) ~= nil then return true end
    return false
end

local function start_black_signal_runtime()
    if runtime_started then return end
    runtime_started = true
    details_started = false
    arch_started = false
    runtime_start_time = g_Time or 0
    runtime_ready_time = 0
    runtime_error = ""

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_RUNTIME_HOOK"] = 6
    end

    if cityv3_ok and bs_city_v3 ~= nil and bs_city_v3.init ~= nil then
        local ok, err = pcall(bs_city_v3.init)
        if not ok then runtime_error = tostring(err) end
    elseif cityv3_load_error ~= "" then
        runtime_error = cityv3_load_error
    else
        runtime_error = "bs_city_v3 module did not load"
    end
end

local function start_detail_runtime()
    if details_started then return end
    details_started = true
    runtime_ready_time = 0

    if details_ok and bs_city_details ~= nil and bs_city_details.init ~= nil then
        local ok, err = pcall(bs_city_details.init)
        if not ok then runtime_error = tostring(err) end
    elseif details_load_error ~= "" then
        runtime_error = details_load_error
    else
        runtime_error = "bs_city_details module did not load"
    end
end

local function start_arch_runtime()
    if arch_started then return end
    arch_started = true
    runtime_ready_time = 0

    if arch_ok and bs_city_arch_dressing ~= nil and bs_city_arch_dressing.init ~= nil then
        local ok, err = pcall(bs_city_arch_dressing.init)
        if not ok then runtime_error = tostring(err) end
    elseif arch_load_error ~= "" then
        runtime_error = arch_load_error
    else
        runtime_error = "bs_city_arch_dressing module did not load"
    end
end

local function show_city_status(now)
    if bs_city_v3 == nil or bs_city_v3.get_status == nil then return end
    local ok, state, clones, roads, templates, buildings, modular, towers, floors, alleys, reject_road, reject_overlap, reject_terrain, err = pcall(bs_city_v3.get_status)
    if not ok then return end
    if now > runtime_start_time + 45000 and tostring(state) ~= "ready" then return end

    local message = "BLACK SIGNAL CITY V3 | " .. tostring(state) ..
        " | clones " .. tostring(clones or 0) ..
        " | buildings " .. tostring(buildings or 0) ..
        " | modular " .. tostring(modular or 0) ..
        " | towers " .. tostring(towers or 0) ..
        " | floors " .. tostring(floors or 0) ..
        " | alleys " .. tostring(alleys or 0) ..
        " | roads " .. tostring(roads or 0)
    if tostring(state) == "ready" then
        message = message ..
            " | reject road " .. tostring(reject_road or 0) ..
            " overlap " .. tostring(reject_overlap or 0) ..
            " terrain " .. tostring(reject_terrain or 0)
    end
    if err ~= nil and tostring(err) ~= "" then message = message .. " | " .. tostring(err) end
    Prompt(message)
end

local function show_detail_status(now)
    if bs_city_details == nil or bs_city_details.get_status == nil then return end
    local ok, state, clones, roads, sidewalks, templates, rails, posts, benches, stops, lamps, planters, service, clutter, reject_road, reject_overlap, reject_terrain, err = pcall(bs_city_details.get_status)
    if not ok then return end

    if tostring(state) == "ready" then
        if runtime_ready_time == 0 then runtime_ready_time = now end
        if now > runtime_ready_time + 3500 then return end
    elseif now > runtime_start_time + 60000 then
        return
    end

    local message = "BLACK SIGNAL DETAIL V1 | " .. tostring(state) ..
        " | clones " .. tostring(clones or 0) ..
        " | sidewalks " .. tostring(sidewalks or 0) ..
        " | rail " .. tostring(rails or 0) ..
        " | posts " .. tostring(posts or 0) ..
        " | benches " .. tostring(benches or 0) ..
        " | stops " .. tostring(stops or 0) ..
        " | lamps " .. tostring(lamps or 0) ..
        " | planters " .. tostring(planters or 0) ..
        " | service " .. tostring(service or 0) ..
        " | clutter " .. tostring(clutter or 0)
    if tostring(state) == "ready" then
        message = message ..
            " | reject road " .. tostring(reject_road or 0) ..
            " overlap " .. tostring(reject_overlap or 0) ..
            " terrain " .. tostring(reject_terrain or 0)
    end
    if err ~= nil and tostring(err) ~= "" then message = message .. " | " .. tostring(err) end
    Prompt(message)
end

local function show_arch_status(now)
    if bs_city_arch_dressing == nil or bs_city_arch_dressing.get_status == nil then return end
    local ok, state, clones, templates, anchors, signs, fireescapes, rooftop, emissives, err = pcall(bs_city_arch_dressing.get_status)
    if not ok then return end

    if tostring(state) == "ready" then
        if runtime_ready_time == 0 then runtime_ready_time = now end
        if now > runtime_ready_time + 6000 then return end
    elseif now > runtime_start_time + 75000 then
        return
    end

    local message = "BLACK SIGNAL ARCH V1 | " .. tostring(state) ..
        " | clones " .. tostring(clones or 0) ..
        " | templates " .. tostring(templates or 0) ..
        " | anchors " .. tostring(anchors or 0) ..
        " | signs " .. tostring(signs or 0) ..
        " | escapes " .. tostring(fireescapes or 0) ..
        " | rooftop " .. tostring(rooftop or 0) ..
        " | emissive " .. tostring(emissives or 0)
    if err ~= nil and tostring(err) ~= "" then message = message .. " | " .. tostring(err) end
    Prompt(message)
end

local function show_runtime_status()
    if Prompt == nil then return end
    local now = g_Time or 0

    if runtime_error ~= "" then
        Prompt("BLACK SIGNAL RUNTIME ERROR: " .. runtime_error)
        return
    end

    if arch_started then
        show_arch_status(now)
    elseif details_started then
        show_detail_status(now)
    else
        show_city_status(now)
    end
end

function gameloop.init()
    gameloop_RegenTickTime = 0
    runtime_started = false
    details_started = false
    arch_started = false
    runtime_start_time = g_Time or 0
    runtime_ready_time = 0
    runtime_error = ""
end

function gameloop.main()
    if g_PlayerHealth > 0 and g_PlayerHealth < g_gameloop_StartHealth and g_PlayerDeadTime == 0 then
        if g_PlayerLastHitTime > 0 then
            if g_Time > g_PlayerLastHitTime + g_gameloop_RegenDelay then
                if g_Time > gameloop_RegenTickTime then
                    gameloop_RegenTickTime = g_Time + g_gameloop_RegenSpeed
                    newHealth = g_PlayerHealth + g_gameloop_RegenRate
                    if newHealth > g_gameloop_StartHealth then newHealth = g_gameloop_StartHealth end
                    SetPlayerHealth(newHealth)
                end
            end
        end
    end

    if not is_black_signal_level() then
        if Prompt ~= nil and (g_Time or 0) < 7000 then
            Prompt("BLACK SIGNAL HOOK ACTIVE | level='" .. tostring(g_LevelFilename or "") .. "'")
        end
        return
    end

    start_black_signal_runtime()

    local city_ready = false
    if cityv3_ok and bs_city_v3 ~= nil and bs_city_v3.main ~= nil and runtime_error == "" then
        local ok, result = pcall(bs_city_v3.main)
        if not ok then runtime_error = tostring(result)
        else city_ready = (result == true) end
    end

    if city_ready and runtime_error == "" then
        start_detail_runtime()
    end

    local details_ready = false
    if details_started and details_ok and bs_city_details ~= nil and bs_city_details.main ~= nil and runtime_error == "" then
        local ok, result = pcall(bs_city_details.main)
        if not ok then runtime_error = tostring(result)
        else details_ready = (result == true) end
    end

    if details_ready and runtime_error == "" then
        start_arch_runtime()
    end

    if arch_started and arch_ok and bs_city_arch_dressing ~= nil and bs_city_arch_dressing.main ~= nil and runtime_error == "" then
        local ok, err = pcall(bs_city_arch_dressing.main)
        if not ok then runtime_error = tostring(err) end
    end

    show_runtime_status()
end

function gameloop.quit()
    if arch_started and bs_city_arch_dressing ~= nil and bs_city_arch_dressing.quit ~= nil then
        pcall(bs_city_arch_dressing.quit)
    end
    if details_started and bs_city_details ~= nil and bs_city_details.quit ~= nil then
        pcall(bs_city_details.quit)
    end
    if runtime_started and bs_city_v3 ~= nil and bs_city_v3.quit ~= nil then
        pcall(bs_city_v3.quit)
    end

    runtime_started = false
    details_started = false
    arch_started = false
    runtime_ready_time = 0
    runtime_error = ""
    module_cameraoverride.restoreandreset()
end

return gameloop
