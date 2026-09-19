# CineGuru MAX integration

CineGuru MAX is an **external GameGuru MAX DLC/dependency** used for BLACK SIGNAL's cinematic layer. It is not vendored into this repository.

## What CineGuru provides

The published CineGuru MAX feature set is a strong fit for BLACK SIGNAL's film-first workflow: controllable cameras, nodal camera paths, camera tracking and subject changes, actor marks/animation/dialogue, trigger zones and trigger entities, light markers, sound/image triggers, subtitles, credits, fades, and visual-logic integration.

The installed package is expected to provide a `Files\scriptbank\Cine Guru MAX` script family. Public package manifests show components including:

```text
cg_actor.lua
cg_camera_endpoint.lua
cg_camera_node.lua
cg_cinematic_camera.lua
cg_credits.lua
cg_focal_point.lua
cg_image_trigger.lua
cg_lib.lua
cg_light_marker.lua
cg_light_node.lua
cg_trigger_zone.lua
```

Exact installed contents can change with CineGuru updates. The local installation and its bundled manual/examples are authoritative for `cg_*` behaviour properties and action-file syntax.

## BLACK SIGNAL rule

**Do not reimplement CineGuru.**

Use CineGuru for:

- cinematic cameras and camera paths
- actors and marks
- focal points / subject tracking
- trigger zones and trigger entities
- cinematic lighting cues
- fades, subtitles, image/sound cues and credits where appropriate

Use project-owned `black_signal` Lua only for BLACK SIGNAL-specific state, production metadata, or small glue behaviours that can be implemented with documented/MAX-tested commands.

Never copy CineGuru's commercial `cg_*` source, icons, manuals, or examples into this public repository.

## Recommended shot construction

For each filmed sequence, keep the GameGuru scene understandable as a virtual set:

```text
SHOT / SEQUENCE
├── set geometry and dressing
├── CineGuru cinematic camera
├── CineGuru camera nodes / endpoint as required
├── focal point or actor target as required
├── CineGuru trigger zone/entity
├── actor marks and cues
├── practical lights / CineGuru light markers
└── BLACK SIGNAL shot marker (project metadata)
```

For Shot 001, start with one locked or extremely slow CineGuru camera on Arrival Boulevard. Do not create a complex path until the static composition works.

## Local dependency check

`tools/deploy-gameguru-project.ps1` checks for:

```text
%USERPROFILE%\Documents\GameGuruApps\GameGuruMAX\Files\scriptbank\Cine Guru MAX
```

If it is missing, deployment still completes but reports CineGuru as an unmet production dependency.

## Version-control boundary

The repository owns the **instructions and project glue**. GameGuru MAX and CineGuru own their installed runtime/DLC files. Marketplace asset packs such as Cyberpunk Streets remain external dependencies and should be referenced by the `.fpm`/`.lst` and `ASSET-MANIFEST.md`, not duplicated into source control.