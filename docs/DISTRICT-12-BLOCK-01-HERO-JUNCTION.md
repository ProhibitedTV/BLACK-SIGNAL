# District 12 Block 01 — Hero Junction

This is the first production blockout for the authored District 12 city.

The goal is to turn the current sparse intersection into a believable cyberpunk city canyon using the Cyber City Streets kit as designed: snap-built roads and pavements, complete modular building shells, deliberate storefronts and overhangs, curb furniture with rhythm, and background towers only beyond the playable blocks.

## Coordinate convention

Use the center of the existing four-way intersection as the local origin.

```text
             NORTH (+Z)
                 ^
                 |
       NW block  |  NE block
                 |
WEST (-X) -------+------- EAST (+X)
                 |
       SW block  |  SE block
                 |
                 v
             SOUTH (-Z)
```

This document uses **snap bays**, not guessed world-unit coordinates. A bay means one native structural module width in GameGuru MAX. All structural pieces remain at 100% scale and use orthogonal rotations.

## Non-negotiable geometry rules

- Roads own the carriageway. No building or prop crosses the road-module footprint.
- Sidewalks form a continuous pedestrian band around every hero block.
- Building shells start behind the sidewalk band.
- Building corners use actual corner modules; do not overlap straight wall pieces to fake corners.
- A building owns its parcel. Neighboring shells never intersect or share the same occupied bay.
- Reserve at least one full snap bay between rear building faces where a service alley is intended.
- Ground-floor entrances face a sidewalk, not another building or bare terrain.
- Structural rotation follows the street axis: 0/90/180/270 only.
- Background-building assets never occupy the four hero blocks.
- Raw hillside/trees must not be visible through gaps between the four hero blocks from the intersection camera.

## Phase 1 — Finish the intersection and pavement datum

Keep the current four-way road as the visual anchor. Extend the road only in whole road modules.

Around the intersection:

1. Use `CS_Sidewalk_Corner1_DropCurb` at each pedestrian corner.
2. Continue with `CS_Sidewalk_Straight_Edge` along the curb.
3. Fill the walkable interior with `CS_Sidewalk_Tile_4x4` and smaller matching tiles where needed.
4. Keep every drop curb and crossing mouth clear of furniture.
5. Use the road-marking/decal family only after the road and sidewalk geometry is final.

The finished junction should read clearly even with every building hidden.

## Phase 2 — Four hero parcels

The first city canyon is four authored buildings surrounding the junction.

### NW — Vale Exchange

**Purpose:** mixed-use commercial block; establishes the human-scale street wall.

- Footprint: about **6 bays along the main avenue × 4 bays deep**.
- Height: **6 floors**.
- Ground floor: storefront/window rhythm with one primary entry near the intersection side.
- Floors 2–5: alternating window-wall and solid-wall modules.
- Floor 6: quieter facade with fewer illuminated accents.
- Overhang: continuous illuminated overhang above the ground floor on the two street-facing elevations.
- Roof: complete roof-tile cap; rooftop detail later.
- Rear: blank/service-heavy wall facing a reserved alley.

Suggested structural family:

- `CS_Wall_Corner_01`
- `CS_Wall_01`
- `CS_Walls_01_Window_With_Bars`
- `CS_Wall_01_Entry_01`
- `CS_Wall_01_Overhang`
- `CS_Wall_01_Overhang_Corner`
- `CS_Roof_Tile_4x4`
- `CS_Roof_Tile_2x2`
- `CS_Store_Front_02_Corner_With_Window`

### NE — Municipal Annex

**Purpose:** taller civic/commercial mass; gives the intersection a dominant face without becoming a background skyscraper.

- Footprint: about **5 × 5 bays**.
- Height: **8 floors**.
- Ground floor: more solid than the NW block, with one formal entry and restrained storefront treatment.
- Floors 2–6: regular vertical window rhythm.
- Floor 7: one-bay setback on the road-facing sides if the kit snaps cleanly at that footprint.
- Floor 8: compact upper level.
- Roof: complete cap.
- Accent: one neon storefront corner or illuminated overhang at the intersection-facing corner, not on every floor.

Suggested additional piece:

- `CS_Store_Front_02_Corner_Neon_Opposite`

### SW — Service Works

**Purpose:** lower industrial/service mass that keeps the street from becoming four identical towers.

- Footprint: about **7 × 3 bays**.
- Height: **4 floors**.
- Ground floor: two service/entry moments separated by long solid wall runs.
- Upper floors: mostly solid wall with sparse barred windows.
- No full facade neon.
- Rear: service alley with trash/litter concentration.
- Roof: broad flat roof for later HVAC placement.

This block should be visually heavier and darker than the other three.

### SE — Signal House

**Purpose:** narrow vertical mixed-use building and the hero silhouette from the current screenshot direction.

- Footprint: about **4 × 4 bays**.
- Height: **10 floors**.
- Ground floor: one entry plus storefront corner toward the intersection.
- Floors 2–6: repeated modular window rhythm.
- Floors 7–10: reduce the footprint by one bay on the rear and one side if the snap geometry supports a clean setback.
- One illuminated overhang above the ground floor.
- Roof: complete cap; later receives antenna/signage/HVAC.

The building should feel tall because of proportion, not because it is a `CS_BG_Building_*` stack.

## Phase 3 — Street-wall spacing

The four buildings should create an intentional canyon without choking the street.

Use this section on both primary streets:

```text
building shell
outer furniture strip
CLEAR WALKING PATH
curb furniture strip
curb / sidewalk edge
================ ROAD ================
curb / sidewalk edge
curb furniture strip
CLEAR WALKING PATH
outer furniture strip
building shell
```

Do not place a planter, lamp, trash can, sign or other prop in the clear walking path.

## Phase 4 — Curb rhythm

Street furniture should repeat with a deliberate cadence instead of random scatter.

For a long straight frontage, use a pattern similar to:

```text
corner clear zone
lamp
2–3 bays clear
planter / guard
2 bays clear
lamp
2–3 bays clear
planter / guard
entry clear zone
```

Current District 12 dependencies already include:

- `CS_Street_Lamp`
- `CS_Planter_01`
- `CS_Trash_Can`
- `CS_Bottle_Can_Cluster_01`
- `CS_Newspaper_01`
- `CS_Newspaper_02`

Rules:

- Lamps belong in the curb strip and line up along a frontage.
- Planters belong outside the clear path.
- Trash cans cluster near entries, transit points, or service zones.
- Bottles/newspapers belong in service alleys and a few curb pockets, never uniformly across every sidewalk.
- Keep all intersection corners and drop curbs clear.

## Phase 5 — Secondary mass to kill the valley look

The four hero buildings are not enough. The visible hills must be screened by a second urban layer.

Behind each hero block, add one simplified secondary structure:

- NW rear: 8–10 floors
- NE rear: 10–12 floors
- SW rear: 6–8 floors
- SE rear: 12–14 floors

These structures may use simpler modular facades because they are not approached as closely, but they still belong to valid parcels and must not overlap the hero shells or roads.

Leave intentional alley/service gaps between the hero and secondary structures.

## Phase 6 — Background skyline ring

Only after the hero and secondary blocks exist should the background-building families be used.

Use `CS_BG_Building_01_*`, `CS_BG_Building_03_*`, and `CS_BG_Building_04_*` beyond the playable blocks to:

- cover exposed hillside gaps,
- create depth behind secondary blocks,
- close the horizon,
- vary distant height.

Do not place them directly on the junction, sidewalk, or first row of parcels.

A good hierarchy from the intersection is:

```text
hero street wall:       4–10 floors
secondary urban mass:   6–14 floors
background skyline:    14+ floor visual mass
```

## Phase 7 — What to remove or relocate from the current scene

The current view still exposes large raw dirt shoulders and tree-covered slopes immediately beside the city. As Block 01 is built:

- cover urban-core dirt with pavement/road/block geometry,
- occlude the nearest hill cuts with secondary buildings or retaining/service architecture,
- keep trees beyond the urban perimeter,
- move any background-building stack that currently acts as a hero street building outward into the skyline band.

## Visual acceptance test

Block 01 is ready for the next district expansion only when all of these are true from the intersection:

- no building intersects the road,
- no two building shells overlap,
- all four corners have continuous sidewalk geometry,
- every hero building reads as a complete shell,
- at least three hero buildings have visibly different height/massing,
- entrances face usable sidewalks,
- curb furniture follows a repeatable rhythm,
- there is at least one intentional service alley,
- raw terrain is no longer visible through the center of the urban block composition,
- background buildings read as skyline depth rather than playable architecture.

## Build order inside MAX

Do not dress while the massing is still wrong.

1. Save a new FPM revision.
2. Finish the intersection road/pavement geometry.
3. Block the four hero parcel footprints with corners/walls only.
4. Walk the junction and confirm no road/sidewalk intrusion.
5. Build all four shells to full height.
6. Add roofs.
7. Add ground-floor entries/storefronts.
8. Add overhangs and facade accents.
9. Add second-row urban mass.
10. Add background skyline.
11. Only then add lamps/planters/trash/litter.
12. Run Test Play from the same screenshot position.
13. Sync the revised FPM/LST back to the repo.

The first target is not maximum density. It is a **coherent, collision-free, snap-built intersection that looks like a real piece of District 12**. Once this junction works, repeat the same parcel/street grammar outward instead of inventing a new layout system for every block.
