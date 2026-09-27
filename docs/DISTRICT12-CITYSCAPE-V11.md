# District 12 populated cityscape

The production FPM now contains all 36 blocks of the existing road grid. Each block has a closed modular building with complete roof coverage, continuous parcel paving, commercial frontage, and a rear service area. Building heights vary from four to twelve floors. This is saved editor geometry, not a runtime-only extension.

The dressed build contains 9,001 entities, including the player start. There are 1,274 newly planned dressing pieces: storefront panels and signs, neon strips, ATMs with luminous screens, stacks of packaged goods and cans, benches, bins, fireplugs, six bus shelters, dumpsters, bags, cardboard, scattered newspapers and bottles, delivery boxes, and paired rooftop HVAC units/stands. Existing calibrated junction trees, planters, crossings, signals and pavement lights are distributed across the interior intersections. Seventy-two street lamps have corresponding light markers.

Shop windows and signs face the negative-Z frontage. Rear service doors have a 100-unit clear approach; dumpsters and waste pockets sit to either side. Commercial frontage colors, building dimensions and heights vary across blocks. The four mismatched outer curved pieces were replaced by square intersection aprons to meet the existing road endpoints; these retain short boundary-facing road stubs. Interiors, actors, vehicles and CineGuru camera choreography are not authored in this pass.

## Build and apply

Close GameGuru MAX, then run:

```powershell
./tools/build-district12-cityscape-v11.ps1 -Deploy
```

The script measures the installed meshes, builds a new encrypted FPM, verifies the saved records, backs up all existing target FPM/LST files, then copies to the curated map, project runtime mapbank and global GameGuru mapbank. Pass `-Candidate <path>` to validate and deploy an existing candidate. Without `-Deploy`, it only builds and validates. Python defaults to the bundled Codex runtime when present; `-PythonPath` overrides it.

The immutable `gameguru/references/District 12 - human corner.fpm` preserves the manually calibrated ELE 342 source. Older human-corner checks use this fixture rather than the changing production map. Exact material records for the new props come from the installed pack's authored `Cyberpunk Streets.fpm`. The narrow 334-to-342 schema adapter retains the original material payload and appends a pinned, editor-authored default extension. Emissive overlay records retain their authored dynamic flag. Regenerate the library with `tools/fpm_prepare_dressing_v11.py` if the source pack changes. No commercial meshes or textures are copied into curated source.

## Verification and review

Local checks cover full encrypted archive traversal, exact saved asset/XYZ/yaw multisets, 36 complete building envelopes, roof pivot alignment, pavement coverage, road clearance, door approaches and ground support for freestanding dressing. Archive members other than `map.ele` and `map.ent` remain unchanged. The saved validation receipt and complete placement plan are in `gameguru/buildplans/district12-v11-*.json`.

These checks establish file and placement integrity. Native appearance, lighting, culling, material appearance, frame rate and filming suitability require manual review in GameGuru MAX. Native capture was unavailable during the build; visual acceptance remains pending. Inspect storefront depth, corner paving, alley approaches and roof silhouettes first, then run the level to check lighting and performance. The 9,001-entity scene has not been performance-qualified.
