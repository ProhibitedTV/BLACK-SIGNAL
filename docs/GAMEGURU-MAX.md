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

## Important: project != loaded level

A GameGuru MAX **project/storyboard** and an `.fpm` **level** are separate pieces of state. Copying `BLACK SIGNAL - District 12.fpm` into `mapbank` does not automatically add that level to the BLACK SIGNAL Storyboard, select it as the current level, or rewrite `projectbank/BLACK SIGNAL/project203.dat`.

For the first isolation test after a deploy:

1. Open GameGuru MAX.
2. From the Level Editor / Load Existing Level flow, load `BLACK SIGNAL - District 12.fpm` directly.
3. Confirm the Player Start marker exists and Test/Play works.
4. Only after direct level test works, add the existing level to the BLACK SIGNAL Storyboard and save the project.

This distinction matters in current MAX builds. Upstream GameGuru MAX issue `Dark-Basic-Software-Limited/GameGuruRepo#6423` (opened July 2026) reports that adding an existing level to a project may fail to transfer that level's referenced files into a separate project folder. BLACK SIGNAL therefore keeps the raw FPM test path as the baseline sanity check instead of assuming project/storyboard integration succeeded.

## Git LFS requirement

The production FPM must be **materialized** before deployment. A 100-ish byte Git LFS pointer is not a playable GameGuru map. The deploy helper now runs an LFS pull and refuses to copy a pointer/stub into GameGuru MAX.

Manual recovery command:

```powershell
git lfs pull --include="gameguru/maps/*.fpm"
```

## Deploy, validate, diagnose

From PowerShell at the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\validate-repo.ps1
powershell -ExecutionPolicy Bypass -File .\tools\deploy-gameguru-project.ps1
powershell -ExecutionPolicy Bypass -File .\tools\diagnose-play-level.ps1
```

The play-level diagnostic verifies that:

- the repository FPM is a real binary rather than an LFS pointer;
- the deployed FPM is present and matches the repository source unless it has been edited in MAX;
- the District 12 dependency list references the Player Start marker;
- the installed Player Start asset exists;
- CineGuru and the BLACK SIGNAL behaviour folder are visible locally;
- a BLACK SIGNAL project descriptor is treated separately from the raw level.

The deploy script copies only BLACK SIGNAL-owned source plus the production map. It does **not** copy or overwrite GameGuru engine content, Cyberpunk Streets assets, CineGuru files, or the project's `project203.dat` storyboard descriptor.

After changing District 12 in MAX, the existing round-trip helper remains available:

```bat
tools\sync-district12-back.bat
```

Always inspect `git status` before committing a binary map revision.
