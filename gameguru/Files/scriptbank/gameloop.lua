-- DESCRIPTION: BLACK SIGNAL project gameloop. Preserves stock MAX player-health logic and builds the District 12 basin, street fabric and skyline.

module_cameraoverride = require "scriptbank\\ai\\module_cameraoverride"

local basin_ok, bs_basin_city = pcall(require, "scriptbank\\user\\black_signal\\bs_basin_city")
local fabric_ok, bs_city_fabric = pcall(require, "scriptbank\\user\\black_signal\\bs_city_fabric")
local city_ok, bs_city_runtime = pcall(require, "scriptbank\\user\\black_signal\\bs_city_runtime")

gameloop_RegenTickTime = 0

local gameloop = {}

function gameloop.init()
    gameloop_RegenTickTime = 0

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

    -- First fill the visible valley itself. This is the pass that turns the
    -- sparse three-building scene into contiguous city blocks and masks terrain.
    if basin_ok and bs_basin_city ~= nil and bs_basin_city.main ~= nil then
        bs_basin_city.main()
    end

    -- Keep the older authored-road fabric pass for extra storefronts, alleys and
    -- service-edge detail. It runs after the basin has established the big masses.
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
    if city_ok and bs_city_runtime ~= nil and bs_city_runtime.quit ~= nil then
        bs_city_runtime.quit()
    end
    if fabric_ok and bs_city_fabric ~= nil and bs_city_fabric.quit ~= nil then
        bs_city_fabric.quit()
    end
    if basin_ok and bs_basin_city ~= nil and bs_basin_city.quit ~= nil then
        bs_basin_city.quit()
    end
    module_cameraoverride.restoreandreset()
end

return gameloop
