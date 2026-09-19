# GameGuru MAX integration

BLACK SIGNAL treats GameGuru MAX as a **local authoring/runtime environment** and this repository as the source of truth for curated project-owned material.

## Two GameGuru trees exist in this repository

The repository currently contains both:

```text
gameguru/                      # curated BLACK SIGNAL source
├── maps/
└── Files/
    └── scriptbank/user/black_signal/

Files/                         # GameGuru MAX project/runtime/writables tree
└── projectbank/BLACK SIGNAL/project203.dat
```

The top-level `Files/` tree should no longer be described as merely a disposable legacy export. The presence of `Files/projectbank/BLACK SIGNAL/project203.dat`, together with the fact that MAX modifies that file when the project is opened/saved, is consistent with this checkout being used as a **Separate Project Folder**.

That does not make the entire top-level `Files/` tree suitable source material: it contains a broad mixture of runtime/copied/engine-style assets and may include third-party content. BLACK SIGNAL-owned scripts and map source remain curated under `gameguru/`.

## Default GameGuru MAX Files tree

The normal user-writable GameGuru MAX tree is expected at:

```text
%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files
```

BLACK SIGNAL's deploy helper always maintains a raw-level copy there so we have a known isolation path independent of Storyboard/project state.

When the repository's own `Files/projectbank/BLACK SIGNAL/project203.dat` is detected, the deploy helper also mirrors the production FPM and BLACK SIGNAL-owned scripts into the repository's top-level `Files/` runtime tree. Those runtime mirrors are ignored by Git; the curated source remains under `gameguru/`.

## Lua behaviour contract

GameGuru MAX discovers custom behaviours from Lua files and expects a description comment near the top of the file. BLACK SIGNAL scripts follow these rules:

1. File name and callback prefix match. `bs_shot_marker.lua` therefore defines `bs_shot_marker_init(e)` and `bs_shot_marker_main(e)`.
2. The script begins with one or more `-- DESCRIPTION:` metadata comments so it appears as a behaviour in MAX.
3. Dynamic Lua editor properties use GameGuru MAX's `DESCRIPTION` syntax and are stored per entity.
4. Project scripts live in curated source at `gameguru/Files/scriptbank/user/black_signal` and are deployed into whichever MAX runtime tree is active.
5. CineGuru's `cg_*` scripts remain an external installed dependency and are never committed into this repository.
6. Scripts should use MAX-tested commands only. Do not assume every historical GameGuru Classic command behaves identically in MAX.

## Map contract

The canonical curated exterior map is:

```text
gameguru/maps/BLACK SIGNAL - District 12.fpm
```

The `.fpm` is a binary GameGuru map and is tracked with Git LFS. Its companion `.lst` records referenced dependencies.

The deploy helper can maintain runtime mirrors at:

```text
%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files\mapbank\BLACK SIGNAL - District 12.fpm
```

and, when the repository is detected as a Separate Project Folder:

```text
<repo>\Files\mapbank\BLACK SIGNAL - District 12.fpm
```

These copies do **not** attach the level to the Storyboard or rewrite `project203.dat`.

## Important: project != loaded level

A GameGuru MAX **project/storyboard** and an `.fpm` **level** are separate pieces of state. Opening My Games > BLACK SIGNAL does not prove District 12 is the currently loaded playable level.

For the first isolation test after a deploy:

1. Open GameGuru MAX.
2. From the Level Editor / Load Existing Level flow, load `BLACK SIGNAL - District 12.fpm` directly.
3. Confirm the Player Start marker exists and Test/Play works.
4. Only after direct-level Test/Play works, add the existing level to the BLACK SIGNAL Storyboard and save the project.

Current upstream GameGuru MAX issue `Dark-Basic-Software-Limited/GameGuruRepo#6423` (opened July 2026) reports that adding an existing level to a project may fail to transfer that level's referenced files into a Separate Project Folder. Keep the raw-level test path as the baseline sanity check.

## Writables folder matters

Separate Project Folder behavior is tied to MAX's writables location. If this repository is the active project folder, inspect:

```text
Edit > Settings > Advanced > Writables folder location
```

If CineGuru exists under the default GameGuru MAX `Files` tree but does not appear while BLACK SIGNAL is open, verify that setting before copying or vendoring any CineGuru files.

## Git LFS requirement

The production FPM must be **materialized** before deployment. A small Git LFS pointer is not a playable GameGuru map. The deploy helper runs an LFS pull and refuses to copy a pointer/stub into MAX.

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

The play-level diagnostic verifies:

- the repository FPM is a real binary rather than an LFS pointer;
- the default deployed FPM is present and matches the curated source unless edited in MAX;
- the District 12 dependency list references the Player Start marker;
- the installed Player Start asset exists;
- CineGuru and the BLACK SIGNAL behavior are visible in the default tree;
- whether this checkout contains Separate Project Folder state;
- whether project-local runtime mirrors of District 12 and the BLACK SIGNAL behavior exist.

The deploy script does **not** rewrite the Storyboard descriptor and does **not** vendor CineGuru or marketplace packs.

After changing District 12 in MAX, use:

```bat
tools\sync-district12-back.bat
```

Always inspect `git status` before committing a binary map revision.
