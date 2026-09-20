#!/usr/bin/env python3
"""Create a controlled BLACK SIGNAL FPM clone test.

This is the first write-capable FPM tool in the project. It deliberately uses a
very narrow mutation strategy:

* decrypt/read an existing GameGuru MAX FPM;
* fully traverse map.ele with fpm_inspect.py;
* prove a byte-identical raw-record round trip;
* select one known-good, ungrouped, static entity record;
* clone that record byte-for-byte;
* patch only the fixed XYZ transform floats in the record prefix;
* increment the map.ele element count;
* preserve every other FPM member payload byte-for-byte;
* write a new traditional ZipCrypto encrypted FPM using GameGuru's password.

No existing FPM is modified in place. The output path must differ from the input.
The initial controlled test intentionally does not change bankindex, scale,
rotation, materials, scripts, grouping, physics, or any other entity property.
"""

from __future__ import annotations

import argparse
import binascii
import datetime as _dt
import hashlib
import os
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from fpm_inspect import (
    FPM_PASSWORD,
    FpmArchive,
    FpmError,
    parse_map_ele,
    parse_map_ent,
)


# Fixed offsets within every ELE v101+ entity record. These are guaranteed by
# the current GameGuru MAX serializer and are intentionally the only bytes the
# controlled clone test mutates.
ELE_MAINTYPE_OFFSET = 0x00
ELE_BANKINDEX_OFFSET = 0x04
ELE_STATICFLAG_OFFSET = 0x08
ELE_X_OFFSET = 0x0C
ELE_Y_OFFSET = 0x10
ELE_Z_OFFSET = 0x14
ELE_RX_OFFSET = 0x18
ELE_RY_OFFSET = 0x1C
ELE_RZ_OFFSET = 0x20


@dataclass
class ArchiveMember:
    name: str
    payload: bytes
    date_time: tuple[int, int, int, int, int, int]
    compress_type: int
    external_attr: int = 0


def _dos_datetime(date_time: tuple[int, int, int, int, int, int]) -> tuple[int, int]:
    year, month, day, hour, minute, second = date_time
    year = min(max(year, 1980), 2107)
    month = min(max(month, 1), 12)
    day = min(max(day, 1), 31)
    hour = min(max(hour, 0), 23)
    minute = min(max(minute, 0), 59)
    second = min(max(second, 0), 59)
    dos_date = ((year - 1980) << 9) | (month << 5) | day
    dos_time = (hour << 11) | (minute << 5) | (second // 2)
    return dos_time, dos_date


def _crc_update(value: int, byte: int) -> int:
    """PKZIP traditional-encryption CRC primitive.

    This is the same state transition used by Python's ZipCrypto decrypter,
    expressed directly so the project can create legacy encrypted ZIP entries
    without requiring a third-party package.
    """
    if not hasattr(_crc_update, "table"):
        table: list[int] = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ (0xEDB88320 if (c & 1) else 0)
            table.append(c & 0xFFFFFFFF)
        setattr(_crc_update, "table", table)
    table = getattr(_crc_update, "table")
    return ((value >> 8) ^ table[(value ^ byte) & 0xFF]) & 0xFFFFFFFF


class _ZipCrypto:
    def __init__(self, password: bytes):
        self.key0 = 0x12345678
        self.key1 = 0x23456789
        self.key2 = 0x34567890
        for byte in password:
            self._update(byte)

    def _update(self, plain_byte: int) -> None:
        self.key0 = _crc_update(self.key0, plain_byte)
        self.key1 = (self.key1 + (self.key0 & 0xFF)) & 0xFFFFFFFF
        self.key1 = (self.key1 * 134775813 + 1) & 0xFFFFFFFF
        self.key2 = _crc_update(self.key2, (self.key1 >> 24) & 0xFF)

    def _mask(self) -> int:
        temp = (self.key2 | 2) & 0xFFFFFFFF
        return ((temp * (temp ^ 1)) >> 8) & 0xFF

    def encrypt(self, plain: bytes) -> bytes:
        out = bytearray(len(plain))
        for i, byte in enumerate(plain):
            out[i] = byte ^ self._mask()
            self._update(byte)
        return bytes(out)


def _compress(payload: bytes, method: int) -> bytes:
    if method == 0:
        return payload
    if method == 8:
        compressor = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=-15)
        return compressor.compress(payload) + compressor.flush()
    raise FpmError(f"Unsupported ZIP compression method {method}; expected stored(0) or deflate(8).")


def _deterministic_crypto_header(name: str, crc32: int) -> bytes:
    # Traditional ZipCrypto uses an arbitrary 11-byte prefix and checks the
    # final byte against the high byte of CRC when bit 3 is clear. A deterministic
    # header keeps test artifacts reproducible without weakening a security
    # boundary; GameGuru's FPM password is a compatibility mechanism, not secrecy.
    seed = hashlib.sha256(name.encode("utf-8") + struct.pack("<I", crc32)).digest()
    return seed[:11] + bytes([(crc32 >> 24) & 0xFF])


def write_zipcrypto_archive(path: Path, members: Iterable[ArchiveMember], password: bytes = FPM_PASSWORD) -> None:
    """Write a conventional encrypted ZIP compatible with GameGuru MAX/minizip."""
    path.parent.mkdir(parents=True, exist_ok=True)
    central_entries: list[bytes] = []
    offset = 0

    with path.open("wb") as fp:
        count = 0
        for member in members:
            count += 1
            name_bytes = member.name.replace("\\", "/").encode("utf-8")
            payload = member.payload
            crc32 = binascii.crc32(payload) & 0xFFFFFFFF
            compressed = _compress(payload, member.compress_type)
            crypto_header = _deterministic_crypto_header(member.name, crc32)
            cipher = _ZipCrypto(password)
            encrypted = cipher.encrypt(crypto_header + compressed)
            compressed_size = len(encrypted)
            dos_time, dos_date = _dos_datetime(member.date_time)
            flags = 0x0001 | 0x0800  # encrypted + UTF-8 names
            version_needed = 20

            local_header = struct.pack(
                "<IHHHHHIIIHH",
                0x04034B50,
                version_needed,
                flags,
                member.compress_type,
                dos_time,
                dos_date,
                crc32,
                compressed_size,
                len(payload),
                len(name_bytes),
                0,
            )
            local_offset = offset
            fp.write(local_header)
            fp.write(name_bytes)
            fp.write(encrypted)
            offset += len(local_header) + len(name_bytes) + len(encrypted)

            central = struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014B50,
                20,  # version made by
                version_needed,
                flags,
                member.compress_type,
                dos_time,
                dos_date,
                crc32,
                compressed_size,
                len(payload),
                len(name_bytes),
                0,  # extra length
                0,  # comment length
                0,  # disk number
                0,  # internal attrs
                member.external_attr,
                local_offset,
            ) + name_bytes
            central_entries.append(central)

        central_offset = offset
        for central in central_entries:
            fp.write(central)
            offset += len(central)
        central_size = offset - central_offset

        if count > 0xFFFF:
            raise FpmError("ZIP64 output is not implemented; too many FPM members.")
        eocd = struct.pack(
            "<IHHHHIIH",
            0x06054B50,
            0,
            0,
            count,
            count,
            central_size,
            central_offset,
            0,
        )
        fp.write(eocd)


def _archive_members(source: FpmArchive, replacement_map_ele: bytes) -> list[ArchiveMember]:
    members: list[ArchiveMember] = []
    for info in source.zip.infolist():
        payload = replacement_map_ele if info.filename.replace("\\", "/").lower() == "map.ele" else source.read(info.filename)
        method = info.compress_type if info.compress_type in (0, 8) else 8
        members.append(
            ArchiveMember(
                name=info.filename,
                payload=payload,
                date_time=info.date_time,
                compress_type=method,
                external_attr=info.external_attr,
            )
        )
    return members


def verify_raw_ele_roundtrip(ele_data: bytes, parsed: dict[str, Any]) -> None:
    """Gate C: prove record boundaries reconstruct the original stream exactly."""
    header_bytes = parsed["header_bytes"]
    rebuilt = bytearray(ele_data[:header_bytes])
    for entity in parsed["entities"]:
        start = entity["record_start_offset"]
        end = entity["record_end_offset"]
        rebuilt += ele_data[start:end]
    if bytes(rebuilt) != ele_data:
        raise FpmError(
            "Gate C failed: concatenating the parsed header and raw entity spans did not "
            "reproduce map.ele byte-for-byte."
        )


def _normalize_asset(value: str | None) -> str:
    return (value or "").replace("/", "\\").lower()


def select_clone_source(parsed: dict[str, Any], asset_query: str, entity_index: int | None = None) -> dict[str, Any]:
    entities = parsed["entities"]
    if entity_index is not None:
        if entity_index < 1 or entity_index > len(entities):
            raise FpmError(f"Entity index {entity_index} is outside 1..{len(entities)}.")
        candidates = [entities[entity_index - 1]]
    else:
        q = asset_query.lower()
        candidates = [e for e in entities if q in _normalize_asset(e.get("asset"))]

    if not candidates:
        raise FpmError(f"No placed entity matches asset query {asset_query!r}.")

    safe: list[dict[str, Any]] = []
    rejected: list[str] = []
    for entity in candidates:
        why: list[str] = []
        if entity["record_index"] == 1:
            why.append("record 1 owns the v319 global group payload")
        if entity.get("staticflag") != 1:
            why.append(f"staticflag={entity.get('staticflag')} (need 1)")
        if entity.get("v319_group_count", 0) != 0:
            why.append("non-zero v319 group payload")
        creation_id = entity.get("creation_of_group_id", -1)
        if creation_id not in (-1, 0):
            why.append(f"creationOfGroupID={creation_id}")
        if why:
            rejected.append(f"#{entity['record_index']}: " + ", ".join(why))
        else:
            safe.append(entity)

    if not safe:
        details = "; ".join(rejected[:8])
        raise FpmError(
            f"Matching entities were found for {asset_query!r}, but none satisfy the "
            f"controlled-clone safety rules. {details}"
        )
    return safe[0]


def clone_ele_record(
    ele_data: bytes,
    parsed: dict[str, Any],
    source_entity: dict[str, Any],
    dx: float,
    dy: float,
    dz: float,
) -> tuple[bytes, dict[str, Any]]:
    if parsed["legacy_preversion"]:
        raise FpmError("Cannot clone pre-version ELE data.")
    if parsed["trailing_bytes"] != 0 or not parsed["traversal_complete"]:
        raise FpmError("Refusing to write because Gate B traversal did not end exactly at EOF.")

    start = source_entity["record_start_offset"]
    end = source_entity["record_end_offset"]
    record = bytearray(ele_data[start:end])
    if len(record) < ELE_RZ_OFFSET + 4:
        raise FpmError("Source entity record is too short to contain the fixed transform prefix.")

    old_pos = source_entity["position"]
    new_pos = {
        "x": float(old_pos["x"] + dx),
        "y": float(old_pos["y"] + dy),
        "z": float(old_pos["z"] + dz),
    }
    struct.pack_into("<f", record, ELE_X_OFFSET, new_pos["x"])
    struct.pack_into("<f", record, ELE_Y_OFFSET, new_pos["y"])
    struct.pack_into("<f", record, ELE_Z_OFFSET, new_pos["z"])

    out = bytearray(ele_data)
    new_count = parsed["entity_count"] + 1
    struct.pack_into("<i", out, 4, new_count)
    out += record

    mutation = {
        "source_record_index": source_entity["record_index"],
        "source_asset": source_entity.get("asset"),
        "source_record_sha256": source_entity["record_sha256"],
        "source_record_bytes": len(record),
        "old_position": old_pos,
        "new_position": new_pos,
        "delta": {"x": dx, "y": dy, "z": dz},
        "old_entity_count": parsed["entity_count"],
        "new_entity_count": new_count,
    }
    return bytes(out), mutation


def build_clone_test(
    source_path: Path,
    output_path: Path,
    asset_query: str,
    dx: float,
    dy: float,
    dz: float,
    entity_index: int | None = None,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise FpmError("Output FPM must differ from the source FPM; in-place writes are forbidden.")

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)

        source_entity = select_clone_source(parsed, asset_query, entity_index)
        new_ele, mutation = clone_ele_record(ele_data, parsed, source_entity, dx, dy, dz)
        members = _archive_members(source, new_ele)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}

    write_zipcrypto_archive(output_path, members)

    # Re-open with the same read path GameGuru-compatible archives use and prove
    # the modified map is structurally valid while all non-ELE payloads match.
    with FpmArchive(output_path) as generated:
        generated_ent = parse_map_ent(generated.read("map.ent"))
        generated_ele_data = generated.read("map.ele")
        generated_parsed = parse_map_ele(generated_ele_data, generated_ent["entries"])
        generated_manifest = {row["name"]: row["sha256"] for row in generated.member_manifest()}

    if generated_parsed["entity_count"] != mutation["new_entity_count"]:
        raise FpmError("Generated FPM entity count did not survive encrypted archive round trip.")
    if generated_parsed["trailing_bytes"] != 0:
        raise FpmError("Generated FPM map.ele has trailing bytes after traversal.")

    changed_members = sorted(
        name for name, sha in generated_manifest.items() if source_manifest.get(name) != sha
    )
    missing_members = sorted(set(source_manifest) - set(generated_manifest))
    extra_members = sorted(set(generated_manifest) - set(source_manifest))
    if missing_members or extra_members:
        raise FpmError(
            f"Archive membership changed unexpectedly. missing={missing_members}, extra={extra_members}"
        )
    if changed_members != [next(name for name in generated_manifest if name.replace('\\', '/').lower() == 'map.ele')]:
        raise FpmError(
            "Generated FPM changed payloads other than map.ele: " + ", ".join(changed_members)
        )

    new_entity = generated_parsed["entities"][-1]
    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "ele_version": parsed["version"],
        "gate_b_traversal": parsed["traversal_complete"] and parsed["trailing_bytes"] == 0,
        "gate_c_byte_identical_raw_roundtrip": True,
        "gate_d_clone": mutation,
        "generated_last_entity": {
            "record_index": new_entity["record_index"],
            "asset": new_entity.get("asset"),
            "position": new_entity["position"],
            "rotation_euler": new_entity["rotation_euler"],
            "staticflag": new_entity["staticflag"],
        },
        "payloads_changed": changed_members,
        "non_ele_payloads_preserved": len(changed_members) == 1,
        "archive_reopen_pass": True,
    }


def _print_report(report: dict[str, Any]) -> None:
    clone = report["gate_d_clone"]
    print("BLACK SIGNAL - controlled FPM raw-clone test")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"ELE version: {report['ele_version']}")
    print()
    print("[PASS] Gate B: full ELE traversal ends exactly at EOF")
    print("[PASS] Gate C: raw record spans rebuild map.ele byte-for-byte")
    print("[PASS] Encrypted output FPM reopens with GameGuru password")
    print("[PASS] Every non-map.ele archive payload is SHA-256 identical")
    print()
    print(
        f"Cloned entity #{clone['source_record_index']} -> #{clone['new_entity_count']} "
        f"({clone['source_asset']})"
    )
    old = clone["old_position"]
    new = clone["new_position"]
    print(f"  old position: ({old['x']:.3f}, {old['y']:.3f}, {old['z']:.3f})")
    print(f"  new position: ({new['x']:.3f}, {new['y']:.3f}, {new['z']:.3f})")
    print(f"  source record bytes preserved: {clone['source_record_bytes']}")
    print("  mutation: element count + XYZ only")
    print()
    print("This is a test artifact. Open the generated FPM directly in MAX; do not overwrite the production map yet.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source GameGuru MAX FPM")
    parser.add_argument("output", type=Path, help="New test FPM output path")
    parser.add_argument(
        "--asset",
        default="CS_Street_Lamp.fpe",
        help="Case-insensitive asset-path substring used to choose a safe clone source",
    )
    parser.add_argument("--entity-index", type=int, default=None, help="Explicit source entity index override")
    parser.add_argument("--dx", type=float, default=1000.0, help="X offset for the clone")
    parser.add_argument("--dy", type=float, default=0.0, help="Y offset for the clone")
    parser.add_argument("--dz", type=float, default=0.0, help="Z offset for the clone")
    args = parser.parse_args(argv)

    try:
        report = build_clone_test(
            args.source,
            args.output,
            args.asset,
            args.dx,
            args.dy,
            args.dz,
            args.entity_index,
        )
        _print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
