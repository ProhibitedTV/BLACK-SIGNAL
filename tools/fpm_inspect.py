#!/usr/bin/env python3
"""Read-only GameGuru MAX FPM inspection utilities.

BLACK SIGNAL uses this as the first safety gate before any direct FPM authoring.
The current GameGuru MAX source shows FPM files are ZIP containers whose members
are encrypted with the password ``mypassword``.  This tool deliberately does not
write or repack FPM files yet.

It can:
- list/archive-inspect an FPM without extracting it;
- read header.dat version fields;
- decode map.ent's entity-bank strings;
- decode the stable placement prefix of the first map.ele entity record;
- extract archive members for offline analysis;
- emit a SHA-256 member manifest so round-trip experiments can prove that
  unrelated level data stayed byte-identical.

The map.ele serializer is versioned and large.  We intentionally stop after the
stable v101 record prefix until the complete v342 schema is implemented and
validated against a real MAX-produced level.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

FPM_PASSWORD = b"mypassword"
EXPECTED_ELE_VERSION = 342


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

    def crlf_string(self, label: str, allow_lf: bool = True) -> str:
        start = self.offset
        crlf = self.data.find(b"\r\n", start)
        lf = self.data.find(b"\n", start) if allow_lf else -1
        if crlf >= 0 and (lf < 0 or crlf <= lf):
            end = crlf
            self.offset = crlf + 2
        elif lf >= 0:
            end = lf
            self.offset = lf + 1
        else:
            raise FpmError(
                f"Could not find CRLF/LF terminator for {label} starting at "
                f"offset 0x{start:X}."
            )
        raw = self.data[start:end]
        return raw.decode("utf-8", errors="replace")


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
        rows: list[dict[str, Any]] = []
        for info in self.zip.infolist():
            rows.append(
                {
                    "name": info.filename,
                    "compressed_bytes": info.compress_size,
                    "uncompressed_bytes": info.file_size,
                    "encrypted": bool(info.flag_bits & 0x1),
                    "compression": info.compress_type,
                    "crc32": f"{info.CRC:08x}",
                }
            )
        return rows

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
    """Fallback for historical/variant DBPro string serialization.

    Current MAX builds are expected to use line strings here, but this fallback
    keeps the inspector diagnostic rather than destructive if a legacy FPM is
    encountered.
    """
    r = BinaryReader(data, 4)
    items: list[str] = []
    for i in range(count):
        n = r.u32(f"map.ent string {i + 1} length")
        if n > r.remaining() or n > 1024 * 1024:
            raise FpmError(f"Implausible map.ent string length {n} at index {i + 1}.")
        raw = data[r.offset : r.offset + n]
        r.offset += n
        raw = raw.rstrip(b"\x00")
        items.append(raw.decode("utf-8", errors="replace"))
    return items


def parse_map_ent(data: bytes) -> dict[str, Any]:
    if len(data) < 4:
        raise FpmError("map.ent is too small.")
    count = struct.unpack_from("<i", data, 0)[0]
    if count < 0 or count > 1_000_000:
        raise FpmError(f"Implausible map.ent entity-bank count: {count}")

    parsers = (
        ("crlf", _parse_ent_crlf),
        ("length-prefixed-fallback", _parse_ent_length_prefixed),
    )
    errors: list[str] = []
    for mode, parser in parsers:
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


def parse_first_ele_prefix(data: bytes, bank: list[dict[str, Any]]) -> dict[str, Any] | None:
    header = parse_ele_header(data)
    if header["entity_count"] <= 0:
        return None
    if header["version"] < 101:
        raise FpmError("Cannot decode entity placement prefix for ELE versions below 101.")

    r = BinaryReader(data, header["header_bytes"])
    start = r.offset
    result: dict[str, Any] = {
        "record_index": 1,
        "record_start_offset": start,
        "maintype": r.i32("entity maintype"),
        "bankindex": r.i32("entity bankindex"),
        "staticflag": r.i32("entity staticflag"),
        "position": {
            "x": r.f32("entity x"),
            "y": r.f32("entity y"),
            "z": r.f32("entity z"),
        },
        "rotation_euler": {
            "x": r.f32("entity rx"),
            "y": r.f32("entity ry"),
            "z": r.f32("entity rz"),
        },
        "name": r.crlf_string("entity name"),
        "legacy_aiinit": r.crlf_string("legacy aiinit"),
        "aimain": r.crlf_string("entity aimain"),
        "legacy_aidestroy": r.crlf_string("legacy aidestroy"),
        "isobjective": r.i32("entity isobjective"),
    }
    result["prefix_end_offset"] = r.offset

    idx = result["bankindex"]
    if 1 <= idx <= len(bank):
        result["asset"] = bank[idx - 1]["path"]
    else:
        result["asset"] = None
        result["bankindex_warning"] = (
            f"bankindex {idx} is outside map.ent range 1..{len(bank)}"
        )

    floats = list(result["position"].values()) + list(result["rotation_euler"].values())
    if not all(math.isfinite(v) for v in floats):
        result["transform_warning"] = "Non-finite transform value detected."
    return result


def inspect_fpm(path: Path) -> dict[str, Any]:
    with FpmArchive(path) as fpm:
        names_lower = {n.replace("\\", "/").lower() for n in fpm.names()}
        required = {"header.dat", "map.ent", "map.ele"}
        missing = sorted(required - names_lower)
        if missing:
            raise FpmError("Required FPM members missing: " + ", ".join(missing))

        header = parse_header_dat(fpm.read("header.dat"))
        ent = parse_map_ent(fpm.read("map.ent"))
        ele_data = fpm.read("map.ele")
        ele = parse_ele_header(ele_data)
        first = parse_first_ele_prefix(ele_data, ent["entries"])

        return {
            "fpm": str(path),
            "archive": {
                "member_count": len(fpm.names()),
                "encrypted_member_count": sum(
                    1 for row in fpm.archive_rows() if row["encrypted"]
                ),
                "members": fpm.archive_rows(),
            },
            "header_dat": header,
            "map_ent": ent,
            "map_ele": {
                **ele,
                "expected_current_version": EXPECTED_ELE_VERSION,
                "version_matches_current_source": ele["version"] == EXPECTED_ELE_VERSION,
                "first_entity_prefix": first,
                "scope": (
                    "Read-only v101 placement prefix only. Full v342 record traversal "
                    "is intentionally not implemented yet."
                ),
            },
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
    first = ele["first_entity_prefix"]
    if first:
        p = first["position"]
        rot = first["rotation_euler"]
        print()
        print("First placed entity (stable v101 prefix):")
        print(f"  bankindex: {first['bankindex']}")
        print(f"  asset:     {first.get('asset') or '<unresolved>'}")
        print(f"  name:      {first['name']!r}")
        print(f"  position:  ({p['x']:.3f}, {p['y']:.3f}, {p['z']:.3f})")
        print(f"  rotation:  ({rot['x']:.3f}, {rot['y']:.3f}, {rot['z']:.3f})")
        print(
            f"  byte span decoded: 0x{first['record_start_offset']:X}.."
            f"0x{first['prefix_end_offset']:X}"
        )
    print()
    print(ele["scope"])


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
        payload = {
            "fpm": str(path),
            "members": fpm.member_manifest(),
        }
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
        description="Read-only GameGuru MAX FPM archive and entity-format inspector."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="Inspect archive, map.ent, and ELE header/prefix.")
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
