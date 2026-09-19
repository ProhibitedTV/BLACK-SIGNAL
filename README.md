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

## Source-of-truth layout

```text
BLACK-SIGNAL/
├── ASSET-MANIFEST.md
├── docs/                         # engine / CineGuru / repo conventions
├── film/                         # screenplay, shot lists, production notes
├── gameguru/
│   ├── maps/                     # production FPM/LST files
│   └── Files/                    # BLACK SIGNAL-owned GameGuru Files mirror
│       └── scriptbank/user/black_signal/
├── tools/                        # validation, deploy and map round-trip helpers
└── Files/                        # LEGACY broad project/export snapshot; not authoritative
```

Do **not** put new BLACK SIGNAL source into the top-level legacy `Files/` tree. Project-owned GameGuru files belong beneath `gameguru/Files/` using the same relative path they need beneath the local GameGuru MAX `Files` directory.

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
```

The deployer targets the user-writable GameGuru MAX tree under `%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files`, backs up an existing District 12 map, deploys the production map, and copies only project-owned `gameguru/Files` content. It does not vendor or overwrite CineGuru or marketplace packs.

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

The repository is now structured to support that work; the next milestone is a real in-engine set-dressing and CineGuru camera pass.