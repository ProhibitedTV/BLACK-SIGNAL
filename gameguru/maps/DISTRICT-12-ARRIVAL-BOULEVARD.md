# District 12 — Arrival Boulevard Blockout

This document is the source-of-truth for the first exterior filming zone in `BLACK SIGNAL - District 12.fpm`.

The production map already references the Cyberpunk Streets Booster Pack road, sidewalk, background-building, storefront, roof, debris, planter, crosswalk, lane-marking, and emissive-building families. The goal of this blockout is to turn that existing CyberCity-derived map into a repeatable virtual backlot rather than expand it into a gameplay city.

## Coordinate convention

Treat the chosen boulevard road centerline as local `Z+` for shot planning. The camera sits near the origin and looks toward positive Z. Exact GameGuru coordinates are intentionally assigned in-editor from the strongest existing road axis; this keeps the design independent of whatever absolute coordinates CyberCity currently uses.

## Zone A — Arrival Boulevard

### Road spine

Use an existing long straight Cyberpunk Streets road as the primary axis. Preserve at least one readable foreground crosswalk or lane marking. The boulevard should remain mostly empty so the road itself becomes a visual leading line.

Suggested visible order from camera to horizon:

1. foreground asphalt / crosswalk or directional arrow
2. sparse sidewalk furniture and debris
3. storefront-scale lower facades
4. mid-rise modular building walls and roofs
5. background-building stacks
6. one elevated structure crossing or touching the sightline
7. one dominant skyline anchor disappearing into haze

### Left street wall

Build a deliberately irregular edge rather than a perfect canyon.

- foreground: storefront / entry wall sections
- midground: modular wall, window, corner, and roof pieces
- background: stacked `cs_bg_building_*` base / floor / top modules
- one emissive cap or sign may remain active

Keep 1–2 gaps so the city feels larger than the set.

### Right street wall

Use a slightly heavier mass than the left side to create asymmetry.

- foreground: storefront corner or plain entry module
- midground: barred-window and plain wall sections
- upper silhouette: modular background-building stacks
- one recessed alley mouth should be preserved for later Service Canyon coverage

### Horizon anchor

Use one elevated bridge / overpass / tower form near the middle or far distance. It should interrupt the vanishing point without fully blocking it.

The horizon anchor is there for composition, not traversal.

### Street dressing

Use only props that sell scale and abandonment:

- planter
- newspaper
- bottle / can cluster
- occasional street furniture
- one active sign or emissive surface

Avoid prop spam. The opening should feel vacated, not destroyed.

## Camera station — SHOT 001

Place the first camera at approximate human eye height and near the boulevard centerline.

Starting target:

- camera height: 1.65–1.75 m equivalent
- FOV: 55° starting point
- pitch: level or slightly down, no heroic upward tilt
- roll: 0°
- composition: road occupies lower third and converges into a readable vanishing point
- movement: static for framing; optional extremely slow push after still-frame approval

The camera should see enough sky/haze to make upper silhouettes disappear gradually rather than clipping against a hard skyline.

## Atmosphere

Preserve the BLACK SIGNAL morning rule:

> A city at 07:43 after something impossible happened at 03:17.

- cool blue-gray haze
- restrained bloom
- desaturated surfaces
- no required rain
- active infrastructure despite the absence of people
- distant geometry lost progressively in fog

## Impossible detail

Use exactly one contradiction in Shot 001.

**Preferred:** an advert / emissive panel briefly changes to:

`I KNOW YOU'RE THERE`

Do not add a second supernatural cue to the same shot.

## Blocking acceptance criteria

Arrival Boulevard is considered blocked when the camera frame contains all of the following:

- long readable road axis
- foreground lane marking / crosswalk / arrow
- built street walls on both sides
- clear vertical scale from background building stacks
- elevated horizon structure
- single skyline anchor
- single active emissive / advert element
- no visible population
- sparse scale props
- deliberate negative space

## Production rule

Anything outside a planned camera frustum may remain unfinished.
