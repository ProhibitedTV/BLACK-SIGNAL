# BLACK SIGNAL — Native GameGuru MAX Flag Patrol Capture

## Why this exists

District 12's current generated civilian routes use coordinate lists. Native MAX review showed that approach does not behave like an editor-authored pedestrian patrol: walkers can appear to take only a few feet of motion and then visibly reset.

GameGuru MAX's stock `npc_control.lua` uses the editor relationship graph instead. A character begins in `flag_pathing`, scans its relationship slots with `GetEntityRelationshipID`, recognizes Flag markers with `GetEntityMarkerMode(...) == 11`, and then follows connected Flags. MAX uses its own pathfinding/movement stack between those linked markers.

We will not guess the serialized relationship format. The v316 ELE record contains seven relationship-header integers, two floats, and ten relationship slots (one float plus three integers per slot), but those raw values must be mapped to real editor semantics from a native MAX save.

## Golden-reference capture

Do this in a **copy** of District 12 or a tiny disposable calibration map. Do not use the production FPM as the experiment.

1. Open GameGuru MAX.
2. Place one normal human character on a broad, flat sidewalk.
3. Assign the stock `npc_control.lua` behavior to that character.
4. Place four Flag markers in a simple, obvious line with large spacing, for example roughly 300–500 units apart.
5. In Visual Logic, connect:
   - Character -> Flag A
   - Flag A -> Flag B
   - Flag B -> Flag C
   - Flag C -> Flag D
6. Do **not** close the chain back to Flag A for the first capture.
7. Save the map as a new FPM.
8. Run the map in MAX and verify the character actually walks the full flag chain in native gameplay.
9. Keep both files:
   - the unmodified baseline copy;
   - the MAX-saved copy containing the native character/flag relationships.

If the character does not traverse the native four-flag chain correctly, stop there. The reference is not valid evidence for automation yet.

## Analyze the capture

From the repository root:

```powershell
python .\tools\fpm_analyze_relationships.py `
  "C:\path\to\baseline.fpm" `
  "C:\path\to\native-flag-reference.fpm" `
  --report-json .\build\native-flag-relationship-diff.json
```

The analyzer is read-only. It reports:

- appended/new entities;
- their names, assets, scripts, and transforms;
- raw v316 relationship-header values;
- raw v316 relationship slot values and IDs;
- which existing records changed when Visual Logic links were saved.

For a clean reference we expect the differences to be tightly bounded to the character, the four Flag entities, and relationship metadata associated with those objects.

## Evidence we need before generating patrols

Do not implement automatic Flag graphs until the capture establishes all of the following:

1. the exact Flag asset/profile used by MAX;
2. which raw v316 field corresponds to the marker/relationship behavior we care about;
3. which of the three per-slot integer IDs maps to the linked entity/unique element/relationship role;
4. how MAX serializes Character -> Flag versus Flag -> Flag;
5. whether link direction is stored on one side or both sides;
6. whether unique-element IDs must be non-zero and globally unique;
7. whether Visual Logic creates or updates any data outside `map.ele`;
8. whether copied Flag records remain valid when appended to the grouped District 12 baseline;
9. whether elevated Flags successfully extend/reach navigation on galleries, rooftops, and skybridges.

## Production rollout after semantics are proven

The intended District 12 pedestrian architecture is:

```text
BS_EXTRA_001 -> BS_FLAG_001_A -> BS_FLAG_001_B -> BS_FLAG_001_C -> BS_FLAG_001_D
BS_EXTRA_002 -> BS_FLAG_002_A -> BS_FLAG_002_B -> ...
```

The generator should author sparse, native flag graphs on validated sidewalk corridors and let MAX own character navigation between flags. It should not teleport or directly transform character objects from Lua.

Rollout order:

1. one ground-level native patrol;
2. one entire city block;
3. several ground-level blocks;
4. one elevated gallery route;
5. one skybridge route;
6. rooftop routes only after native review proves nav coverage is reliable.

Native GameGuru MAX review remains the acceptance boundary at every stage.
