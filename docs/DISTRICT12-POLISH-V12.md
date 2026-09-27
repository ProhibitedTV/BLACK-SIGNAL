# Manual-baseline city polish

This pass starts from the user's saved, 9,009-entity level in `gameguru/references/District 12 - manual polish.fpm`. It does not regenerate the roads, blocks or building shells. The user's moved shops, ATM, added markings/lights, overhang and two tents remain the reference. The previous experimental crowd candidates were never deployed over that work.

## V12.1 grouped-baseline safety rule

The manual reference contains native GameGuru MAX v319 editor-group metadata in the first ELE entity record. The exact meaning of MAX's opaque group item IDs is not guessed or rewritten by BLACK SIGNAL tooling.

For this grouped baseline, V12.1 therefore uses an **append-only source-preservation strategy**:

- every source ELE record remains at exactly the same record index;
- every source ELE record, including the first record containing the native group table, is preserved byte-for-byte;
- source entities are not deleted, replaced, moved or rescaled by the automated V12 pass;
- new V12 entities are appended only after the complete manual baseline;
- candidate validation verifies source record order, source record hashes, byte identity, group count and the absence of a second group table in appended records;
- deployment remains fail-closed and occurs only after candidate validation succeeds.

This deliberately trades a few cosmetic automated corrections for map integrity. Traffic-signal reduction, automated road-stud grounding/deduplication, replicated storefront/ATM offsets, approach-marking changes and the automated upper-doorway replacement are recorded as skipped proposals on a grouped baseline rather than physically rewriting source records. Those edits can be revisited later only after native group remapping semantics are proven or after the user performs/captures them safely in MAX.

The exporter still copies all untouched entity records byte for byte. A manifest names every proposed or intentional change. Player/global metadata, terrain and archive members other than the entity streams and explicit lighting settings are preserved. A deployment guard refuses to overwrite project-map changes newer than the captured baseline or last applied receipt.

## Incremental additions

V12 adds new work after the preserved baseline rather than rewriting grouped source records:

- Add 216 unarmed civilian extras: 144 walkers on independently checked sidewalk loops, 66 ground-level shoppers/bystanders and six upper-gallery residents. The existing city's props and the new stairs/tents are route obstacles.
- Add six selected side galleries. Two canopy bays and measured deck blocks form each upper floor, 200 units above the pavement. Twenty solid steps have a 10-unit rise and 20-unit tread; railings protect the stairs and gallery edge. Placement uses existing kit meshes with recorded scale transforms; the road network remains untouched.
- Add two small, sheltered tent clusters beneath selected galleries, four tents total, alongside the user's original two. This detail is concentrated rather than repeated on every block.
- Add six elevated neon accents and twelve practical light sources around the hero areas. Exposure changes from 1 to 1.18, contrast from about 1.167 to 1.07, and environment-probe brightness from 1 to 1.15. Fog begins at 3,000 and reaches its configured distance at 16,000 units to give the far city more separation. These are restrained starting settings for native review, not a claim of finished lighting.
- Add six curbside puddles and two mid-block utility vehicles. The usable installed road-vehicle family is limited; this is not a diverse traffic fleet or moving-traffic implementation.

## Build and apply

Generate and validate a candidate without changing the production map:

```powershell
./tools/build-district12-polish-v12.ps1
```

After reviewing the candidate workflow, close GameGuru MAX before applying:

```powershell
./tools/build-district12-polish-v12.ps1 -Deploy
```

With `-Candidate <path>`, the helper validates an existing export and its route sidecar. The deployment path backs up maps, lists and behavior scripts, then copies matching FPM, dependency list and pedestrian route scripts to curated, project and global locations. New manual edits must be captured and reviewed before rebuilding; the old v11 deployment entry point is blocked once this baseline exists.

The city-polish measurement table records mesh bounds and FPE profile scale. The staircase uses the known flat roof-block top and bottom, rather than the overall height of a railing or open prop. The template library preserves original material payloads from installed example levels. No commercial mesh/texture files are added to curated source by the V12 authoring pipeline.

## Acceptance boundary

Automated checks cover grouped-baseline byte identity, source-index stability, locked road/crosswalk geometry, saved transforms, supported steps/gallery heights, unique civilian bindings, sidewalk route containment, obstacle clearance, route/FPM agreement and complete encrypted archive traversal. The actual Lua behavior is exercised by the existing test suite, including stalled frames and missing animation clips.

Native visual and performance acceptance is still required. Inspect the manually edited block first, then stairs and handrails, pedestrian foot contact/animation speed, tent placement, lighting and the two parked vehicles. Collision-disabled extras are cinematic background actors and cannot be pushed into roads; they are not interactive NPCs. This is a bounded polish pass, not completion of every aspiration in `CITY-POLISH-BRIEF.md`: extensive facade/material replacement, moving traffic, weather/steam effects and hardware performance qualification remain future work.
