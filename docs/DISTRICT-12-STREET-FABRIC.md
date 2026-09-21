# District 12 authored street fabric

District 12's streets are not visually complete when only road and sidewalk geometry exists. The baseline still needs road markings, lamps, dynamic lights, sidewalk lighting, curb protection, bollards, and utility infrastructure.

## Important production change

The first generated street-fabric pass is **retired from production**.

It proved that BLACK SIGNAL can write valid GameGuru MAX FPM entity records, but its spatial model was wrong: it treated each road entity origin as if every module shared a reliable curb coordinate system, then repeated guessed local offsets. In the real level that placed lamp bases, rails, posts, and other furniture in traffic lanes and produced an implausibly dense obstacle course.

That is a placement-grammar failure, not an FPM-format failure.

`tools/promote-district12-street-fabric.ps1` now refuses to promote that known-bad pass unless `-ForceKnownBad` is supplied for regression testing.

## New ground truth: the installed CyberCity exemplar

The Cyber City Streets DLC ships with modular road/pavement pieces and road markings designed to snap cleanly together, plus modular building pieces, shop fronts, background buildings, street furniture, lights, and props. BLACK SIGNAL now treats the installed `CyberCity.fpm` showcase map as the spatial ground truth instead of inventing curb offsets.

For this throwaway production test project, the fastest way to restore a coherent city is to rebase the local District 12 runtime map on that official exemplar, then iterate from a city that already demonstrates the pack's intended scale, cadence, enclosure, and prop placement.

Run with GameGuru MAX closed:

```bat
cd /d "%USERPROFILE%\Desktop\BLACK SIGNAL\BLACK SIGNAL"
git pull
powershell -ExecutionPolicy Bypass -File .\tools\rebase-district12-on-cybercity.ps1
```

The rebase tool:

- locates the installed `CyberCity.fpm` in the normal GameGuru MAX / Steam mapbanks;
- validates the donor FPM with the BLACK SIGNAL parser before use;
- backs up the current project/global District 12 FPM and LST;
- copies the CyberCity FPM into the active Separate Project Folder and normal GameGuru MAX mapbank under the District 12 filename;
- copies the companion LST when present;
- verifies the promoted FPM byte-for-byte by SHA-256;
- deliberately does **not** modify the tracked `gameguru/maps` FPM.

The last rule is important because the repository is public and the Cyber City Streets license does not permit redistributing the DLC assets as an asset pack. The exemplar remains local to the licensed GameGuru MAX installation.

## Coherent road-system v4

The production road builder now treats a road as a **profile**, not a bag of interchangeable meshes.

`tools/build-district12-road-network.ps1` runs two stages:

1. `fpm_author_road_network_v3.py` rebuilds the physical road surface with one full-width grammar: 4-way/T/curve junction pieces plus `CS_Street_Straight_4X` for every ordinary main-street span.
2. `fpm_author_road_details_v4.py` reads the installed `CyberCity.fpm`, chooses one authored exemplar for each supported road kind, captures allow-listed road detail transforms around that exemplar, and repeats that same profile across the generated network.

Main traffic streets therefore never substitute `Straight 2X`, `Straight`, or `Straight Quarter` pieces. A block span stays `junction -> 4X -> 4X -> 4X -> junction`, so road width and module cadence cannot change randomly mid-block.

The first v4 detail profile is intentionally conservative:

- Straight 4X roads inherit exemplar-relative double center markings and street lamps with their real light markers.
- Four-way intersections inherit exemplar-relative crosswalk decals and blocker/bollard posts.
- T intersections inherit the same intersection detail roles when the chosen donor exemplar contains them.
- Existing copies of those profile details are stripped before re-authoring, making the pass repeatable.
- Sidewalk/curb geometry is **not** synthesized from guessed lateral offsets. It remains a separate calibration task.

The radius used while discovering a donor assembly is only a selection envelope. Final placements are copied from the chosen CyberCity exemplar's actual relative transforms and rotated with the target road module.

Run with GameGuru MAX closed:

```bat
cd /d "%USERPROFILE%\Desktop\BLACK SIGNAL\BLACK SIGNAL"
git pull
powershell -ExecutionPolicy Bypass -File .\tools\build-district12-road-network.ps1 -GridSize 7
```

Before adding buildings, inspect at least one full avenue and one hero intersection in MAX. The road system should read as one consistent street family from end to end, with repeatable markings and lighting instead of mixed-size road patches.

## What comes next

Once the project opens on the exemplar-derived city, future procedural authoring should learn from it instead of guessing. The next authoring grammar should derive relative transforms and cadence from actual exemplar neighborhoods: road module -> center marking -> sidewalk edge -> lamp/rail/bollard -> storefront/building wall. Only then should those patterns be transplanted or adapted into BLACK SIGNAL-specific blocks.

The direct FPM work remains useful: full ELE traversal, raw-record cloning, same-version donor records, encrypted repacking, and verification all passed. The change is that spatial placement must be calibrated from authored source data before replication.
