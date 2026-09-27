# District 12 manual reference analysis

When a visually corrected intersection is saved in GameGuru MAX and captured into the canonical Git-LFS map (`gameguru/maps/BLACK SIGNAL - District 12.fpm`), use `tools/fpm_analyze_manual_reference.py` to inspect the authored transforms before changing generator constants.

The analyzer attaches center lines, crosswalks, straight arrows, street lamps, and sidewalk-corner assets to the nearest compatible road module and reports owner-local X/Y/Z/yaw signatures. Repeated signatures represent generator cadence; rare deviations are candidates for the manually corrected placement.

A dedicated GitHub Actions workflow checks out the LFS object, materializes the real FPM, runs the analyzer, and uploads `manual-reference-report.json`. This keeps binary map inspection reproducible and avoids guessing transforms from screenshots.
