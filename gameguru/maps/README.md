# GameGuru MAX Film Maps

BLACK SIGNAL uses GameGuru MAX maps as virtual production stages.

## Canonical exterior stage

The production exterior map should be committed here as:

`BLACK SIGNAL - District 12.fpm`

It should be duplicated from the existing local editable map:

`%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files\mapbank\CyberCity.fpm`

Do not overwrite the original `CyberCity.fpm`.

A helper script exists at `tools\import-city-stage.bat` to make this copy from the local GameGuru MAX workspace into the repository.

## Source-control rules

- Treat `.fpm` map files as source assets, not generated exports.
- Track production `.fpm` files with Git LFS.
- Do not commit `_automatedbackups`.
- Do not bulk-copy the entire GameGuru MAX `Files` directory into this folder.
- Add only project-specific maps, scripts, and custom assets required by BLACK SIGNAL.

See `film/production/CITY-STAGE.md` for the stage design and filming requirements.
