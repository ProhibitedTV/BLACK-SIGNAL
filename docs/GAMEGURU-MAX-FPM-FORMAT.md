# GameGuru MAX FPM format notes

This document records the parts of the GameGuru MAX level format that BLACK SIGNAL has verified from the current open-source GameGuru MAX codebase. The goal is to support **safe, deterministic authored-city generation** without treating `.fpm` as an opaque binary.

## Current conclusion

An `.fpm` is a ZIP-style file block used by GameGuru MAX. The current engine creates the archive with the password:

```text
mypassword
```

The save path in `M-MapFile.cpp` creates the FPM and adds the level working files from `levelbank/testmap`. The ZIP implementation in `FileBlocks.cpp` / `cZip.cpp` uses minizip/zlib and passworded ZIP entries.

Primary upstream references:

- https://github.com/Dark-Basic-Software-Limited/GameGuruMAX/blob/main/GameGuru%20Core/GameGuru/Source/M-MapFile.cpp
- https://github.com/Dark-Basic-Software-Limited/GameGuruMAX/blob/main/GameGuru%20Core/GameGuru/Source/M-Entity.cpp
- https://github.com/Dark-Basic-Software-Limited/GameGuruMAX/blob/main/GameGuru%20Core/Dark%20Basic%20Public%20Shared/Dark%20Basic%20Pro%20SDK/DarkSDKMore/Enhancements/FileBlocks.cpp
- https://github.com/Dark-Basic-Software-Limited/GameGuruMAX/blob/main/GameGuru%20Core/Dark%20Basic%20Public%20Shared/Dark%20Basic%20Pro%20SDK/DarkSDKMore/Enhancements/Zlib/cZip.cpp
- https://github.com/Dark-Basic-Software-Limited/GameGuruMAX/blob/main/GameGuru%20Core/GameGuru/Include/Types.h

## FPM members

The current save routine explicitly includes the following core members when present:

```text
header.dat
playerconfig.dat
locked.cfg
cfg.cfg
map.ele
map.ent
map.way
map.obs
visuals.ini
grass_coloronly.dds
ggterrain.dat
terrain node folders / terrain data
groupimg*.png
...
```

For city-object authoring, the two key files are:

```text
map.ent  = entity asset bank
map.ele  = placed entity element records
```

Other files may contain derived or independent state. Initial authoring experiments must preserve them byte-for-byte.

## header.dat

Current MAX writes two 32-bit integer fields at the start:

```text
major = 1
minor = 0
```

The FPM inspector reports these but does not modify them.

## map.ent

`entity_savebank()` writes the entity-bank count followed by one string for each bank entry. `entity_loadbank()` reads the same count and strings back into `entitybank_s[]`.

Conceptually:

```text
int32 entity_bank_count
string bank_entry_1
string bank_entry_2
...
```

An entity instance in `map.ele` refers to this table using `bankindex`.

The inspector currently attempts the line-string representation first and has a diagnostic fallback for legacy/variant serialization. It never rewrites `map.ent` yet.

## map.ele

The current MAX serializer sets:

```text
versionnumbersave = 342
```

The stream begins:

```text
int32 ele_version
int32 entity_element_count
```

For ELE version 101 and later, every entity record starts with a stable placement prefix:

```text
int32 maintype
int32 bankindex
int32 staticflag

float32 x
float32 y
float32 z

float32 rx
float32 ry
float32 rz

string name
string legacy_aiinit
string aimain
string legacy_aidestroy
int32 isobjective
...
```

The full record then continues through many version-gated fields. Later versions add scale, Wicked material overrides, group state, quaternion values, particle state, collision settings, shader parameters, sound fields, and more.

Notable version additions from the current serializer include:

```text
305  scalex / scaley / scalez
314  Wicked material state
316  object relationship data
317  per-mesh material state
318  render-order bias
319  entity group table payload
320+ particle/decal/collision/gameplay fields
329  quaternion mode and quaternion values
330  auto-flatten
334  group names
335  creationOfGroupID
336  light probe XYZ
339  custom shader ID/parameters
340  Wicked effect and related fields
341  use-FPE-settings
342  soundset4a
```

`MAXMESHMATERIALS` is currently `100` in `Types.h`, which matters because ELE versions 314/317/318 contain large material arrays.

## Primitive encoding

The current `EntityWriter` writes `int` and `float` values by copying their native 4-byte representation into the byte stream. On the Windows/x86-64 MAX target this is little-endian 32-bit integer / IEEE-754 float data.

The ELE-specific string writer appends CRLF (`0x0D 0x0A`) after string bytes.

## Why direct authoring is plausible

Object placement is not hidden in terrain data or an undocumented scene database. Position, Euler rotation, scale, bank reference, and the rest of the per-entity state are explicitly serialized in `map.ele`.

That means a deterministic city compiler can eventually perform this pipeline:

```text
city build plan
    -> read FPM
    -> decrypt/extract members
    -> parse map.ent
    -> parse map.ele v342
    -> clone known-good static entity records
    -> change bankindex / transform / selected safe fields
    -> serialize map.ent + map.ele
    -> preserve every unrelated member
    -> recreate compatible passworded FPM
    -> open once in MAX and Save Level
```

## Safety gates

We are deliberately not jumping directly to a writer.

### Gate A - archive and prefix inspection

Implemented by `tools/fpm_inspect.py`.

Requirements:

- open the real District 12 FPM with the known password;
- list members;
- report `header.dat` version;
- decode the `map.ent` bank;
- report ELE version and entity count;
- decode the first entity's stable placement prefix and resolve its `bankindex` to an asset path;
- extract members and emit SHA-256 manifests for later preservation checks.

### Gate B - full v342 traversal

Before writing anything, the parser must consume every entity record in the real District 12 `map.ele` and end exactly at EOF. No heuristic record scanning is acceptable.

### Gate C - byte-identical serialization

Parse and reserialize `map.ele` without semantic changes. The output must be byte-identical, or differences must be fully explained and validated in MAX.

### Gate D - one controlled clone

Clone one known-good static Cyber City Streets entity record, change only a transform, increment the element count, build a new test FPM, and load it in MAX.

### Gate E - city compiler

Only after Gates A-D succeed do we generate Block 01 and later city blocks from the modular Cyber City Streets kit.

## Current tool usage

Inspect the curated repository copy:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1
```

Inspect the Separate Project Folder copy:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1 -Source Project
```

Inspect the global GameGuru MAX mapbank copy:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1 -Source Global
```

Emit JSON:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1 -Json
```

Decrypt/extract the FPM for local analysis without changing the original:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1 -ExtractDir .\_fpm_probe
```

Do not commit extracted commercial DLC content or generated FPM internals. The extraction option is for local format analysis only.
