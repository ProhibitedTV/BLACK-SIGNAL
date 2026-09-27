# Manual-baseline city polish

This pass starts from the user's saved, 9,009-entity level in `gameguru/references/District 12 - manual polish.fpm`. It does not regenerate the roads, blocks or building shells. The user's moved shops, ATM, added markings/lights, overhang and two tents remain the reference. The previous experimental crowd candidates were never deployed over that work.

The exporter copies untouched entity records byte for byte. A manifest names every intentional change. All road segments, crosswalk records and newly hand-authored records are protected and checked against the saved source. Player/global metadata, terrain and archive members other than the entity streams and explicit lighting settings are preserved. A deployment guard refuses to overwrite project-map changes newer than the captured baseline or last applied receipt.

## Incremental changes

- Apply the demonstrated storefront and ATM offsets to corresponding unedited placements. Retain individually authored examples exactly.
- Apply the user's approach-arrow and center-line cadence to matching approach markings, leaving crosswalks intact.
- Correct the previous interpretation of `CS_Street_Light_Marker`: these are visible road studs, not point-light sources. Ground the remaining misplaced instances on road centers and deduplicate shared road segments.
- Reduce 100 repeated traffic-signal poles to 50. Preserve the existing 215-unit asset height, consistent with the measured building/character scale.
- Add 216 unarmed civilian extras: 144 walkers on independently checked sidewalk loops, 66 ground-level shoppers/bystanders and six upper-gallery residents. The existing city's props and the new stairs/tents are route obstacles.
- Add six selected side galleries. Two canopy bays and measured deck blocks form each upper floor, 200 units above the pavement. Twenty solid steps have a 10-unit rise and 20-unit tread; railings protect the stairs and gallery edge. Six upper doorways connect them visually to the buildings. Placement uses existing kit meshes with recorded scale transforms; the road network remains untouched.
- Add two small, sheltered tent clusters beneath selected galleries, four tents total, alongside the user's original two. This detail is concentrated rather than repeated on every block.
- Add six elevated neon accents and twelve practical light sources around the hero areas. Exposure changes from 1 to 1.18, contrast from about 1.167 to 1.07, and environment-probe brightness from 1 to 1.15. Fog begins at 3,000 and reaches its configured distance at 16,000 units to give the far city more separation. These are restrained starting settings for native review, not a claim of finished lighting.
- Add six curbside puddles and two mid-block utility vehicles. The usable installed road-vehicle family is limited; this is not a diverse traffic fleet or moving-traffic implementation.

## Build and apply

```powershell
./tools/build-district12-polish-v12.ps1 -Deploy
```

Without `-Deploy`, it creates and validates a separate candidate. With `-Candidate <path>`, it validates an existing export and its route sidecar. Close MAX before applying. The helper backs up maps, lists and behavior scripts, then copies matching FPM, dependency list and pedestrian route scripts to curated, project and global locations. New manual edits must be captured and reviewed before rebuilding; the old v11 deployment entry point is blocked once this baseline exists.

The city-polish measurement table records mesh bounds and FPE profile scale. The staircase uses the known flat roof-block top and bottom, rather than the overall height of a railing or open prop. The template library preserves original material payloads from installed example levels. No commercial mesh/texture files are added to curated source.

## Acceptance boundary

Automated checks cover protected-record identity, locked road/crosswalk geometry, saved transforms, supported steps/gallery heights, unique civilian bindings, sidewalk route containment, obstacle clearance, route/FPM agreement and complete encrypted archive traversal. The actual Lua behavior is exercised in a ten-minute simulation, including stalled frames and missing animation clips.

Native visual and performance acceptance is still required. Inspect the manually edited block first, then stairs and handrails, pedestrian foot contact/animation speed, tent placement, lighting and the two parked vehicles. Collision-disabled extras are cinematic background actors and cannot be pushed into roads; they are not interactive NPCs. This is a bounded polish pass, not completion of every aspiration in `CITY-POLISH-BRIEF.md`: extensive facade/material replacement, moving traffic, weather/steam effects and hardware performance qualification remain future work.
