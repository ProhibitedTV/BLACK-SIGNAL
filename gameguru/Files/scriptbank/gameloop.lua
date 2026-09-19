-- DESCRIPTION: BLACK SIGNAL runtime-aware gameloop. Preserves stock MAX player-health logic and conditionally builds District 12 from the normal GameGuru scriptbank path.

module_cameraoverride = require "scriptbank\\ai\\module_cameraoverride"

local basin_ok, bs_basin_city = pcall(require, "scriptbank\\user\\black_signal\\bs_basin_city")
local fabric_ok, bs_city_fabric = pcall(require, "scriptbank\\user\\black_signal\\bs_city_fabric")
local city_ok, bs_city_runtime = pcall(require, "scriptbank\\user\\black_signal\\bs_city_runtime")

gameloop_RegenTickTime = 0

local gameloop = {}
local runtime_started = false

local function lower(value)
    if value == nil then return "" end
    return string.lower(tostring(value))
end

local function is_black_signal_level()
    -- GameGuru MAX exposes the active level through g_LevelFilename. Keep this
    -- hook safe in the default user Files tree by doing absolutely nothing for
    -- unrelated projects/levels.
    local level = lower(g_LevelFilename or "")
    if level == "" then return false end
    if string.find(level, "district 12", 1, true) ~= nil then return true end
    if string.find(level, "black signal", 1, true) ~= nil then return true end
    return false
end

local function start_black_signal_runtime()
    if runtime_started then return end
    runtime_started = true

    if g_UserGlobal ~= nil then
        g_UserGlobal["BLACK_SIGNAL_RUNTIME_HOOK"] = 1
    end

    if basin_ok and bs_basin_city ~= nil and bs_basin_city.init ~= nil then
        bs_basin_city.init()
    end
    if fabric_ok and bs_city_fabric ~= nil and bs_city_fabric.init ~= nil then
        bs_city_fabric.init()
    end
    if city_ok and bs_city_runtime ~= nil and bs_city_runtime.init ~= nil then
        bs_city_runtime.init()
    end
end

function gameloop.init()
    gameloop_RegenTickTime = 0
    runtime_started = false
end

function gameloop.main()
    -- Stock GameGuru MAX player health regeneration behaviour.
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

    -- g_LevelFilename may not be populated when GameLoopInit fires, so bootstrap
    -- the project runtime lazily from the first frame where the level identity is
    -- known. This also makes the same hook safe for unrelated GameGuru projects.
    start_black_signal_runtime()

    -- First fill the visible valley itself. This is the pass that turns the
    -- sparse three-building scene into contiguous city blocks and masks terrain.
    if basin_ok and bs_basin_city ~= nil and bs_basin_city.main ~= nil then
        bs_basin_city.main()
    end

    -- Add storefronts, alley mouths, service edges and curb-level residue.
    if (g_Time or 0) >= 850 then
        if fabric_ok and bs_city_fabric ~= nil and bs_city_fabric.main ~= nil then
            bs_city_fabric.main()
        end
    end

    -- Finish with the broader skyline/parallax shell.
    if (g_Time or 0) >= 1150 then
        if city_ok and bs_city_runtime ~= nil and bs_city_runtime.main ~= nil then
            bs_city_runtime.main()
        end
    end
end

function gameloop.quit()
    if runtime_started then
        if city_ok and bs_city_runtime ~= nil and bs_city_runtime.quit ~= nil then
            bs_city_runtime.quit()
        end
        if fabric_ok and bs_city_fabric ~= nil and bs_city_fabric.quit ~= nil then
            bs_city_fabric.quit()
        end
        if basin_ok and bs_basin_city ~= nil and bs_basin_city.quit ~= nil then
            bs_basin_city.quit()
        end
    end

    runtime_started = false
    module_cameraoverride.restoreandreset()
end

return gameloop
