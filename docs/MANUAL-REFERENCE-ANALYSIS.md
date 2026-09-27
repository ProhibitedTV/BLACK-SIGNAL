# District 12 manual reference analysis

When a visually corrected intersection is saved in GameGuru MAX and captured into the canonical Git-LFS map (`gameguru/maps/BLACK SIGNAL - District 12.fpm`), use `tools/fpm_analyze_manual_reference.py` to inspect the authored transforms before changing generator constants.

The analyzer attaches center lines, crosswalks, straight arrows, street lamps, and sidewalk-corner assets to the nearest compatible road module and reports owner-local X/Y/Z/yaw signatures. Repeated signatures represent generator cadence; rare signatures identify the hand-edited reference.

A dedicated GitHub Actions workflow checks out the LFS object, materializes the real FPM, runs the analyzer, and uploads `manual-reference-report.json`. This keeps binary map inspection reproducible and avoids guessing transforms from screenshots.

## Captured reference: 2026-09-26

The captured FPM retained the exact validated road graph: 25 four-way junctions, 20 T junctions, 4 curves, and 252 Straight 4X modules. Against the repeated v9.1 dressing pattern, the hand-edited intersection produced four unique transform clues:

| Role | Repeated/generated transform | Manual reference transform | V9.2 rule |
| --- | --- | --- | --- |
| Double center line | local Z `±100`, local yaw `90°` | local Z `-100`, local yaw `0°` | keep `±100`, align both decals to road yaw (`0°` local yaw) |
| Straight arrow | lane offset `±94`, setback `±120`, quarter-turn yaw | `(-100, -180, 180°)` on the corrected approach | use lane offset `±100`, setback `±180`, local yaw `0°/180°` with travel |
| Crosswalk | north approach `(0, +200, 0°)` | `(+95, +200, 0°)` | compensate the asset's 95-unit lateral pivot bias and rotate that correction through all four approaches |
| Sidewalk corner | absent | `(-300, +300, -90°)` | rotate this exact corner transform through all four quadrants of every 4-way |

The manual map contained no unique street-lamp transform. V9.2 therefore preserves the v9.1 lamp cadence, 390-unit edge offset, alternating side, and safe dynamic-light-marker policy unchanged.

T-junction sidewalk/crosswalk grammar is still intentionally omitted: the captured manual correction proves the four-way layout only, so V9.2 does not invent an unobserved T layout.
