# District 12 city fabric

District 12 now uses three complementary BLACK SIGNAL runtime passes:

1. `bs_basin_city.lua` fills the visible valley with dense blocks and towers.
2. `bs_city_fabric.lua` adds storefront rhythm, alley mouths, service edges and curb-level dressing.
3. `bs_city_runtime.lua` adds the outer skyline/parallax belt.

The intent is that ordinary player/camera-height views read as a **city first**, not as a handful of buildings surrounded by terrain.

## Dense basin pass

`gameguru/Files/scriptbank/user/black_signal/bs_basin_city.lua` is the primary massing pass. It scans only original Cyberpunk Streets entities in the authored FPM, infers the dominant road axis, then fills the flat basin around that road with a deterministic urban grid.

It currently creates:

- six rows/bands of urban blocks around the main boulevard;
- repeated mid-rise masses built from `cs_bg_building_01_*` and `cs_bg_building_03_*` pieces;
- taller outer-band towers to mask the surrounding hills;
- three broad cross-street corridors through the block grid;
- secondary building masses inside most blocks so blocks contain internal alley/service gaps rather than one isolated building;
- continuous boulevard-facing facade strips using walls, barred windows, entries and storefront pieces;
- restrained neon storefront accents;
- lamps, planters, trash, bottles/cans and newspaper residue at street level;
- end-cap tower groups so long sightlines terminate in architecture instead of empty terrain.

The basin pass has a hard ceiling of `MAX_CLONES = 780`. Generated massing is non-destructive, collision-light film-stage geometry; hero interaction and cinematic collision should still be authored deliberately in MAX.

Published counters:

- `BLACK_SIGNAL_BASIN_READY`
- `BLACK_SIGNAL_BASIN_CLONES`
- `BLACK_SIGNAL_BASIN_BLOCKS`
- `BLACK_SIGNAL_BASIN_BUILDINGS`
- `BLACK_SIGNAL_BASIN_FACADES`
- `BLACK_SIGNAL_BASIN_PROPS`
- `BLACK_SIGNAL_BASIN_TOWERS`

## Lived-in fabric pass

`bs_city_fabric.lua` remains the near/midground detailing layer. It adds:

- street-wall/frontage rows;
- storefront variation;
- neon accents;
- deliberate alley mouths;
- short side-street/service-corridor wings;
- secondary service-edge wall runs;
- low/mid-rise massing behind street walls;
- curb dressing using street lamps, planters, trash cans, bottle/can clusters and newspapers.

Published counters:

- `BLACK_SIGNAL_FABRIC_CLONES`
- `BLACK_SIGNAL_FABRIC_ARCHITECTURE`
- `BLACK_SIGNAL_FABRIC_STOREFRONTS`
- `BLACK_SIGNAL_FABRIC_PROPS`
- `BLACK_SIGNAL_FABRIC_ALLEYS`
- `BLACK_SIGNAL_FABRIC_SIDE_STREETS`

## Skyline pass

`bs_city_runtime.lua` now places its tower belts much closer to the authored district than the original implementation. The old shell could begin several thousand GameGuru units beyond the sparse map and disappear behind the valley walls. The current rings begin just outside the authored architecture bounds and expand outward in three belts, providing visible tower mass and parallax before the terrain horizon.

Published counters:

- `BLACK_SIGNAL_CITY_READY`
- `BLACK_SIGNAL_CITY_CLONES`

## Asset policy

No marketplace/DLC binaries are copied into Git. Every generated object is cloned at runtime from entity templates already present in the loaded District 12 map via GameGuru MAX `SpawnNewEntity`.

The runtime recognizes existing Cyberpunk Streets assets including:

- `cs_bg_building_01_*`
- `cs_bg_building_03_*`
- `cs_wall_01`
- `cs_walls_01_window_with_bars`
- `cs_wall_01_entry_01`
- `cs_wall_corner_01`
- `cs_store_front_02_corner_with_window`
- `cs_store_front_02_corner_neon_opposite`
- `cs_street_lamp`
- `cs_planter_01`
- `cs_trash_can`
- `cs_bottle_can_cluster_01`
- `cs_newspaper_01`
- `cs_newspaper_02`

## Runtime activation

The BLACK SIGNAL `gameloop.lua` is deployed only into this project's Separate Project Folder. Because of that project-level isolation, the dense basin and skyline passes no longer depend on `g_LevelFilename` matching a particular Storyboard string. This avoids a fragile failure mode where the project was playable but procedural city generation silently did not run because the Storyboard reported a different level name.

Startup order is deliberately staggered:

1. basin fill begins first;
2. lived-in fabric begins after the main massing pass has started;
3. skyline belts begin last.

## Production intent

These systems create **base-city massing and lived-in texture**, not final cinematic set dressing. The goal is to make District 12 feel like a dense futuristic neighborhood before CineGuru shot construction begins.

Once the city reads correctly from ordinary street level, hero areas can be hand-art-directed for specific shots. Generated objects that interfere with a planned composition should be excluded/reserved by generator rules rather than baking the entire procedural city permanently into the `.fpm`.
