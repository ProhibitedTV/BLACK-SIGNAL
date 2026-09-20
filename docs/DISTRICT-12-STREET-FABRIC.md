# District 12 authored street fabric

District 12's streets are not considered visually complete when only road and sidewalk geometry exists. The following are baseline city infrastructure, not optional prop dressing:

- yellow center-road indication using `CS_Street_Double_Center_Line.fpe`;
- crosswalk decals at hero four-way junction approaches;
- physical `CS_Street_Lamp.fpe` meshes on a repeated curb rhythm;
- actual GameGuru MAX `CS_Street_Light_Marker.fpe` dynamic light entities paired with street lamps;
- `CS_Sidewalk_Light.fpe` low sidewalk lighting;
- `CS_Sidewalk_Guard.fpe` pedestrian/curb rails;
- `CS_Street_Crosswalk_Metal_Blocker_Post.fpe` as crossing pole stops / bollards;
- `CS_Street_Electrical_Pole_01.fpe` utility infrastructure;
- `CS_Plastic_Divider_1.fpe` only where a harder service/curb separator is useful.

The exact pack assets above were confirmed by the installed Cyber City Streets / Cyberpunk Streets Booster Pack scan. In particular, the pack includes `CS_Street_Light_Marker.fpe`; a lamp mesh by itself is not treated as a dynamic light.

## Authoring model

`tools/fpm_author_street_fabric.py` derives placements from the road entities already authored in the FPM and writes a separate generated FPM. It does not use runtime entity spawning.

For each required asset the writer uses this template policy:

1. exact placed record already in District 12;
2. otherwise an exact placed record harvested from a donor FPM with the same ELE version;
3. for ordinary static props only, an explicitly reported generic-static bank import may reuse a known-good static record while changing the `map.ent` bank reference.

The third path is a compatibility experiment and must be visually checked in MAX. It is never used for the dynamic light marker.

`CS_Street_Light_Marker.fpe` requires an exact same-version donor record when District 12 does not already contain one. This preserves the MAX-authored light fields instead of pretending that a generic prop record is a light.

## Deterministic layout

The first street-fabric pass follows a deliberately simple city rhythm:

```text
straight road
  -> yellow double center line on every module
  -> sidewalk lights on both sides
  -> full street lamps on both sides every second module
     -> one real dynamic light marker above each lamp
  -> curb guards on the lamp rhythm
  -> one utility pole every third module

four-way junction
  -> four crosswalk decals
  -> four crossing blocker posts / bollards
```

The current constants intentionally favor legibility over clutter. After the first generated FPM is visually validated, offsets and cadence can be tuned from screenshots without changing the file-format architecture.

## Safety rules

- Production `BLACK SIGNAL - District 12.fpm` is never overwritten by the authoring command.
- The source ELE stream must traverse exactly to EOF before any write.
- Raw entity records are cloned; the large versioned tail remains engine-authored.
- The generated FPM is reopened and fully parsed after writing.
- Only decrypted `map.ent` and `map.ele` are allowed to change.
- Dynamic light markers may not use generic static records.
- Donor records must use the same ELE version as the target map.
- Generated output belongs under `_fpm_generated/` and is not committed.

## Command

Close GameGuru MAX before generating the test map, then run:

```bat
cd /d "%USERPROFILE%\Desktop\BLACK SIGNAL\BLACK SIGNAL"
git pull
powershell -ExecutionPolicy Bypass -File .\tools\create-district12-street-fabric.ps1
```

The output is:

```text
_fpm_generated\BLACK SIGNAL - District 12 - street-fabric.fpm
_fpm_generated\BLACK SIGNAL - District 12 - street-fabric.report.json
```

Open the generated FPM directly in GameGuru MAX. Verify road-center markings, rail/post placement, poles, lamp meshes, and actual light contribution before any production promotion.

If the command reports that `CS_Street_Light_Marker.fpe` has no exact same-version donor record, the safe path is to create/save one exact marker exemplar in a disposable MAX level of the same ELE version or seed it into District 12 manually once. The writer will then harvest that engine-authored record and can reproduce it deterministically thereafter.
