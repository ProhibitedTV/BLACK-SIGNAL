# District 12 — Street Detail Pass

`DETAIL V1` runs after modular `CITY V3` reaches `ready`. Its job is to turn the generated district from architecture into a believable street environment without putting furniture in roads or inside buildings.

## Placement rules

1. Authored Cyberpunk Streets road meshes remain hard no-build zones.
2. Authored sidewalk meshes provide the placement frame for curb furniture.
3. The nearest road determines which side of a sidewalk is the curb side and which is the building/outer side.
4. Rails, parking posts/bollards, fireplugs and similar protection pieces stay on the curb side.
5. Benches, bus stops, planters, lamps and ATMs stay on the outer/pedestrian side so the sidewalk center remains readable.
6. CITY V3 buildings are rescanned after construction and treated as blockers.
7. Service props are placed behind building masses relative to the nearest road, never randomly in front of the facade.
8. All detail uses oriented collision footprints and terrain checks before being accepted.
9. Detail spawning is incremental to avoid the one-frame freeze seen in the early dense-city prototypes.

## Current always-available seed assets

District 12 already contains exemplars for:

- `cs_street_lamp`
- `cs_planter_01`
- `cs_trash_can`
- `cs_bottle_can_cluster_01`
- `cs_newspaper_01`
- `cs_newspaper_02`

These are enough for DETAIL V1 to add curb rhythm, planter/lamp variation, service clutter and lived-in debris immediately.

## Optional Cyberpunk Streets detail families

The Cyber City Streets DLC contains substantially more street furniture than the current District 12 level has seeded. DETAIL V1 recognizes these automatically when at least one exemplar is present in the level:

- parking posts / bollards
- pedestrian rails / parking barriers
- `CS_Bench`
- `CS_Bus_Stop`
- `CS_ATM`
- `CS_Dumpster_Closed`
- `CS_Fireplug`
- `CS_AirCon_01` and `CS_AirCon_01_Stand`
- cardboard / box clutter
- newspaper clusters

The runtime intentionally discovers parking-post and rail assets semantically (`parking + post`, `bollard`, `rail`, or `parking + barrier`) rather than depending on one exact filename. That makes the project tolerant of small DLC filename changes.

## Why an exemplar is required

GameGuru MAX's Lua `SpawnNewEntity(currente)` API clones an entity already loaded into the level; it does not load an arbitrary `.fpe` by path at runtime. Therefore optional detail assets need one seed instance in the FPM before Lua can clone them.

The seed object can live outside the filming area. Once it exists in `BLACK SIGNAL - District 12.fpm`, DETAIL V1 finds its entity path during startup and uses it wherever the placement rules permit.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\audit-cyberpunk-detail-assets.ps1
```

The audit searches the installed Cyberpunk Streets pack for relevant detail assets and tells you which families are already referenced by District 12.

## Runtime sequence

```text
CITY V3
  road network
      -> parcels
      -> modular buildings
      -> alleys / second-row mass
      -> ready

DETAIL V1
  rescan finished city
      -> sidewalks
      -> curb protection
      -> pedestrian furniture
      -> service edges
      -> debris / litter
      -> ready
```

## Diagnostics

During the pass the lower-screen diagnostic reports counts similar to:

```text
BLACK SIGNAL DETAIL V1 | building details 84/190 | clones 78 | sidewalks 41 | rail 8 | posts 14 | benches 3 | stops 1 | lamps 20 | planters 11 | service 6 | clutter 15
```

If `rail 0` or `posts 0` while the city otherwise dresses correctly, the likely cause is simply that the FPM does not yet contain a rail or parking-post exemplar. That is an asset-seeding issue, not a generator failure.
