# District 12 authored-city workflow

District 12 is now built as an authored GameGuru MAX level, not as a runtime-generated city.

The Cyberpunk Streets pack is designed around snap-friendly construction:

- 16 background buildings for extending the city beyond the playable area
- 56 modular shop fronts and signs
- 57 modular road and pavement pieces plus road markings that snap together
- 69 modular building pieces including illuminated overhangs, walls, walkways, and tunnels
- 70 miscellaneous props including litter, air conditioners, ATM machines, street lights, and more

BLACK SIGNAL should use those categories according to their intended purpose instead of treating every asset as an interchangeable runtime prop.

## Current production target

The next authored construction pass is **Block 01 — Hero Junction**:

- build plan: `docs/DISTRICT-12-BLOCK-01-HERO-JUNCTION.md`
- machine-readable checklist: `gameguru/buildplans/district12/block-01-hero-junction.csv`
- readiness/checklist tool: `tools/show-district12-block01-plan.ps1`

Block 01 turns the current sparse four-way junction into the first finished District 12 city canyon with four distinct hero parcels, secondary urban mass, deliberate curb rhythm and a background skyline ring.

## Hard rules

1. **The FPM is the source of truth for physical city geometry.**
   Roads, sidewalks, buildings, skyline mass, street furniture, alleys and utility placement are saved into `BLACK SIGNAL - District 12.fpm`.

2. **No runtime city spawning.**
   `gameloop.lua` must not call `SpawnNewEntity` or invoke the retired CITY/DETAIL/CURB/ARCH generator stack.

3. **Snap first; do not eyeball structural modules.**
   Road, pavement, wall, corner, roof, overhang, walkway and storefront modules should stay on the MAX grid and use the pack's native dimensions.

4. **Structural pieces remain at 100% scale by default.**
   The pieces are authored to connect. Scaling a wall or road module breaks the kit grammar and should be exceptional, deliberate and visually verified.

5. **Rotations follow the street/grid.**
   Structural modules use orthogonal rotations unless a purpose-built curve or angled module is being used.

6. **Background buildings stay in the background.**
   `CS_BG_Building_*` families are skyline/perimeter mass. They should not be the playable street wall or occupy hero sidewalks/intersections.

7. **Playable buildings are complete modular shells.**
   A hero building should read as a whole structure: corners, street facade, side/rear walls, entries, upper floors, overhangs and a roof/cap. Do not glue a decorative facade to a background tower and call it finished.

8. **Street furniture follows urban rhythm.**
   Lights, guards, dividers, planters, benches, hydrants, poles and signs align to curb/sidewalk zones. They are not noise scattered around open space.

9. **Keep the carriageway and pedestrian path readable.**
   Buildings never intrude into road modules. Furniture never blocks the main sidewalk path. Intersections and drop curbs stay clear.

10. **Hide the terrain inside the urban core.**
    Raw hillsides, trees and dirt between hero buildings break the city illusion. Grade, pave, wall-off or occlude the center of District 12; let terrain read only beyond the constructed perimeter.

## Construction order

Build in this order so later passes inherit clean geometry:

1. District pad / terrain cleanup
2. Primary road network
3. Secondary streets / service lanes
4. Sidewalks, corners and drop curbs
5. Road markings / crosswalks
6. Playable block envelopes
7. Modular building shells
8. Shopfronts, entries and signs
9. Walkways / tunnels / overhangs
10. Rooftops and service equipment
11. Curb protection / street lights / planters / poles
12. Benches / ATMs / bus stops / dumpsters / litter
13. Background skyline ring
14. Lighting / emissive signs / animated advertising
15. CineGuru cameras, blocking and shot-specific polish

## Playable building grammar

Use the modular building kit to make repeated rules, not repeated buildings.

A typical mixed-use block can be assembled as:

```text
roof tile / rooftop equipment
wall + window modules
wall + window modules
illuminated overhang
shopfront | shopfront | entry | shopfront
sidewalk
curb furniture
road
```

Variation should come from authored choices such as:

- parcel width in whole module bays
- floor count
- corner treatment
- entry position
- storefront family
- overhang frequency
- window/blank-wall rhythm
- setbacks made from smaller upper footprints
- roof treatment
- signage
- rear/service treatment

Do not create variation by adding arbitrary position jitter, arbitrary scale or arbitrary rotation.

## Street section

A normal hero street should read approximately as:

```text
building facade
outer furniture zone: planter / bench / ATM / service door
clear pedestrian path
curb zone: light / guard / divider / hydrant / pole
curb
road lane / markings
median or opposing lane
curb
curb zone
clear pedestrian path
building facade
```

Keep long runs consistent. Break the rhythm intentionally at intersections, bus stops, loading/service areas, alleys and hero entrances.

## Skyline hierarchy

Use three depth bands:

### Hero/playable street

Mostly modular buildings built from the 69-piece building family and 56-piece storefront/sign family. These need complete geometry and believable street interfaces.

### Secondary urban mass

Larger but still authored structures one block behind the hero street. These can be simpler because they are rarely approached closely.

### Background skyline

Use the 16 background-building assets only here. Their job is to extend city depth, close horizon gaps and hide terrain—not to replace the modular playable city.

## Runtime responsibilities after this reset

Lua remains useful for things that actually belong at runtime:

- cinematic triggers
- shot metadata
- camera/actor glue
- animated advertisements or state changes
- environmental effects
- scripted lights
- six-second-delay story events
- municipal-system behavior

It should not construct the physical city during Test Play.

## Current authored kit already referenced by District 12

The level dependency list already includes representative pieces from the correct categories, including:

- `CS_Street_Straight_4x`
- `CS_Street_Straight_2x`
- `CS_Street_T-Intersect_3`
- `CS_Street_4_Way_2`
- `CS_Street_Curve_1`
- `CS_Sidewalk_Straight_Edge`
- `CS_Sidewalk_Corner1_DropCurb`
- `CS_Sidewalk_Tile_4x4`
- `CS_Wall_01`
- `CS_Wall_Corner_01`
- `CS_Walls_01_Window_With_Bars`
- `CS_Wall_01_Entry_01`
- `CS_Wall_01_Entry_04`
- `CS_Wall_01_Overhang`
- `CS_Wall_01_Overhang_Corner`
- `CS_Roof_Tile_2x2`
- `CS_Roof_Tile_4x4`
- Cyberpunk storefront corner modules
- background-building families 01, 03 and 04

The next map iterations should expand the authored city with more of the pack's native modular pieces inside MAX and commit the resulting FPM/LST changes through Git LFS.

## Legacy runtime generators

The old `bs_city_v3.lua`, `bs_city_details.lua`, `bs_curb_utilities.lua`, `bs_city_arch_dressing.lua` and earlier experiments remain in source history for reference. The active `gameloop.lua` deliberately does not require or call them.
