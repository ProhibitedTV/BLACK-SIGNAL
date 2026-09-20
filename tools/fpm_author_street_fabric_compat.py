#!/usr/bin/env python3
"""Compatibility entry point for authored District 12 street fabric.

GameGuru MAX ELE v329+ stores quaternion state in a slightly awkward way:
current MAX save code writes ``quatmode`` with WriteFloat even though the field
is an integer in memory, while load code reads the same four bytes with
ReadLong and treats any non-zero value as "quaternion mode active".

Older/re-saved levels can therefore carry very large non-zero numeric values in
the serialized quatmode slot. For BLACK SIGNAL street-fabric clones we only
need orthogonal/yaw Euler rotations, so this wrapper safely normalizes cloned
records to Euler mode instead of rejecting them.
"""

from __future__ import annotations

import struct
import sys

import fpm_author_street_fabric as base
from fpm_inspect import FpmError


def _find_quaternion_span(raw_record: bytes, quaternion: dict[str, float]) -> int:
    """Find the exact 20-byte v329 quaternion payload in a raw record.

    ``fpm_inspect`` decodes all five serialized slots as float32, matching the
    bytes produced by current MAX's writer. Repacking those decoded values lets
    us locate the payload without depending on offsets of earlier variable-size
    fields. Refuse ambiguity rather than patching an uncertain location.
    """

    needle = struct.pack(
        "<5f",
        float(quaternion.get("mode", 0.0)),
        float(quaternion.get("x", 0.0)),
        float(quaternion.get("y", 0.0)),
        float(quaternion.get("z", 0.0)),
        float(quaternion.get("w", 0.0)),
    )
    offsets: list[int] = []
    start = 0
    while True:
        pos = raw_record.find(needle, start)
        if pos < 0:
            break
        offsets.append(pos)
        start = pos + 1

    if len(offsets) != 1:
        raise FpmError(
            "Could not uniquely locate serialized v329 quaternion payload "
            f"inside cloned record (matches={len(offsets)})."
        )
    return offsets[0]


def _patched_patch_record(
    template: base.Template,
    bankindex: int,
    placement: base.Placement,
) -> bytes:
    """Clone a record while forcing authored street pieces into Euler mode."""

    raw = bytearray(template.raw_record)
    entity = template.parsed
    requested_ry = entity["rotation_euler"]["y"] if placement.ry is None else placement.ry

    struct.pack_into("<i", raw, base.ELE_BANKINDEX_OFFSET, bankindex)
    struct.pack_into("<f", raw, base.ELE_X_OFFSET, float(placement.x))
    struct.pack_into("<f", raw, base.ELE_Y_OFFSET, float(placement.y))
    struct.pack_into("<f", raw, base.ELE_Z_OFFSET, float(placement.z))
    struct.pack_into("<f", raw, base.ELE_RX_OFFSET, float(placement.rx))
    struct.pack_into("<f", raw, base.ELE_RY_OFFSET, float(requested_ry))
    struct.pack_into("<f", raw, base.ELE_RZ_OFFSET, float(placement.rz))

    # Street-fabric placements are intentionally Euler/yaw driven. If this ELE
    # version carries v329 quaternion state, explicitly disable quaternion mode
    # so a stale/corrupt non-zero mode cannot override the authored Euler fields.
    # Current MAX writes quatmode through WriteFloat, so 0.0f is the canonical
    # four-byte false value; identity quaternion is retained as benign payload.
    quat = entity.get("quaternion")
    if quat is not None:
        quat_offset = _find_quaternion_span(template.raw_record, quat)
        struct.pack_into("<5f", raw, quat_offset, 0.0, 0.0, 0.0, 0.0, 1.0)

    # A cloned placed entity should not inherit a non-zero unique-element token.
    unique_offset = base.record_uniqueelement_offset(bytes(raw))
    old_unique = struct.unpack_from("<i", raw, unique_offset)[0]
    if old_unique != 0:
        struct.pack_into("<i", raw, unique_offset, 0)

    return bytes(raw)


def main(argv: list[str] | None = None) -> int:
    base.patch_record = _patched_patch_record
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
