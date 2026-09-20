#!/usr/bin/env python3
"""Read-only GameGuru MAX FPM inspection utilities.

The current GameGuru MAX source shows FPM files are passworded ZIP containers
and that placed entities live in a versioned binary stream named ``map.ele``.
This tool is deliberately read-only: it can decrypt, inspect, traverse, hash,
and extract an FPM, but it does not write or repack one.

The ELE parser below mirrors the field order written by the current
``entity_saveelementsdata`` implementation through ELE version 342. Its core
safety property is structural: every declared entity record must be consumed
and the final parser offset must land exactly at EOF. No heuristic record
scanning is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

FPM_PASSWORD = b"mypassword"
EXPECTED_ELE_VERSION = 342
MAX_MESH_MATERIALS = 100


class FpmError(RuntimeError):
    pass


@dataclass
class BinaryReader:
    data: bytes
    offset: int = 0

    def remaining(self) -> int:
        return len(self.data) - self.offset

    def require(self, size: int, label: str) -> None:
        if self.offset + size > len(self.data):
            raise FpmError(
                f"Unexpected end of data while reading {label} at offset "
                f"0x{self.offset:X} (need {size}, have {self.remaining()})."
            )

    def i32(self, label: str) -> int:
        self.require(4, label)
        value = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return value

    def u32(self, label: str) -> int:
        self.require(4, label)
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def f32(self, label: str) -> float:
        self.require(4, label)
        value = struct.unpack_from("<f", self.data, self.offset)[0]
        self.offset += 4
        return value

    def crlf_string(self, label: str) -> str:
        start = self.offset
        end = self.data.find(b"\r\n", start)
        if end < 0:
            raise FpmError(
                f"Could not find CRLF terminator for {label} starting at "
                f"offset 0x{start:X}."
            )
        self.offset = end + 2
        return self.data[start:end].decode("utf-8", errors="replace")

    def skip_i32(self, count: int, label: str) -> None:
        if count < 0:
            raise FpmError(f"Negative integer count for {label}: {count}")
        self.require(count * 4, label)
        self.offset += count * 4

    def skip_f32(self, count: int, label: str) -> None:
        if count < 0:
            raise FpmError(f"Negative float count for {label}: {count}")
        self.require(count * 4, label)
        self.offset += count * 4

    def skip_strings(self, count: int, label: str) -> None:
        if count < 0:
            raise FpmError(f"Negative string count for {label}: {count}")
        for i in range(count):
            self.crlf_string(f"{label}[{i}]")


class FpmArchive:
    def __init__(self, path: Path):
        self.path = path
        if not path.is_file():
            raise FpmError(f"FPM not found: {path}")
        try:
            self.zip = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile as exc:
            raise FpmError(
                f"{path} is not readable as a ZIP/FPM container: {exc}"
            ) from exc

    def close(self) -> None:
        self.zip.close()

    def __enter__(self) -> "FpmArchive":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def names(self) -> list[str]:
        return self.zip.namelist()

    def _actual_name(self, requested: str) -> str:
        wanted = requested.replace("\\", "/").lower()
        for name in self.names():
            if name.replace("\\", "/").lower() == wanted:
                return name
        raise FpmError(f"FPM member not found: {requested}")

    def read(self, name: str) -> bytes:
        actual = self._actual_name(name)
        try:
            return self.zip.read(actual, pwd=FPM_PASSWORD)
        except RuntimeError as exc:
            raise FpmError(
                f"Failed to decrypt/read '{actual}' with the known GameGuru MAX "
                f"FPM password: {exc}"
            ) from exc

    def archive_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "name": info.filename,
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": info.file_size,
                "encrypted": bool(info.flag_bits & 0x1),
                "compression": info.compress_type,
                "crc32": f"{info.CRC:08x}",
            }
            for info in self.zip.infolist()
        ]

    def member_manifest(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for info in self.zip.infolist():
            if info.is_dir():
                continue
            payload = self.read(info.filename)
            rows.append(
                {
                    "name": info.filename,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        return rows

    def extract(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        base = out_dir.resolve()
        for info in self.zip.infolist():
            rel = Path(info.filename.replace("\\", "/"))
            target = (base / rel).resolve()
            if base != target and base not in target.parents:
                raise FpmError(f"Unsafe archive path rejected: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read(info.filename))


def parse_header_dat(data: bytes) -> dict[str, Any]:
    r = BinaryReader(data)
    if r.remaining() < 8:
        raise FpmError("header.dat is too small to contain major/minor version longs.")
    return {
        "major": r.i32("header major version"),
        "minor": r.i32("header minor version"),
        "bytes": len(data),
    }


def _parse_ent_crlf(data: bytes, count: int) -> list[str]:
    r = BinaryReader(data, 4)
    items = [r.crlf_string(f"map.ent entity {i + 1}") for i in range(count)]
    trailing = data[r.offset:]
    if trailing.strip(b"\x00\r\n\t "):
        raise FpmError(
            f"map.ent CRLF parser left {len(trailing)} non-padding byte(s)."
        )
    return items


def _parse_ent_length_prefixed(data: bytes, count: int) -> list[str]:
    r = BinaryReader(data, 4)
    items: list[str] = []
    for i in range(count):
        n = r.u32(f"map.ent string {i + 1} length")
        if n > r.remaining() or n > 1024 * 1024:
            raise FpmError(f"Implausible map.ent string length {n} at index {i + 1}.")
        raw = data[r.offset : r.offset + n]
        r.offset += n
        items.append(raw.rstrip(b"\x00").decode("utf-8", errors="replace"))
    return items


def parse_map_ent(data: bytes) -> dict[str, Any]:
    if len(data) < 4:
        raise FpmError("map.ent is too small.")
    count = struct.unpack_from("<i", data, 0)[0]
    if count < 0 or count > 1_000_000:
        raise FpmError(f"Implausible map.ent entity-bank count: {count}")

    errors: list[str] = []
    for mode, parser in (
        ("crlf", _parse_ent_crlf),
        ("length-prefixed-fallback", _parse_ent_length_prefixed),
    ):
        try:
            items = parser(data, count)
            return {
                "count": count,
                "encoding": mode,
                "entries": [
                    {"bankindex": i + 1, "path": value}
                    for i, value in enumerate(items)
                ],
                "bytes": len(data),
            }
        except FpmError as exc:
            errors.append(f"{mode}: {exc}")
    raise FpmError("Unable to decode map.ent. " + " | ".join(errors))


def parse_ele_header(data: bytes) -> dict[str, Any]:
    r = BinaryReader(data)
    version_or_count = r.i32("map.ele version/count")
    if version_or_count < 100:
        return {
            "version": 100,
            "legacy_preversion": True,
            "entity_count": version_or_count,
            "header_bytes": 4,
            "bytes": len(data),
        }
    count = r.i32("map.ele entity count")
    if count < 0 or count > 10_000_000:
        raise FpmError(f"Implausible map.ele entity count: {count}")
    return {
        "version": version_or_count,
        "legacy_preversion": False,
        "entity_count": count,
        "header_bytes": 8,
        "bytes": len(data),
    }


def _checked_count(value: int, label: str, maximum: int) -> int:
    if value < 0 or value > maximum:
        raise FpmError(f"Implausible {label}: {value}")
    return value


def _parse_material_slot(r: BinaryReader, label: str) -> None:
    r.skip_i32(4, f"{label} flags")
    r.skip_strings(2, f"{label} colors")
    r.skip_f32(1, f"{label} reflectance")
    r.skip_strings(6, f"{label} textures")
    r.skip_f32(5, f"{label} scalar settings")


def parse_ele_record(
    r: BinaryReader,
    version: int,
    record_index: int,
    bank: list[dict[str, Any]],
) -> dict[str, Any]:
    start = r.offset
    result: dict[str, Any] = {
        "record_index": record_index,
        "record_start_offset": start,
        "maintype": r.i32(f"entity {record_index} maintype"),
        "bankindex": r.i32(f"entity {record_index} bankindex"),
        "staticflag": r.i32(f"entity {record_index} staticflag"),
        "position": {
            "x": r.f32(f"entity {record_index} x"),
            "y": r.f32(f"entity {record_index} y"),
            "z": r.f32(f"entity {record_index} z"),
        },
        "rotation_euler": {
            "x": r.f32(f"entity {record_index} rx"),
            "y": r.f32(f"entity {record_index} ry"),
            "z": r.f32(f"entity {record_index} rz"),
        },
        "name": r.crlf_string(f"entity {record_index} name"),
    }

    # Version 101 base record.
    r.crlf_string(f"entity {record_index} legacy aiinit")
    result["aimain"] = r.crlf_string(f"entity {record_index} aimain")
    r.crlf_string(f"entity {record_index} legacy aidestroy")
    result["isobjective"] = r.i32(f"entity {record_index} isobjective")
    r.skip_strings(3, f"entity {record_index} use/ifused strings")
    r.skip_i32(1, f"entity {record_index} uniqueelement")
    r.skip_strings(3, f"entity {record_index} texture/effect strings")
    r.skip_i32(2, f"entity {record_index} transparency/editorfixed")
    r.skip_strings(2, f"entity {record_index} soundset strings")
    r.skip_i32(7, f"entity {record_index} spawn/render/speed")
    r.skip_strings(1, f"entity {record_index} legacy aishoot")
    r.crlf_string(f"entity {record_index} hasweapon")
    r.skip_i32(4, f"entity {record_index} lives/spawn runtime")
    result["profile_scale"] = r.f32(f"entity {record_index} profile scale")
    r.skip_f32(2, f"entity {record_index} cone fields")
    r.skip_i32(9, f"entity {record_index} strength/light/trigger")
    r.skip_strings(1, f"entity {record_index} legacy basedecal")

    if version >= 102:
        r.skip_i32(6, f"entity {record_index} v102 weapon")
        r.skip_f32(2, f"entity {record_index} v102 throw")
        r.skip_i32(12, f"entity {record_index} v102 spawn/flags")
    if version >= 103:
        r.skip_i32(9, f"entity {record_index} v103 physics")
    if version >= 104:
        r.skip_i32(1, f"entity {record_index} v104 phyalways")
    if version >= 105:
        r.skip_i32(6, f"entity {record_index} v105 random spawn")
    if version >= 106:
        r.skip_i32(2, f"entity {record_index} v106 spawn lifecycle")
    if version >= 107:
        r.skip_i32(1, f"entity {record_index} v107 light index")
    if version >= 199:
        r.skip_i32(17, f"entity {record_index} v199 placeholders")
    if version >= 200:
        r.skip_i32(6, f"entity {record_index} v200 placeholders")
    if version >= 217:
        r.skip_i32(17, f"entity {record_index} v217 particle")
    if version >= 218:
        r.skip_i32(1, f"entity {record_index} v218 particle animated")
    if version >= 301:
        r.skip_strings(4, f"entity {record_index} v301 AI names")
    if version >= 303:
        r.skip_i32(1, f"entity {record_index} v303 animspeed")
    if version >= 304:
        r.skip_f32(1, f"entity {record_index} v304 conerange")
    if version >= 305:
        result["scale_xyz"] = {
            "x": r.f32(f"entity {record_index} scalex"),
            "y": r.f32(f"entity {record_index} scaley"),
            "z": r.f32(f"entity {record_index} scalez"),
        }
        r.skip_i32(2, f"entity {record_index} v305 range/dropoff")
    if version >= 306:
        r.skip_i32(1, f"entity {record_index} v306 violent")
    if version >= 307:
        r.skip_i32(1, f"entity {record_index} v307 explodeheight")
    if version >= 308:
        r.skip_i32(1, f"entity {record_index} v308 spotlighting")
    if version >= 309:
        r.skip_i32(1, f"entity {record_index} v309 lodmodifier")
    if version >= 310:
        r.skip_i32(5, f"entity {record_index} v310 occlusion/parent")
        r.skip_strings(3, f"entity {record_index} v310 soundsets")
    if version >= 311:
        r.skip_f32(1, f"entity {record_index} v311 lootpercentage")
    if version >= 312:
        r.skip_i32(1, f"entity {record_index} v312 parent index")
    if version >= 313:
        r.skip_strings(1, f"entity {record_index} v313 voiceset")
        r.skip_i32(1, f"entity {record_index} v313 voicerate")
    if version >= 314:
        r.skip_i32(6, f"entity {record_index} v314 material flags")
        r.skip_strings(2, f"entity {record_index} v314 material colors")
        r.skip_f32(1, f"entity {record_index} v314 reflectance")
        r.skip_i32(1, f"entity {record_index} v314 material reserved")
        r.skip_strings(6, f"entity {record_index} v314 textures")
        r.skip_f32(5, f"entity {record_index} v314 material scalars")
    if version >= 315:
        r.skip_i32(1, f"entity {record_index} v315 light probe")
    if version >= 316:
        r.skip_i32(7, f"entity {record_index} v316 relationship header")
        r.skip_f32(2, f"entity {record_index} v316 ranges")
        for rel in range(10):
            r.skip_f32(1, f"entity {record_index} v316 relation {rel} data")
            r.skip_i32(3, f"entity {record_index} v316 relation {rel} ids")
    if version >= 317:
        for slot in range(1, MAX_MESH_MATERIALS):
            _parse_material_slot(r, f"entity {record_index} v317 material {slot}")
    if version >= 318:
        r.skip_f32(MAX_MESH_MATERIALS, f"entity {record_index} v318 render bias")
    if version >= 319:
        result["v319_unique_group_id"] = r.i32(
            f"entity {record_index} v319 unique group id"
        )
        group_count = _checked_count(
            r.i32(f"entity {record_index} v319 group count"),
            f"entity {record_index} v319 group count",
            10_000,
        )
        result["v319_group_count"] = group_count
        if record_index == 1:
            for gi in range(group_count):
                item_count = _checked_count(
                    r.i32(f"entity 1 v319 group {gi} item count"),
                    f"entity 1 v319 group {gi} item count",
                    1_000_000,
                )
                for item in range(item_count):
                    r.skip_i32(3, f"entity 1 v319 group {gi} item {item} ids")
                    r.skip_f32(7, f"entity 1 v319 group {gi} item {item} transform")
            r.skip_i32(group_count, "entity 1 v319 group image flags")
        elif group_count != 0:
            raise FpmError(
                f"Entity {record_index} has non-zero v319 group count {group_count}; "
                "current MAX writes the group table only on entity 1."
            )
    if version >= 320:
        r.skip_i32(4, f"entity {record_index} v320 particle flags")
        r.skip_f32(3, f"entity {record_index} v320 transition timing")
        r.skip_strings(1, f"entity {record_index} v320 transition")
        r.skip_f32(2, f"entity {record_index} v320 speed/opacity")
    if version >= 321:
        r.skip_strings(1, f"entity {record_index} v321 emitter")
    if version >= 322:
        r.skip_f32(2, f"entity {record_index} v322 decal")
    if version >= 323:
        r.skip_i32(1, f"entity {record_index} v323 collision override")
    if version >= 324:
        r.skip_f32(2, f"entity {record_index} v324 damage multipliers")
    if version >= 325:
        r.skip_i32(3, f"entity {record_index} v325 movement/gravity")
    if version >= 326:
        r.skip_i32(1, f"entity {record_index} v326 spot radius")
    if version >= 327:
        r.skip_strings(2, f"entity {record_index} v327 soundsets")
    if version >= 328:
        r.skip_i32(1, f"entity {record_index} v328 sound variants")
    if version >= 329:
        result["quaternion"] = {
            "mode": r.f32(f"entity {record_index} quatmode"),
            "x": r.f32(f"entity {record_index} quatx"),
            "y": r.f32(f"entity {record_index} quaty"),
            "z": r.f32(f"entity {record_index} quatz"),
            "w": r.f32(f"entity {record_index} quatw"),
        }
    if version >= 330:
        r.skip_f32(1, f"entity {record_index} v330 autoflatten")
    if version >= 331:
        r.skip_strings(1, f"entity {record_index} v331 override anim set")
    if version >= 332:
        r.skip_i32(1, f"entity {record_index} v332 collectable")
    if version >= 333:
        r.skip_i32(1, f"entity {record_index} v333 swim speed")
    if version >= 334:
        group_name_count = _checked_count(
            r.i32(f"entity {record_index} v334 group name count"),
            f"entity {record_index} v334 group name count",
            10_000,
        )
        result["v334_group_name_count"] = group_name_count
        r.skip_strings(group_name_count, f"entity {record_index} v334 group names")
    if version >= 335:
        result["creation_of_group_id"] = r.i32(
            f"entity {record_index} v335 creationOfGroupID"
        )
    if version >= 336:
        r.skip_i32(3, f"entity {record_index} v336 probe xyz")
    if version >= 337:
        r.skip_i32(1, f"entity {record_index} v337 underwater")
    if version >= 338:
        r.skip_i32(3, f"entity {record_index} v338 weapon fields")
    if version >= 339:
        r.skip_i32(1, f"entity {record_index} v339 shader id")
        r.skip_f32(7, f"entity {record_index} v339 shader params")
        r.skip_strings(1, f"entity {record_index} v339 decal name")
    if version >= 340:
        r.skip_strings(1, f"entity {record_index} v340 effect")
        r.skip_f32(1, f"entity {record_index} v340 probe brightness")
        r.skip_i32(2, f"entity {record_index} v340 bullet/material sound")
        r.skip_f32(2, f"entity {record_index} v340 fillers")
        r.skip_i32(3, f"entity {record_index} v340 project flags")
        r.skip_strings(3, f"entity {record_index} v340 filler strings")
    if version >= 341:
        r.skip_i32(1, f"entity {record_index} v341 FPE settings")
    if version >= 342:
        r.skip_strings(1, f"entity {record_index} v342 soundset4a")

    result["record_end_offset"] = r.offset
    result["record_bytes"] = r.offset - start
    result["record_sha256"] = hashlib.sha256(r.data[start:r.offset]).hexdigest()

    idx = result["bankindex"]
    if 1 <= idx <= len(bank):
        result["asset"] = bank[idx - 1]["path"]
    else:
        result["asset"] = None
        result["bankindex_warning"] = (
            f"bankindex {idx} is outside map.ent range 1..{len(bank)}"
        )

    transform_values = list(result["position"].values()) + list(
        result["rotation_euler"].values()
    )
    if "scale_xyz" in result:
        transform_values.extend(result["scale_xyz"].values())
    if not all(math.isfinite(v) for v in transform_values):
        result["transform_warning"] = "Non-finite transform value detected."
    return result


def parse_map_ele(data: bytes, bank: list[dict[str, Any]]) -> dict[str, Any]:
    header = parse_ele_header(data)
    if header["legacy_preversion"]:
        raise FpmError("Pre-version ELE files are not supported by safe traversal.")
    version = header["version"]
    if version < 101 or version > EXPECTED_ELE_VERSION:
        raise FpmError(
            f"ELE version {version} is outside supported range 101..{EXPECTED_ELE_VERSION}."
        )

    r = BinaryReader(data, header["header_bytes"])
    entities: list[dict[str, Any]] = []
    for index in range(1, header["entity_count"] + 1):
        try:
            entities.append(parse_ele_record(r, version, index, bank))
        except FpmError as exc:
            raise FpmError(
                f"map.ele traversal failed in entity {index} near offset "
                f"0x{r.offset:X}: {exc}"
            ) from exc

    trailing = len(data) - r.offset
    if trailing != 0:
        trailer = data[r.offset : r.offset + min(trailing, 32)].hex(" ")
        raise FpmError(
            f"map.ele schema consumed {r.offset} of {len(data)} bytes; "
            f"{trailing} trailing byte(s) remain at 0x{r.offset:X}. "
            f"Trailer begins: {trailer}"
        )

    return {
        **header,
        "expected_current_version": EXPECTED_ELE_VERSION,
        "version_matches_current_source": version == EXPECTED_ELE_VERSION,
        "fully_traversed": True,
        "parsed_bytes": r.offset,
        "trailing_bytes": 0,
        "entities": entities,
    }


def inspect_fpm(path: Path) -> dict[str, Any]:
    with FpmArchive(path) as fpm:
        names_lower = {n.replace("\\", "/").lower() for n in fpm.names()}
        required = {"header.dat", "map.ent", "map.ele"}
        missing = sorted(required - names_lower)
        if missing:
            raise FpmError("Required FPM members missing: " + ", ".join(missing))

        header = parse_header_dat(fpm.read("header.dat"))
        ent = parse_map_ent(fpm.read("map.ent"))
        ele = parse_map_ele(fpm.read("map.ele"), ent["entries"])
        archive_rows = fpm.archive_rows()

        return {
            "fpm": str(path),
            "archive": {
                "member_count": len(archive_rows),
                "encrypted_member_count": sum(
                    1 for row in archive_rows if row["encrypted"]
                ),
                "members": archive_rows,
            },
            "header_dat": header,
            "map_ent": ent,
            "map_ele": ele,
        }


def print_human(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - GameGuru MAX FPM inspector")
    print(f"FPM: {report['fpm']}")
    print()
    archive = report["archive"]
    print(
        f"Archive: {archive['member_count']} member(s), "
        f"{archive['encrypted_member_count']} encrypted"
    )
    h = report["header_dat"]
    print(f"header.dat: version {h['major']}.{h['minor']} ({h['bytes']} bytes)")
    ent = report["map_ent"]
    print(
        f"map.ent: {ent['count']} entity-bank entrie(s), "
        f"string mode={ent['encoding']}"
    )
    ele = report["map_ele"]
    marker = "PASS" if ele["version_matches_current_source"] else "WARN"
    print(
        f"map.ele: version {ele['version']}, {ele['entity_count']} placed element(s) "
        f"[{marker}: current source={ele['expected_current_version']}]"
    )
    print(
        f"Traversal: PASS - {ele['parsed_bytes']} / {ele['bytes']} bytes, "
        f"trailing={ele['trailing_bytes']}"
    )

    entities = ele["entities"]
    if entities:
        print()
        print("Placed entity summary (first 12):")
        for e in entities[:12]:
            p = e["position"]
            rot = e["rotation_euler"]
            asset = e.get("asset") or "<unresolved>"
            print(
                f"  #{e['record_index']:>4} bank={e['bankindex']:<4} "
                f"pos=({p['x']:.1f},{p['y']:.1f},{p['z']:.1f}) "
                f"rot=({rot['x']:.1f},{rot['y']:.1f},{rot['z']:.1f}) "
                f"{asset}"
            )
        if len(entities) > 12:
            print(f"  ... {len(entities) - 12} more; use --json for every record")


def cmd_inspect(args: argparse.Namespace) -> int:
    report = inspect_fpm(Path(args.fpm))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_human(report)
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    path = Path(args.fpm)
    with FpmArchive(path) as fpm:
        payload = {"fpm": str(path), "members": fpm.member_manifest()}
    print(json.dumps(payload, indent=2))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    path = Path(args.fpm)
    out = Path(args.output)
    with FpmArchive(path) as fpm:
        fpm.extract(out)
    print(f"Extracted {path} -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only GameGuru MAX FPM archive and ELE v342 inspector."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="Inspect archive and fully traverse map.ele.")
    p.add_argument("fpm")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("manifest", help="SHA-256 every decrypted archive member.")
    p.add_argument("fpm")
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("extract", help="Decrypt/extract all archive members.")
    p.add_argument("fpm")
    p.add_argument("output")
    p.set_defaults(func=cmd_extract)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return int(args.func(args))
    except (FpmError, zipfile.BadZipFile, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
