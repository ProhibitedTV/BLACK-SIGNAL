# BLACK SIGNAL asset and tool manifest

This repository should contain only BLACK SIGNAL-owned source plus explicitly permitted project files. Engine, DLC and marketplace packs are external dependencies unless their license explicitly permits source redistribution.

| Dependency | Role | Repository policy |
| --- | --- | --- |
| GameGuru MAX | Editor, renderer, runtime and map authoring | External; do not vendor engine/runtime files |
| CineGuru MAX | Cinematic cameras, actors, triggers, lighting and sequence tools | External commercial DLC; do not vendor `cg_*` scripts/assets/manuals |
| Cyberpunk Streets Booster Pack | Roads, sidewalks, modular buildings, storefronts and city dressing used by District 12 | External asset dependency; reference through the map, do not copy raw pack files here |
| BLACK SIGNAL District 12 `.fpm` / `.lst` | Project production map and dependency list | Versioned under `gameguru/maps/`; `.fpm` via Git LFS |
| BLACK SIGNAL custom Lua | Project-specific behaviours and glue | Versioned under `gameguru/Files/scriptbank/user/black_signal/` |
| BLACK SIGNAL original audio/images/entities | Project-owned production material | Add only under the corresponding `gameguru/Files/...` project namespaces |

## Legacy root `Files/`

The existing root `Files/` directory predates this manifest and is a broad GameGuru project/export snapshot. Treat it as legacy, not as the template for new work. Do not add new engine or marketplace content there.

A later cleanup can remove or rewrite legacy content only after explicit approval and an ownership/licensing review.