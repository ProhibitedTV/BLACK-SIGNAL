# BLACK SIGNAL GameGuru MAX behaviours

This folder mirrors the local GameGuru MAX path:

```text
Files\scriptbank\user\black_signal
```

Only project-owned Lua belongs here. Do not copy CineGuru MAX's commercial `Cine Guru MAX` script folder into the repository.

## Current behaviour

`bs_shot_marker.lua` is a Dynamic Lua metadata behaviour for virtual-production entities. Its filename matches its `bs_shot_marker_*` callbacks and its `DESCRIPTION` fields expose Shot ID, Take and Enabled values in GameGuru MAX.

Keep every new behaviour's filename and callback prefix aligned, and validate the repo before deployment.