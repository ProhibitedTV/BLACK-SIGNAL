# Hero Block 01: measured assembly candidate

## Current status

The builder and geometric checks are implemented. **No finished FPM has been exported or promoted.** The first export failed because C: reported zero free bytes; its incomplete output was removed. The builder now checks space before writing and removes its own output if writing fails. GameGuru MAX window capture also timed out, so native visual acceptance remains pending. The existing District 12 production map was not changed.

The user's current screenshot shows disconnected vertical facade strips, exposed terrain between roads and buildings, and misoriented road markings. The saved production map contains 14 six-window stacks with one roof tile apiece, rather than complete street buildings.

## Replacement approach

`tools/measure-cybercity-kit.py` runs the installed GameGuru MAX DBO2X converter and measures actual flattened mesh vertices. `cybercity-kit-measurements.json` records dimensions, pivot offsets and mesh hashes; no commercial mesh or texture is added to source control. Rerun measurement after asset updates.

The measurements establish:

- Wall bay and story height: 200 units each.
- Corner modules: 100-unit legs, with exterior trim extending 20 units beyond the corner pivot.
- Roof 2x2: 200-unit square, with its bottom at local Y=80. Placing it at the wall-top pivot height would float it 80 units above the wall.
- Straight 4X road: centered 400-unit square.
- Four-way intersection: centered 600-unit square.
- Curve 1: 800-unit footprint beginning at its corner pivot. It cannot use the centered-road assumptions.
- Sidewalk surface: local Y=10; asphalt: local Y=2.

`tools/fpm_author_hero_block.py` composes complete shells explicitly instead of harvesting nearby pivots as alleged buildings. Four parcels surround a central junction:

| Set | Shell | Floors | Purpose |
| --- | --- | --- | --- |
| Vale Exchange | 800 x 800 | 6 | Commercial street wall |
| Municipal Annex | 800 x 800 | 8 | Civic mass |
| Service Works | 800 x 600 | 4 | Lower industrial frontage and rear space |
| Signal House | 600 x 800 | 10 | Slender landmark |

All four sides have wall courses and corner modules, entry modules occupy ground-floor bays, and complete tiled roofs sit on the last wall course. Paving and drop curbs repeat a measured relationship from the original CyberCity map. Lamps sit in curb strips. The road layout uses only calibrated straight and four-way pieces at this stage. Road markings, outer-road termination treatment, skyline, interiors, detailed dressing, terrain inspection and film lighting remain future work.

This is a calibration backlot, not the finished episodic city. Its outer roads expose set boundaries. The neutral mesh preview is a geometry diagnostic, not an in-engine beauty shot.

## Build after freeing disk space

The failed run had only C: available, with no free space. Free at least 100 MB for the candidate; more working space is needed for MAX itself.

From the repository root, with a Python 3 interpreter:

```powershell
python tools/measure-cybercity-kit.py --install 'C:/Program Files (x86)/Steam/steamapps/common/GameGuru MAX' --output docs/cybercity-kit-measurements.json
python tools/fpm_author_hero_block.py --donor 'C:/Users/RhythmicCarnage/Documents/GameGuruApps/GameGuruMAX/Files/mapbank/CyberCity.fpm' --output '_fpm_generated/BLACK SIGNAL - Hero Block 01.fpm' --measurements docs/cybercity-kit-measurements.json
python -m unittest discover -s tools/tests -p test_fpm_author_hero_block.py
```

Python is not on PATH in the execution environment used for this work. The available interpreter was `C:/Users/RhythmicCarnage/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

The writer refuses an existing output path, uses the donor's ELE version consistently, preserves the first record's global metadata, normalizes clone quaternion state and retains asset-specific donor records. It changes only `map.ele` inside the candidate archive and verifies the decrypted member hashes and entity traversal. It never deploys or modifies the production map.

Save any unsaved editor work before loading the separate candidate. Review ground-level approaches, roof seams, all building corners, curb transitions, terrain exposure and collision in MAX before promotion. CineGuru camera work should follow native approval of this first block.
