# BLACK SIGNAL

**BLACK SIGNAL** is a cyberpunk short film produced primarily inside **GameGuru MAX**, using the engine as a virtual production stage rather than as the final gameplay experience.

## Logline

A municipal systems technician enters an evacuated district that is still consuming power. The streets are empty, but the city behaves as if its residents are still there—and the deeper she goes, the more the infrastructure appears to remember her before she arrived.

## Format

- Short film / proof of concept
- Target runtime: 10–20 minutes
- Primary production environment: GameGuru MAX
- Style: atmospheric science-fiction thriller with cyberpunk production design
- Priority: cinematography, sound, environment, tension, and story over gameplay systems

## Core idea

The district was managed by an experimental municipal AI trained on traffic cameras, microphones, smart-home telemetry, purchases, utility usage, and public infrastructure. After the population was evacuated, the system continued modeling the people it had observed.

It did not understand that they were gone.

The city is not haunted. It is being remembered.

## Visual rule

This is not a generic rainy-neon cyberpunk city. The primary visual concept is:

> A city at 7:43 AM after something impossible happened at 3:17 AM.

Cold morning haze, empty infrastructure, distant machinery, active advertising, long sightlines, sparse human presence, and small impossible details.

## Production philosophy

Build only what the camera needs. Reuse sets aggressively through lighting, signage, lensing, fog, camera placement, and dressing.

The first production target is the opening sequence: **CURRENT POPULATION: ZERO**.

## District 12 city stage

The canonical exterior virtual-production set is **District 12**, based on a duplicate of the existing editable `CyberCity.fpm` map and redressed with the available Cityscape, Future, Scifi, and custom Building Editor assets.

Production documentation:

- `film/production/CITY-STAGE.md`
- `gameguru/maps/README.md`
- `tools/import-city-stage.bat`

The importer copies the local `CyberCity.fpm` into the repository as `BLACK SIGNAL - District 12.fpm` without overwriting the original and stages the map for Git LFS.

See also:

- `film/CONCEPT.md`
- `film/screenplay/OPENING.md`
- `film/shotlists/OPENING.md`
