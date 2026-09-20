# District 12 detail seed palette

The Cyberpunk Streets audit on the current GameGuru MAX install found 268 FPE assets. Runtime passes can only clone entities that are already loaded by the level, so optional DLC props still need one hidden exemplar in `BLACK SIGNAL - District 12.fpm` before runtime code can propagate them.

## Recommended first seed set

Place one exemplar of each of these outside the filming/play area and save the level:

1. `Misc\Sidewalk Misc\CS_Bench.fpe`
2. `Misc\General Misc\CS_Bus_Stop.fpe`
3. `Misc\General Misc\CS_Bus_Stop_Neon_Sign.fpe`
4. `Misc\General Misc\CS_ATM.fpe`
5. `Misc\General Misc\CS_ATM_Screen.fpe`
6. `Misc\General Misc\CS_Dumpster_Closed.fpe`
7. `Misc\Sidewalk Misc\CS_Fireplug.fpe`
8. `Misc\Building Misc\CS_AirCon_01.fpe`
9. `Misc\Building Misc\CS_AirCon_01_Stand.fpe`
10. `Misc\Building Misc\CS_AirCon_02.fpe`
11. `Misc\Building Misc\CS_AirCon_02_Stand.fpe`
12. `Misc\Building Misc\CS_Neon_01.fpe`
13. `Misc\Building Misc\CS_Neon_03.fpe`
14. `Misc\Building Misc\CS_Neon_05.fpe`
15. `Misc\Building Misc\CS_FireEscape_01.fpe`
16. `Misc\Building Misc\CS_FireEscape_02.fpe`
17. `Misc\Building Misc\CS_FireEscape_Ladder.fpe`
18. `Misc\Debris\CS_Box_01.fpe`
19. `Misc\Debris\CS_Box_02.fpe`
20. `Misc\Debris\CS_Cardboard.fpe`
21. `Misc\Debris\CS_Newspaper_Cluster.fpe`
22. `Streets and Sidewalks\Sidewalks\CS_Overpass_01.fpe`

The full neon family discovered by the audit also includes `CS_Neon_02`, `CS_Neon_04`, `CS_Neon_06`, `CS_Neon_07`, and `CS_Neon_Emitter`. Add them later if more sign variety is needed.

## Exact curb / sidewalk utility candidates

The broader installed-pack scan resolved the vague parking-post / rail request into real asset names. Seed these as the first CURB V1 palette:

1. `Misc\Sidewalk Misc\CS_Sidewalk_Guard.fpe` — pedestrian-protection / guard runs along the curb edge.
2. `Misc\Sidewalk Misc\CS_Plastic_Divider_1.fpe` — short parking/loading-edge dividers.
3. `Misc\Sidewalk Misc\CS_Sidewalk_Light.fpe` — dedicated sidewalk illumination on the outer pedestrian zone.
4. `Misc\Sidewalk Misc\CS_Sidewalk_Planter.fpe` — additional sidewalk greenery/furniture distinct from `CS_Planter_01`.
5. `Misc\Sidewalk Misc\CS_Street_Electrical_Pole_01.fpe` — sparse utility poles on long sidewalk runs.

The same scan found `CS_Street_Electrical_Pole_01_Wire.fpe` through `_Wire_05.fpe`. CURB V1 deliberately does **not** auto-place those wire meshes yet. Their origin and length need one visual verification pass first so wires do not slice through buildings or streets.

## Why hidden exemplars are required

`SpawnNewEntity` clones an entity element already loaded by the current level. Having an FPE somewhere in the commercial GameGuru install is not sufficient by itself. The exemplar can be placed far outside the camera/play area; its purpose is to make the asset available as a runtime template.

## Runtime use after seeding

- DETAIL V1: benches, bus stops, ATMs, dumpsters, fireplugs, basic street furniture, service clutter, boxes, cardboard and newspaper piles.
- CURB V1: exact sidewalk guards, plastic dividers, sidewalk lights, sidewalk planters and sparse electrical poles discovered by the installed-pack candidate scan. Placement follows the sidewalk axis and keeps curb-side and outer-pedestrian-side roles separate.
- ARCH V1: facade neon, fire escapes, rooftop HVAC, paired ATM/bus-stop emissive pieces and sparse architectural accents.
- `CS_Overpass_01` is discovered by ARCH V1 but is deliberately not auto-spawned until its scale/origin are visually verified in District 12. Large infrastructure should not be dropped blindly over a road.
