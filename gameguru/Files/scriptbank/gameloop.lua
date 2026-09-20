-- DESCRIPTION: BLACK SIGNAL film runtime. District 12 geometry is authored in the FPM with the Cyberpunk Streets snap kit; this loop intentionally does not spawn, move, scale, or dress city geometry at runtime.

module_cameraoverride = require "scriptbank\\ai\\module_cameraoverride"

gameloop_RegenTickTime = 0

local gameloop = {}
local runtime_started = false
local runtime_start_time = 0

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

    if g_UserGlobal ~= nil then
        -- Hook version 8 marks the authored/snap-driven city reset. Physical
        -- District 12 geometry now belongs in the saved FPM, not runtime cloning.
        g_UserGlobal["BLACK_SIGNAL_RUNTIME_HOOK"] = 8
        g_UserGlobal["BLACK_SIGNAL_AUTHORED_CITY"] = 1
        g_UserGlobal["BLACK_SIGNAL_RUNTIME_GEOMETRY"] = 0
    end
end

local function optional_debug_prompt()
    if Prompt == nil or g_UserGlobal == nil then return end
    if g_UserGlobal["BLACK_SIGNAL_DEBUG_RUNTIME"] ~= 1 then return end
    if (g_Time or 0) > runtime_start_time + 4000 then return end
    Prompt("BLACK SIGNAL | authored District 12 | runtime geometry disabled")
end

function gameloop.init()
    gameloop_RegenTickTime = 0
    runtime_started = false
    runtime_start_time = g_Time or 0
end

function gameloop.main()
    -- Preserve the stock GameGuru MAX player-health regeneration behaviour.
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

    if not is_black_signal_level() then return end
    start_black_signal_runtime()
    optional_debug_prompt()
end

function gameloop.quit()
    runtime_started = false
    module_cameraoverride.restoreandreset()
end

return gameloop
