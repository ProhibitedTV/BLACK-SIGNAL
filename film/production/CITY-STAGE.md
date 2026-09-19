# BLACK SIGNAL — District 12 City Stage

## Purpose

District 12 is the reusable exterior city set for BLACK SIGNAL. It is a virtual production backlot, not a complete open-world level. Every block exists to serve specific camera angles, blocking, and story beats.

The production target is a dense, empty near-future district at 07:43: cold morning haze, active infrastructure, long sightlines, and almost no people.

## Base map

Use the existing editable GameGuru MAX map:

`Documents\GameGuruApps\GameGuruMAX\Files\mapbank\CyberCity.fpm`

Do **not** edit the original. Duplicate it as the film stage:

`BLACK SIGNAL - District 12.fpm`

The companion `CyberCity.lst` should be copied alongside the film-stage map when useful.

## Stage layout

### A — Arrival Boulevard

The opening establishing set.

- broad road corridor
- strong vanishing point
- future towers as background silhouettes
- overpass crossing frame at mid-distance
- sparse streetlights
- billboard / advert surfaces
- one traffic signal or crossing point that can behave strangely
- enough empty foreground for a slow push or lateral dolly

Primary assets:

- Cityscape road material
- Mega Pack 01 Future `buildingblock1`–`buildingblock4`
- Mega Pack 01 Future `tower1`–`tower3`
- `OVERPASS1`, `OVERPASS2`
- `CASUALSTREETLAMP`, `FUNKY_STREETLIGHT`
- future advert-sign materials

### B — Service Canyon

A compressed industrial street used for walking coverage and unease.

- narrow road / service lane
- concrete buildings close to camera
- scaffolding and pipes
- vents, AC equipment, cables
- isolated practical lights
- dumpsters / barrels / barriers as foreground occluders

Primary assets:

- Cityscape `Concrete_building`, `Concrete_building_2`
- `Metal_strut`
- scaffold / warehouse / wire-pole materials
- Mega Pack Future pillar, vents, AC unit
- CityscapePBR concrete barriers, walls, cylinders, girders
- Scifi Pack cables and power boxes

### C — Municipal Plaza

The district's civic face. Cleaner, wider, more controlled than the service canyon.

- one hero building or HQ facade
- wide pedestrian space
- industrial tower or observation structure
- symmetry that feels deliberately artificial
- room for a locked-off wide shot with no visible humans

Potential hero geometry:

- user Building Editor `HQ`
- `Building1` / `BuildingOne`
- Future building blocks and towers
- Scifi Pack observation towers

### D — Underpass / Utility Threshold

Transition space between public city and infrastructure.

- overpass underside
- barriers and damaged concrete
- cables and exposed utilities
- radio / power hardware
- deep shadow with bright exterior background

This set can redress into multiple locations by moving only foreground props and changing light.

### E — Skyline Card

Background-only geometry. It never needs to be traversable.

- towers placed to create depth layers
- silhouettes hidden by haze
- repeating structures allowed if rotation and spacing vary
- no detail where the camera cannot resolve it

## Asset families already available locally

### Cityscape / CityscapePBR

Use these for the physical city language: roads, concrete, warehouse forms, bridge pieces, barriers, damaged walls, scaffolding, poles, and industrial clutter.

### Mega Pack 01 — Future

Use these for the high-level cyberpunk read: modular future building blocks, overpasses, towers, streetlights, advert signs, industrial tower, pillars, vents, and AC units.

### Scifi Pack

Use selectively for technology dressing rather than the whole architecture: observation towers, radio towers, cables, power boxes, monitors, holo furniture, drones, and utility pieces.

### User Building Editor

Use the existing custom building-editor structures where they help give the city unique hero buildings instead of a pure asset-pack look.

## Cinematography rules

1. Build for the frame, not for navigation.
2. Maintain at least three depth layers in exterior wides: foreground occluder, midground architecture, hazy skyline.
3. Keep one recognizable landmark visible from multiple angles to imply geographic continuity.
4. Reuse the same block aggressively by changing lens, camera height, signage, fog, and practical lighting.
5. Favor 35–65 mm-equivalent compositions over ultra-wide game-camera framing.
6. Empty space is intentional. The city should look operational but depopulated.
7. Avoid defaulting to constant rain. Morning haze and dry reflective surfaces are the baseline look.

## First five required shots

1. **District wide** — empty boulevard, skyline disappearing into blue haze.
2. **Traffic behavior** — signal changes for an empty crossing.
3. **Long-lens compression** — towers, overpass, and signage stacked into one frame.
4. **Technician arrival** — protagonist enters a frame that has been empty long enough to feel wrong.
5. **Impossible billboard** — advert briefly displays `I KNOW YOU'RE THERE` before returning to normal.

If these five shots work, the city stage is production-ready enough to continue the opening sequence.

## Production acceptance criteria

District 12 is ready for principal virtual photography when:

- the duplicated film-stage map opens independently of `CyberCity.fpm`
- the boulevard, service canyon, plaza, and utility threshold can each produce at least two distinct camera setups
- no required opening shot exposes unfinished geometry
- skyline repetition is hidden by composition and atmosphere
- the protagonist can be blocked through the exterior route without needing game logic
- a clean 1080p or higher capture can be made from all five required opening shots
