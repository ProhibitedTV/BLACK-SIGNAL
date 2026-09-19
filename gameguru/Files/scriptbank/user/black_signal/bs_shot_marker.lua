-- DESCRIPTION: BLACK SIGNAL virtual-production shot marker.
-- DESCRIPTION: [SHOT_ID$="SHOT-001"]
-- DESCRIPTION: [TAKE=1(1,99)]
-- DESCRIPTION: [ENABLED!=1]

-- This behavior intentionally contains no undocumented engine or CineGuru calls.
-- It provides per-entity production metadata and verifies the repo -> GameGuru
-- MAX custom-behavior pipeline.

g_bs_shot_marker = {}

function bs_shot_marker_properties(e, shot_id, take, enabled)
    if g_bs_shot_marker[e] == nil then
        g_bs_shot_marker[e] = {}
    end

    g_bs_shot_marker[e].shot_id = shot_id
    g_bs_shot_marker[e].take = take
    g_bs_shot_marker[e].enabled = enabled
end

function bs_shot_marker_init(e)
    if g_bs_shot_marker[e] == nil then
        g_bs_shot_marker[e] = {}
    end

    -- Defaults are only applied when MAX has not already supplied editor values.
    if g_bs_shot_marker[e].shot_id == nil then
        g_bs_shot_marker[e].shot_id = "SHOT-001"
    end
    if g_bs_shot_marker[e].take == nil then
        g_bs_shot_marker[e].take = 1
    end
    if g_bs_shot_marker[e].enabled == nil then
        g_bs_shot_marker[e].enabled = 1
    end
end

function bs_shot_marker_main(e)
    -- Metadata-only behavior by design. CineGuru owns cinematic execution.
end
