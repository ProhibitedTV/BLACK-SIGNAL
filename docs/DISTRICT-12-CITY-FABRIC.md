# District 12 lived-in city fabric

`gameguru/Files/scriptbank/user/black_signal/bs_city_fabric.lua` is the near/midground complement to `bs_city_runtime.lua`.

The skyline runtime makes District 12 feel large. The city-fabric runtime makes the playable/filmable district feel **occupied, layered and urban** before cinematic-specific dressing begins.

## What it generates

At level startup the script scans the original entities already authored into `BLACK SIGNAL - District 12.fpm`, infers the dominant road axis from the Cyberpunk Streets road pieces, and builds deterministic urban fabric around that axis:

- continuous street-wall/frontage rows on both sides of the dominant road;
- storefront variation using the Cyberpunk Streets storefront pieces already present in the map;
- neon storefront accents at restrained intervals;
- deliberate frontage gaps that read as alley mouths;
- four short side-street/service-corridor wings branching from the main road;
- secondary service-edge wall runs;
- low/mid-rise massing behind street walls;
- curb dressing using street lamps, planters, trash cans, bottle/can clusters and newspapers.

The generator uses a fixed seed so the layout is identical between film takes.

## Asset policy

No marketplace/DLC binaries are copied into Git. The runtime only clones entity templates that already exist in the loaded District 12 map via GameGuru MAX `SpawnNewEntity`.

The current fabric recognizes these Cyberpunk Streets assets when present:

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
- `cs_bg_building_01_*`
- `cs_bg_building_03_*`

These are already referenced by the District 12 dependency list; the script does not add or redistribute the underlying pack.

## Runtime boundaries

The fabric generator has its own clone ceiling (`MAX_CLONES = 460`) and is separate from the skyline shell (`bs_city_runtime.lua`). Near architecture keeps collision and shadows where useful; small dressing props and generated background massing favor performance.

The project-local `gameloop.lua` runs the fabric generator before the skyline generator. Both are gated to `BLACK SIGNAL - District 12`.

Published debug counters in `g_UserGlobal`:

- `BLACK_SIGNAL_FABRIC_CLONES`
- `BLACK_SIGNAL_FABRIC_ARCHITECTURE`
- `BLACK_SIGNAL_FABRIC_STOREFRONTS`
- `BLACK_SIGNAL_FABRIC_PROPS`
- `BLACK_SIGNAL_FABRIC_ALLEYS`
- `BLACK_SIGNAL_FABRIC_SIDE_STREETS`
- `BLACK_SIGNAL_CITY_CLONES` (skyline runtime)

## Production intent

This system is **base-city dressing**, not final shot dressing. It should provide useful streets, alley mouths, block faces, storefront rhythm and urban clutter so the environment reads as a futuristic district from ordinary player/camera height.

Cinematic hero areas should still be hand-art-directed in MAX. When a generated object conflicts with a planned shot, prefer changing the generator's layout rules or reserving that camera corridor rather than permanently baking the entire procedural city into the FPM.
