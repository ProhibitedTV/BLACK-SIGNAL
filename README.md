# BLACK SIGNAL

**BLACK SIGNAL** is a cyberpunk short film produced primarily inside **GameGuru MAX**, using the engine as a virtual-production stage and **CineGuru MAX** as the cinematic toolset.

## Logline

A municipal systems technician enters an evacuated district that is still consuming power. The streets are empty, but the city behaves as if its residents are still there—and the deeper she goes, the more the infrastructure appears to remember her before she arrived.

## Format

- Short film / proof of concept
- Target runtime: 10–20 minutes
- Primary production environment: GameGuru MAX
- Cinematic layer: CineGuru MAX
- Style: atmospheric science-fiction thriller with cyberpunk production design
- Priority: cinematography, sound, environment, tension, and story over gameplay systems

## Visual rule

> A city at 7:43 AM after something impossible happened at 3:17 AM.

Cold morning haze, empty infrastructure, distant machinery, active advertising, long sightlines, sparse human presence, and small impossible details.

## Repository layout

```text
BLACK-SIGNAL/
├── ASSET-MANIFEST.md
├── docs/                         # engine / CineGuru / repo conventions
├── film/                         # screenplay, shot lists, production notes
├── gameguru/
│   ├── maps/                     # curated production FPM/LST source
│   └── Files/                    # curated BLACK SIGNAL-owned GameGuru source
│       └── scriptbank/user/black_signal/
├── tools/                        # validation, deploy and map round-trip helpers
└── Files/                        # GameGuru MAX project/runtime tree from the Separate Project Folder
```

The important distinction is **curated source vs MAX runtime state**:

- `gameguru/` is the clean, reviewable source boundary for BLACK SIGNAL-owned maps/scripts.
- top-level `Files/` is the GameGuru MAX project/runtime tree created by the project workflow. It contains `projectbank/BLACK SIGNAL/project203.dat` plus a broad mixture of MAX/runtime assets, so it is **not disposable**, but it is also **not the preferred place to author new hand-maintained source**.
- deploy helpers can mirror the curated production map and owned scripts into the detected Separate Project Folder at runtime without creating duplicate Git source.

Do not bulk-add new engine/DLC/marketplace material from top-level `Files/` to Git. Project-owned code should still be authored under `gameguru/Files/` and deployed into MAX.

## District 12

The canonical exterior production map is:

```text
gameguru/maps/BLACK SIGNAL - District 12.fpm
```

It is tracked with Git LFS. The companion `.lst` records referenced map dependencies. Importing/versioning the map does not build the film set by itself: geometry, dressing, lighting, CineGuru cameras, camera nodes, actors and trigger entities still have to be authored and saved inside GameGuru MAX.

## GameGuru MAX / CineGuru MAX

Project conventions:

- `docs/GAMEGURU-MAX.md`
- `docs/CINEGURU-MAX.md`
- `docs/REPO-AUDIT.md`
- `ASSET-MANIFEST.md`

The repository contains BLACK SIGNAL-owned scripts only. CineGuru's commercial `cg_*` files and marketplace asset packs remain external dependencies.

A MAX-native Dynamic Lua behaviour is provided at:

```text
gameguru/Files/scriptbank/user/black_signal/bs_shot_marker.lua
```

## Validate and deploy

From PowerShell at the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\validate-repo.ps1
powershell -ExecutionPolicy Bypass -File .\tools\deploy-gameguru-project.ps1
powershell -ExecutionPolicy Bypass -File .\tools\diagnose-play-level.ps1
```

The deployer:

- materializes the Git LFS FPM;
- deploys District 12 and BLACK SIGNAL-owned scripts to the default GameGuru MAX `Files` tree;
- detects this repository's `Files/projectbank/BLACK SIGNAL/project203.dat` and, when present, also mirrors District 12 and owned scripts into the Separate Project Folder runtime tree;
- does **not** rewrite `project203.dat` or automatically attach the level to the Storyboard;
- does **not** vendor CineGuru or marketplace packs.

For the first play-test, load `BLACK SIGNAL - District 12.fpm` directly in the Level Editor. If Test/Play works there, add the existing level to the BLACK SIGNAL Storyboard and save the project.

After saving a District 12 edit in GameGuru MAX:

```bat
tools\sync-district12-back.bat
```

Review `git status` before committing the updated binary map.

## First film milestone

The first production target remains **Shot 001 — CURRENT POPULATION: ZERO** on Arrival Boulevard. See:

- `film/production/SHOT-001-FRAME.md`
- `gameguru/maps/DISTRICT-12-ARRIVAL-BOULEVARD.md`
- `film/production/DISTRICT-12-ASSET-AUDIT.md`

The repository is structured to support that work; the next milestone is a real in-engine set-dressing and CineGuru camera pass.
