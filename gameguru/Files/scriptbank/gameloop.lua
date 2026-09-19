-- DESCRIPTION: BLACK SIGNAL project gameloop. Preserves stock MAX player-health logic and adds District 12 city fabric and skyline expansion.

module_cameraoverride = require "scriptbank\\ai\\module_cameraoverride"

local fabric_ok, bs_city_fabric = pcall(require, "scriptbank\\user\\black_signal\\bs_city_fabric")
local city_ok, bs_city_runtime = pcall(require, "scriptbank\\user\\black_signal\\bs_city_runtime")

gameloop_RegenTickTime = 0

local gameloop = {}

function gameloop.init()
    gameloop_RegenTickTime = 0

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
                    if newHealth > g_gameloop_StartHealth then
                        newHealth = g_gameloop_StartHealth
                    end
                    SetPlayerHealth(newHealth)
                end
            end
        end
    end

    -- Generate the near/midground urban fabric first: storefronts, street walls,
    -- side-street channels, alley mouths and lived-in curb dressing.
    if fabric_ok and bs_city_fabric ~= nil and bs_city_fabric.main ~= nil then
        bs_city_fabric.main()
    end

    -- Then extend the skyline outside the authored district. Both modules are
    -- level-gated and only run for BLACK SIGNAL - District 12.
    if city_ok and bs_city_runtime ~= nil and bs_city_runtime.main ~= nil then
        bs_city_runtime.main()
    end
end

function gameloop.quit()
    if city_ok and bs_city_runtime ~= nil and bs_city_runtime.quit ~= nil then
        bs_city_runtime.quit()
    end
    if fabric_ok and bs_city_fabric ~= nil and bs_city_fabric.quit ~= nil then
        bs_city_fabric.quit()
    end
    module_cameraoverride.restoreandreset()
end

return gameloop
