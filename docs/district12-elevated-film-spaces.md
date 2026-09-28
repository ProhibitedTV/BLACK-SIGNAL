# District 12 elevated filming spaces

This pass adds a small set of repeatable vertical stages for BLACK SIGNAL episodic production. The intent is to make District 12 read as a layered city rather than a flat street grid while keeping the existing road network and grouped manual baseline untouched.

## Second-tier exterior galleries

Four tall hero buildings receive an additional east-side exterior gallery at roughly two storeys above street level:

- Block-02-01
- Block-06-01
- Block-04-03
- Block-03-04

The original V12 west-side gallery remains at the lower level. The new gallery is mirrored to the opposite facade so the building reads as layered from multiple street angles and so the existing upper-resident staging is not obstructed.

Good uses:

- surveillance dialogue
- a character watching activity below
- two-level cross-cut conversations
- sniper / lookout framing without needing a rooftop
- foreground rail silhouettes against the street canyon

## Skybridges

Two narrow elevated crossings are authored at +600 relative to street level:

- Block-02-03 to Block-03-03
- Block-04-04 to Block-05-04

Each bridge is exactly five measured 200-unit deck sections across a saved 1000-unit facade gap. The ends meet the two saved building planes exactly; there are no guessed world-space offsets.

Good uses:

- conversations suspended above moving street action
- long-lens shots down the street through railings
- pursuit beats
- isolated silhouette shots in fog
- characters observing a plaza or intersection below
- transitions between episodes or locations without leaving District 12

## Rooftop terraces

Four roofs receive restrained perimeter rails and practical light pools:

- Block-04-01
- Block-02-04
- Block-03-05
- Block-05-04

The south edge of each terrace deliberately leaves a broad camera gap instead of enclosing the entire roof. This gives CineGuru/free-camera setups a clean entrance for wide shots and keeps the terrace useful as a virtual-production stage rather than a gameplay cage.

Good uses:

- private dialogue scenes
- skyline establishing shots
- antenna / surveillance scenes
- emergency-response staging
- sunrise or storm coverage
- episode-end reveals

## Visual grammar

These spaces should remain part of the BLACK SIGNAL 07:43 look:

- cold gray ambient morning
- localized practical pools rather than universal brightness
- sparse neon accents below and around the elevated geometry
- fog used to separate vertical layers
- wet streets visible beneath elevated camera positions
- strong foreground rail / bridge silhouettes

Do not add elevated structures to every block. Their value comes from being recognizable locations with different visual identities.

## Safety / authoring rules

- The grouped 9,009-record manual baseline remains append-only and byte/index stable.
- No road geometry is changed.
- New decks and bridges use measured Cyberpunk Streets asset dimensions.
- Skybridge endpoints must meet saved facade planes exactly.
- Rooftop rail Y positions are derived from saved floor counts.
- Any asset/profile change that invalidates those relationships should fail the build rather than place floating geometry.
- Native GameGuru MAX review is still required for visual acceptance.
