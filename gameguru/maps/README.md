# GameGuru MAX Film Maps

BLACK SIGNAL uses GameGuru MAX maps as virtual production stages.

## Canonical exterior stage

The production exterior map is committed here as:

`BLACK SIGNAL - District 12.fpm`

The tracked copy under `gameguru/maps/` is the canonical Git/LFS source. The editable GameGuru MAX runtime copy may live in either:

`<repo>\Files\mapbank\BLACK SIGNAL - District 12.fpm`

or:

`%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files\mapbank\BLACK SIGNAL - District 12.fpm`

The repository-root `Files/mapbank/BLACK SIGNAL - District 12.fpm` mirror is intentionally ignored so normal builds and GameGuru saves do not constantly dirty Git history.

Use:

`tools\import-city-stage.bat`

to capture the current edited District 12 runtime map into the canonical `gameguru/maps/` location and stage it with Git LFS. The helper prefers the repo runtime map, then the user-profile District 12 map. It falls back to `CyberCity.fpm` only when no District 12 runtime map exists, for initial bootstrap only.

Do not overwrite the original `CyberCity.fpm`.

## Source-control rules

- Treat canonical `.fpm` map files as source assets, not generated exports.
- Track production `.fpm` files with Git LFS.
- Capture manual GameGuru edits into `gameguru/maps/` before committing if another tool or collaborator needs to inspect exact transforms.
- Do not commit `_automatedbackups`.
- Do not bulk-copy the entire GameGuru MAX `Files` directory into this folder.
- Add only project-specific maps, scripts, and custom assets required by BLACK SIGNAL.

See `film/production/CITY-STAGE.md` for the stage design and filming requirements.
