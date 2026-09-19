# District 12 — Modular CITY V3

CITY V3 replaces the earlier strategy of cloning complete towers beside the road. The generator now treats the existing Cyberpunk Streets road network as zoning input, creates collision-safe parcels beside those roads, and assembles varied buildings from the modular pieces already loaded by the District 12 map.

## Design goals

1. **Roads are sacred.** No generated parcel may overlap an authored road footprint.
2. **One parcel, one building envelope.** Accepted parcel footprints are reserved before any geometry is spawned, so two generated buildings cannot occupy the same space.
3. **Use the pack as a kit, not a bag of prefabs.** Street-facing buildings combine background-building cores with modular walls, windows, entries, overhangs, corners and roof tiles.
4. **Height is procedural.** Building archetypes control floor count, podium scale, tower scale and facade depth instead of selecting a single finished tower mesh.
5. **Urban depth is deliberate.** Frontage buildings form the street wall; a second row of taller cores can sit behind a reserved service/alley gap.
6. **Intersections and curves remain open.** Only straight authored road pieces generate frontage parcels. Intersection and curved-road meshes still participate in collision tests, keeping corners and bends clear.
7. **Terrain matters.** The center and all four parcel corners are sampled against terrain. Parcels spanning steep grade changes are rejected.
8. **Runtime construction stays incremental.** Geometry is spawned a few pieces per frame so GameGuru MAX remains responsive during Test Play.

## Assets used

CITY V3 discovers exemplars already present in `BLACK SIGNAL - District 12.fpm` and clones only those existing entity templates.

### Background building cores

- `cs_bg_building_01_base(.fpe)` / `base2` / `floor` / `floor_between` / `top`
- `cs_bg_building_03_base` / `floor` / `top`
- `cs_bg_building_04_base` / `base2` / `floor` / `top`

These provide closed building mass, emissive variation and efficient vertical stacking.

### Modular facade / roof kit

- `cs_wall_01`
- `cs_walls_01_window_with_bars`
- `cs_wall_corner_01`
- `cs_wall_01_entry_01`
- `cs_wall_01_entry_04`
- `cs_wall_01_overhang`
- `cs_wall_01_overhang_corner`
- `cs_roof_tile_2x2`
- `cs_roof_tile_4x4`
- `cs_store_front_02_corner_with_window`
- `cs_store_front_02_corner_neon_opposite`

The modular pieces are measured at runtime from `GetEntityColBox`, so facade bay spacing follows the actual asset dimensions rather than a guessed constant.

### Street-life kit

- `cs_street_lamp`
- `cs_planter_01`
- `cs_trash_can`
- `cs_bottle_can_cluster_01`
- `cs_newspaper_01`
- `cs_newspaper_02`

Street-life pieces are attached to accepted frontage parcels and reserved alley mouths instead of being scattered globally.

## Building grammar

Each valid parcel receives one of six deterministic archetypes:

| Archetype | Typical height | Character |
| --- | ---: | --- |
| `shopblock` | 4–6 floors | broad lower commercial block with entries and more facade treatment |
| `midrise` | 7–10 floors | mixed-use street wall with a smaller upper mass |
| `slab` | 8–12 floors | wider urban slab with overhang bands |
| `industrial` | 5–7 floors | heavier, broader podium and restrained facade rhythm |
| `needle` | 12–18 floors | narrow vertical tower with a smaller upper core |
| `corporate` | 15–22 floors | tall background/corporate mass with restrained street treatment |

A building is assembled in layers:

```text
roof / cap
upper tower core (reduced scale)
transition floor / setback
podium core
modular street facade
entry / window / neon / overhang rhythm
sidewalk buffer
ROAD
```

The lower podium defines the parcel envelope. Upper sections may scale down, but they never expand beyond the reserved footprint.

## Placement algorithm

For each straight road entity CITY V3:

1. Reads the road's actual oriented collision footprint.
2. Detects the long axis and side-normal from the mesh bounds and rotation.
3. Selects a deterministic building archetype and background-core kit.
4. Measures the chosen kit and facade module to derive a conservative parcel width/depth.
5. Positions the parcel outside the road footprint plus a sidewalk buffer.
6. Rejects the parcel if its oriented footprint intersects:
   - any authored road,
   - any existing authored building,
   - any previously accepted generated parcel,
   - the player-start clearance zone,
   - terrain with excessive slope/spread.
7. If blocked, retries only **farther away from the road**.
8. Reserves occasional frontage gaps as alley/service mouths.
9. Optionally places a taller second-row tower beyond a real alley/service gap.
10. Converts accepted buildings into an incremental spawn job queue.

## Why this is different from CITY V2

CITY V2 proved runtime generation and collision-safe parcels, but its output was still essentially a collection of complete tower prefabs. CITY V3 separates **urban planning** from **building grammar**:

- road -> parcel
- parcel -> archetype
- archetype -> core massing
- core -> facade modules
- facade -> street detail

This gives District 12 substantially more silhouette variation while preserving the fundamental rule that buildings cannot occupy roads or overlap one another.

## Runtime limits

Current safeguards:

- maximum generated pieces: **850**
- maximum accepted generated buildings: **28**
- spawn budget: **4 pieces/frame**
- deterministic layout from authored geometry and position hashes

These are production defaults, not artistic limits. Increase them only after a representative Test Play remains stable.

## Film workflow

CITY V3 is still a background/midground city system, not a substitute for art direction. Once its urban fabric is convincing:

- keep CITY V3 for district scale and parallax,
- replace or redress hero storefronts by hand,
- add CineGuru cameras/actors only after the environment reads correctly,
- manually art-direct the few alleys, intersections and rooftops that appear in close shots.
