# GameGuru MAX integration

BLACK SIGNAL treats GameGuru MAX as a **local authoring/runtime environment** and this repository as the source of truth for project-owned material.

## Authoritative layout

```text
gameguru/
├── maps/                         # production .fpm/.lst maps
└── Files/                        # project-owned files that mirror GameGuru MAX/Files
    ├── scriptbank/
    │   └── user/
    │       └── black_signal/     # BLACK SIGNAL Lua behaviours
    ├── entitybank/
    │   └── User/
    │       └── BLACK SIGNAL/     # future custom entities only
    ├── audiobank/
    │   └── black_signal/         # future owned audio
    └── imagebank/
        └── black_signal/         # future owned images
```

The top-level legacy `Files/` directory is **not** the authoritative project structure. It came from the original broad GameGuru project/export snapshot and contains engine/runtime material. Do not add new BLACK SIGNAL work there.

## Local GameGuru MAX target

The default user-writable GameGuru MAX tree is expected at:

```text
%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files
```

Custom project scripts deploy beneath `scriptbank\user\black_signal` so GameGuru updates do not replace them.

## Lua behaviour contract

GameGuru MAX discovers custom behaviours from Lua files and expects a description comment near the top of the file. BLACK SIGNAL scripts follow these rules:

1. File name and callback prefix match. `bs_shot_marker.lua` therefore defines `bs_shot_marker_init(e)` and `bs_shot_marker_main(e)`.
2. The script begins with one or more `-- DESCRIPTION:` metadata comments so it appears as a behaviour in MAX.
3. Dynamic Lua editor properties use GameGuru MAX's `DESCRIPTION` syntax and are stored per entity.
4. Project scripts live in `scriptbank/user/black_signal`; CineGuru's `cg_*` scripts remain an external installed dependency and are never copied into this repository.
5. Scripts should use MAX-tested commands only. Do not assume every historical GameGuru Classic command behaves identically in MAX.

A minimal project-owned behaviour is provided at:

```text
gameguru/Files/scriptbank/user/black_signal/bs_shot_marker.lua
```

It intentionally does not call undocumented engine or CineGuru internals. Its first job is to prove the repo-to-MAX behaviour pipeline and provide editable production metadata inside the editor.

## Map contract

The canonical exterior map is:

```text
gameguru/maps/BLACK SIGNAL - District 12.fpm
```

The `.fpm` is a binary GameGuru map and is tracked with Git LFS. Its companion `.lst` records referenced dependencies. The repository can version and deploy the map, but actual street geometry, entity placement, CineGuru camera nodes, lights, actors, and trigger zones must be authored/saved inside GameGuru MAX.

## Deploy and validate

From PowerShell at the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\validate-repo.ps1
powershell -ExecutionPolicy Bypass -File .\tools\deploy-gameguru-project.ps1
```

The deploy script copies only BLACK SIGNAL-owned source plus the production map. It does **not** copy or overwrite GameGuru engine content, Cyberpunk Streets assets, or CineGuru files.

After changing District 12 in MAX, the existing round-trip helper remains available:

```bat
tools\sync-district12-back.bat
```

Always inspect `git status` before committing a binary map revision.