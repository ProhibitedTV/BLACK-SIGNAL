# GameGuru MAX FPM format notes

This document records the parts of the GameGuru MAX level format that BLACK SIGNAL has verified from the current open-source GameGuru MAX codebase and from the real District 12 level. The goal is to support **safe, deterministic authored-city generation** without treating `.fpm` as an opaque binary.

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

## Real District 12 verification

The Separate Project Folder copy of `BLACK SIGNAL - District 12.fpm` has now been inspected with the schema-driven parser. The real map reports:

```text
Archive members: 16, all encrypted
header.dat:      version 1.0
map.ent:         59 entity-bank entries
map.ele:         version 338
placed elements: 711
map.ele bytes:   6,814,157
trailing bytes:  0
```

That result matters because the production level is **ELE v338**, not v342. Current GameGuru MAX source writes v342, but the parser intentionally supports the historical version gates from v101 through v342. District 12 traverses all 711 real records and lands exactly at EOF, so Gate B is satisfied for the actual map.

The first real records also resolve cleanly through `map.ent`, including the Player Start and Cyberpunk Streets road modules. This proves the bank-index-to-placement relationship on the production FPM rather than only on synthetic test data.

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

Other files may contain derived or independent state. Initial authoring experiments preserve them byte-for-byte.

## header.dat

Current MAX writes two 32-bit integer fields at the start:

```text
major = 1
minor = 0
```

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

The authoring prototype does not need to rewrite `map.ent` for the first controlled clone because it clones an entity whose asset is already present in the bank.

## map.ele

Current MAX source sets:

```text
versionnumbersave = 342
```

but FPMs retain the version that was used when they were last saved. District 12 is v338.

The stream begins:

```text
int32 ele_version
int32 entity_element_count
```

For ELE version 101 and later, every entity record starts with a stable placement prefix:

```text
+0x00 int32   maintype
+0x04 int32   bankindex
+0x08 int32   staticflag

+0x0C float32 x
+0x10 float32 y
+0x14 float32 z

+0x18 float32 rx
+0x1C float32 ry
+0x20 float32 rz

+0x24 ...     first CRLF-terminated string and the versioned tail
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
338  clip/weapon reserve fields
339  custom shader ID/parameters
340  Wicked effect and related fields
341  use-FPE-settings
342  soundset4a
```

`MAXMESHMATERIALS` is currently `100` in `Types.h`, which matters because ELE versions 314/317/318 contain large material arrays.

## Primitive encoding

The current `EntityWriter` writes `int` and `float` values by copying their native 4-byte representation into the byte stream. On the Windows/x86-64 MAX target this is little-endian 32-bit integer / IEEE-754 float data.

The ELE-specific string writer appends CRLF (`0x0D 0x0A`) after string bytes.

## Why raw-record cloning is the first writer

A full semantic v338/v342 serializer is possible, but it is not required for the first safe authoring test. Once every entity record boundary is known, an existing static Cyber City Streets record can be preserved byte-for-byte and appended as another entity.

For the controlled clone, only these bytes change:

```text
map.ele header:
  entity_element_count += 1

cloned record:
  +0x0C x
  +0x10 y
  +0x14 z
```

The initial test intentionally does **not** change rotation, quaternion state, bankindex, scale, materials, behavior, physics, grouping, or any other property.

This is safer than constructing a large record from defaults because all FPE-derived and MAX-specific state stays exactly as MAX originally wrote it.

## Passworded FPM writer

`tools/fpm_clone_entity.py` includes a small traditional PKZIP/ZipCrypto writer so the test does not depend on 7-Zip or a third-party Python package. It:

- preserves archive member names and order;
- preserves every decrypted member payload except `map.ele` byte-for-byte;
- writes every output member with the GameGuru password `mypassword`;
- reopens the generated archive with the same FPM reader;
- re-runs the complete ELE traversal;
- SHA-256 compares every non-`map.ele` payload against the source.

The ZIP container bytes themselves are not expected to be identical because compression and encryption headers are regenerated. The **decrypted payloads** are what must remain identical.

## Safety gates

### Gate A - archive/entity inspection — PASS

Implemented by `tools/fpm_inspect.py`.

Verified on District 12:

- passworded FPM opens;
- `header.dat` decodes;
- `map.ent` decodes;
- `map.ele` header and bank references decode.

### Gate B - complete ELE traversal — PASS on real District 12

The schema parser consumes every version-gated field for all declared entities and requires EOF after the final record.

Real District 12 result:

```text
ELE v338
711 records
6,814,157 / 6,814,157 bytes consumed
trailing=0
```

No heuristic record scanning is used.

### Gate C - byte-identical raw-record reconstruction — implemented

`fpm_clone_entity.py` rebuilds `map.ele` as:

```text
original header bytes
+ raw bytes of entity 1
+ raw bytes of entity 2
+ ...
+ raw bytes of entity N
```

and refuses to proceed unless that reconstruction is byte-identical to the original stream.

This is a record-boundary proof rather than a field-by-field reserialization and is the preferred basis for the first writer.

### Gate D - one controlled clone — implemented, MAX compatibility test pending

The tool can now:

1. select an existing ungrouped static Cyber City Streets entity;
2. clone its complete raw record;
3. patch XYZ only;
4. increment the ELE count;
5. create a separate encrypted test FPM;
6. reopen and fully traverse the generated FPM;
7. prove that only decrypted `map.ele` changed.

The remaining Gate D check is external: load the generated FPM in GameGuru MAX and confirm the level opens and the clone appears at the reported new position.

### Gate E - deterministic city compiler

After Gate D passes in MAX, the next writer can emit many raw-record clones from a build plan. Rotation will require either matching pre-rotated source records or safely updating both Euler/quaternion state as appropriate. New asset families that are not already in `map.ent` will require controlled entity-bank extension.

## Current tool usage

Inspect the Separate Project Folder copy:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1 -Source Project
```

Create the one-object compatibility test from the real project FPM:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\create-district12-clone-test.ps1
```

The wrapper defaults to a known-present `CS_Street_Straight_4X.fpe` and moves its clone +1000 units on X. It writes:

```text
_fpm_generated\BLACK SIGNAL - District 12 - clone-test.fpm
```

The production FPM is never overwritten.

Custom example:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\create-district12-clone-test.ps1 `
  -Asset 'CS_Wall_01.fpe' -Dx 500 -Dz 500
```

Decrypt/extract the source FPM for local analysis without changing it:

```bat
powershell -ExecutionPolicy Bypass -File .\tools\inspect-district12-fpm.ps1 -ExtractDir .\_fpm_probe
```

Do not commit extracted commercial DLC content, generated FPM internals, or compatibility-test FPMs. `_fpm_probe/` and `_fpm_generated/` are ignored by Git.
