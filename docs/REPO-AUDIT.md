# Repository audit — GameGuru MAX / CineGuru MAX

## Corrected finding

The repository contains **two different classes of GameGuru data**, and treating them as the same thing caused confusion:

1. `gameguru/` is the curated BLACK SIGNAL source boundary we control.
2. top-level `Files/` appears to be the GameGuru MAX **Separate Project Folder runtime/writables tree** for the BLACK SIGNAL project because it contains `Files/projectbank/BLACK SIGNAL/project203.dat` and changes there when the project is opened/saved.

The top-level `Files/` tree is therefore **not safe to call disposable legacy data**. It still contains a broad mixture of copied/runtime/engine-style assets and must be audited for ownership before public redistribution, but it also contains real GameGuru project state.

## Existing good pieces

- `gameguru/maps/BLACK SIGNAL - District 12.fpm` is the curated exterior-map source and is tracked through Git LFS.
- `gameguru/maps/BLACK SIGNAL - District 12.lst` records map dependencies.
- `film/` contains concept, screenplay, shot-list and production notes.
- `gameguru/Files/scriptbank/user/black_signal/` is the clean home for BLACK SIGNAL-owned Lua source.
- `tools/deploy-gameguru-project.ps1` mirrors curated source into the GameGuru runtime trees without rewriting Storyboard state.

## Why Play/Test can still be disabled

GameGuru MAX project/storyboard state and raw `.fpm` level state are separate. The repo contains a BLACK SIGNAL `project203.dat`, but copying a District 12 FPM into a mapbank does not automatically add that level to the Storyboard or make it the currently loaded level.

The current upstream GameGuru MAX issue `Dark-Basic-Software-Limited/GameGuruRepo#6423` (July 2026) reports that adding existing levels to a Separate Project Folder project may fail to transfer referenced files into the project folder. For that reason the supported isolation path is:

1. deploy/materialize District 12;
2. load `BLACK SIGNAL - District 12.fpm` directly in the Level Editor;
3. confirm Test/Play works on the raw level;
4. then add the existing level to the BLACK SIGNAL Storyboard and save `project203.dat` through MAX.

## Source vs runtime layout

```text
BLACK-SIGNAL/
├── ASSET-MANIFEST.md
├── docs/
├── film/
├── gameguru/                     # curated source we intentionally maintain
│   ├── maps/
│   └── Files/
│       └── scriptbank/user/black_signal/
├── tools/
└── Files/                        # GameGuru MAX Separate Project Folder runtime/state
    └── projectbank/BLACK SIGNAL/project203.dat
```

Do not bulk-copy the top-level `Files/` tree back into `gameguru/Files/`. The curated tree should contain only project-owned source. Conversely, do not delete top-level `Files/` until the Separate Project Folder relationship and all custom content have been fully audited.

## CineGuru boundary

CineGuru remains an external installed dependency. BLACK SIGNAL may use it locally, but its commercial `cg_*` files should not be vendored into the public repository. If MAX is opened with this repository as a Separate Project Folder and CineGuru is not visible, first inspect **Edit > Settings > Advanced > Writables folder location** rather than copying commercial files into Git.

## What this does not claim

The city still needs an in-engine authoring pass: street selection/rebuild, modular buildings, background skyline, signage, lighting, CineGuru camera/trigger placement, and a saved map revision.

The corrected architecture is meant to make that work reproducible without confusing GameGuru's generated project state with BLACK SIGNAL-owned source.
