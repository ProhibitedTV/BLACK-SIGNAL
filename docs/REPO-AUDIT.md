# Repository audit — GameGuru MAX / CineGuru MAX

## Finding

The repository had a valid source-controlled copy of the District 12 `.fpm` map and useful production documentation, but it did **not** yet have a proper project-owned GameGuru `Files` mirror, any BLACK SIGNAL Lua behaviours, or an explicit CineGuru dependency boundary.

That explains why opening the project in GameGuru MAX did not reveal a newly authored film set: the repository had imported a pre-existing city map and documented how Arrival Boulevard should be dressed, but no tool had actually placed geometry or CineGuru camera entities inside the binary `.fpm`.

## Existing good pieces

- `gameguru/maps/BLACK SIGNAL - District 12.fpm` is the canonical exterior map and is tracked through Git LFS.
- `gameguru/maps/BLACK SIGNAL - District 12.lst` records map dependencies.
- `film/` contains concept, screenplay, shot-list and production notes.
- `tools/deploy-district12.bat` and `tools/sync-district12-back.bat` establish a safe binary-map round trip.

## Structural problems found

### 1. `gameguru/` contained only `maps/`

There was no source-controlled custom `scriptbank`, `entitybank`, `audiobank`, or `imagebank` namespace for BLACK SIGNAL.

### 2. The root `Files/` tree is a legacy broad snapshot

The original commit contains many GameGuru engine/runtime asset families (`audiobank`, `gamecore`, `terraintextures`, `treebank`, and more) plus `projectbank`. This is not a clean project-source boundary and may include redistributable-license concerns for third-party/runtime content.

No destructive cleanup is performed by this branch. History rewriting or deleting the legacy tree should be a separate, explicitly approved operation after ownership/licensing review.

### 3. CineGuru was installed locally but not represented as a dependency

CineGuru should remain external. BLACK SIGNAL should reference and use its installed behaviours rather than copying commercial `cg_*` scripts into a public repository.

### 4. No project-owned Lua behaviour existed

The new `bs_shot_marker.lua` provides a deliberately small MAX-native Dynamic Lua behaviour whose filename, callbacks, `DESCRIPTION` metadata and per-entity properties follow GameGuru MAX conventions.

## New source-of-truth layout

```text
BLACK-SIGNAL/
├── ASSET-MANIFEST.md
├── docs/
│   ├── GAMEGURU-MAX.md
│   ├── CINEGURU-MAX.md
│   └── REPO-AUDIT.md
├── film/
├── gameguru/
│   ├── maps/
│   └── Files/
│       └── scriptbank/user/black_signal/
└── tools/
    ├── validate-repo.ps1
    ├── deploy-gameguru-project.ps1
    ├── deploy-district12.bat
    └── sync-district12-back.bat
```

Future project-owned entities/audio/images should be added under `gameguru/Files/...` in the same relative path they need inside the user's GameGuru MAX `Files` directory.

## What this does not claim

This structure does **not** mean District 12 is finished. The city still needs an in-engine authoring pass: street selection/rebuild, modular buildings, background skyline, signage, lighting, CineGuru camera/trigger placement, and a saved map revision.

The point of this audit is to make the repository technically coherent so those edits can be versioned and reproduced instead of living as an opaque local GameGuru project.