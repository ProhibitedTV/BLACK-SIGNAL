# BLACK SIGNAL GameGuru MAX behaviours

This folder mirrors the local GameGuru MAX path:

```text
Files\scriptbank\user\black_signal
```

Only project-owned Lua belongs here. Do not copy CineGuru MAX's commercial `Cine Guru MAX` script folder into the repository.

## Active runtime direction

District 12 physical city geometry is authored in the `.fpm` with the Cyberpunk Streets snap kit. The active `scriptbank\gameloop.lua` deliberately does **not** run any procedural city generator.

`bs_shot_marker.lua` remains an active Dynamic Lua metadata behaviour for virtual-production entities. Its filename matches its `bs_shot_marker_*` callbacks and its `DESCRIPTION` fields expose Shot ID, Take and Enabled values in GameGuru MAX.

Lua added from this point forward should focus on runtime/film behaviour such as triggers, shot metadata, animated advertisements, lighting/state changes and story events—not constructing roads, buildings or street furniture during Test Play.

## Legacy generator experiments

The following scripts are retained for source-history/reference but are not required or invoked by the active gameloop:

- `bs_city_runtime.lua`
- `bs_city_fabric.lua`
- `bs_basin_city.lua`
- `bs_city_v2.lua`
- `bs_city_v3.lua`
- `bs_city_details.lua`
- `bs_curb_utilities.lua`
- `bs_city_arch_dressing.lua`

Do not reconnect these to `gameloop.lua` as the production District 12 build path. See `docs/DISTRICT-12-AUTHORED-CITY.md` for the authored construction workflow.

Keep every new behaviour's filename and callback prefix aligned, and validate the repo before deployment.
