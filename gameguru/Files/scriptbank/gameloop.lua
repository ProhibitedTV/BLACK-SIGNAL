-- DESCRIPTION: BLACK SIGNAL runtime-aware gameloop. Preserves stock MAX player-health logic and builds District 12 through the modular parcel-based CITY V3 generator.

module_cameraoverride = require "scriptbank\\ai\\module_cameraoverride"

local cityv3_ok, cityv3_result = pcall(require, "scriptbank\\user\\black_signal\\bs_city_v3")
local bs_city_v3 = nil
local cityv3_load_error = ""
if cityv3_ok then
    bs_city_v3 = cityv3_result
else
    cityv3_load_error = tostring(cityv3_result)
end

gameloop_RegenTickTime = 0

local gameloop = {}
local runtime_started = false
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
    runtime_start_time = g_Time or 0
    runtime_ready_time = 0
    runtime_error = ""

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_RUNTIME_HOOK"] = 4
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

local function show_runtime_status()
    if Prompt == nil then return end
    local now = g_Time or 0

    if runtime_error ~= "" then
        Prompt("BLACK SIGNAL CITY V3 ERROR: " .. runtime_error)
        return
    end

    if bs_city_v3 ~= nil and bs_city_v3.get_status ~= nil then
        local ok, state, clones, roads, templates, buildings, modular, towers, floors, alleys, reject_road, reject_overlap, reject_terrain, err = pcall(bs_city_v3.get_status)
        if ok then
            if tostring(state) == "ready" then
                if runtime_ready_time == 0 then runtime_ready_time = now end
                if now > runtime_ready_time + 5000 then return end
            elseif now > runtime_start_time + 45000 then
                return
            end

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
    end
end

function gameloop.init()
    gameloop_RegenTickTime = 0
    runtime_started = false
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

    if cityv3_ok and bs_city_v3 ~= nil and bs_city_v3.main ~= nil and runtime_error == "" then
        local ok, err = pcall(bs_city_v3.main)
        if not ok then runtime_error = tostring(err) end
    end

    show_runtime_status()
end

function gameloop.quit()
    if runtime_started and bs_city_v3 ~= nil and bs_city_v3.quit ~= nil then
        pcall(bs_city_v3.quit)
    end

    runtime_started = false
    runtime_ready_time = 0
    runtime_error = ""
    module_cameraoverride.restoreandreset()
end

return gameloop
