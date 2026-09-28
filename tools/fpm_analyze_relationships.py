#!/usr/bin/env python3
"""Inspect GameGuru MAX v316 relationship data in one or two FPM files.

This tool exists for reverse-engineering *native editor-authored* relationships such
as Character -> Flag -> Flag patrol graphs.  It is deliberately read-only and does
not assign semantics to the v316 fields until a manually-authored MAX reference map
proves them.

Typical workflow:

  python tools/fpm_analyze_relationships.py baseline.fpm reference-with-flags.fpm \
      --report-json build/flag-relationship-diff.json

The second map should be a copy of the baseline saved by GameGuru MAX after adding a
small native patrol graph in Visual Logic.  The report highlights new entities and
records whose v316 relationship payload changed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from fpm_inspect import BinaryReader, FpmArchive, FpmError, parse_map_ele, parse_map_ent

RELATION_SLOT_COUNT = 10
RELATION_PAYLOAD_BYTES = 7 * 4 + 2 * 4 + RELATION_SLOT_COUNT * (4 + 3 * 4)


def _skip_to_v316(raw: bytes, version: int, record_index: int) -> tuple[BinaryReader, int]:
    """Mirror the ELE reader only through the v316 relationship payload.

    Keeping this separate from the canonical parser lets us inspect the currently
    opaque relationship fields without changing production parsing semantics.
    """
    r = BinaryReader(raw)

    # Fixed record prefix through version 101.
    r.skip_i32(3, f"entity {record_index} maintype/bank/static")
    r.skip_f32(6, f"entity {record_index} transform")
    r.crlf_string(f"entity {record_index} name")
    r.skip_strings(3, f"entity {record_index} legacy ai strings")
    r.skip_i32(1, f"entity {record_index} isobjective")
    r.skip_strings(3, f"entity {record_index} use/ifused strings")
    r.skip_i32(1, f"entity {record_index} uniqueelement")
    r.skip_strings(3, f"entity {record_index} texture/effect strings")
    r.skip_i32(2, f"entity {record_index} transparency/editorfixed")
    r.skip_strings(2, f"entity {record_index} soundset strings")
    r.skip_i32(7, f"entity {record_index} spawn/render/speed")
    r.skip_strings(1, f"entity {record_index} legacy aishoot")
    r.crlf_string(f"entity {record_index} hasweapon")
    r.skip_i32(4, f"entity {record_index} lives/spawn runtime")
    r.skip_f32(3, f"entity {record_index} scale/cone fields")
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
        r.skip_f32(3, f"entity {record_index} v305 scale xyz")
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

    return r, r.offset


def relationship_payload(raw: bytes, version: int, record_index: int) -> dict[str, Any] | None:
    if version < 316:
        return None
    r, start = _skip_to_v316(raw, version, record_index)
    header = [r.i32(f"entity {record_index} v316 header[{i}]") for i in range(7)]
    ranges = [r.f32(f"entity {record_index} v316 range[{i}]") for i in range(2)]
    slots = []
    for i in range(RELATION_SLOT_COUNT):
        value = r.f32(f"entity {record_index} v316 relation {i} value")
        ids = [r.i32(f"entity {record_index} v316 relation {i} id[{j}]") for j in range(3)]
        slots.append({"slot": i, "value": value, "ids": ids})
    end = r.offset
    if end - start != RELATION_PAYLOAD_BYTES:
        raise FpmError(
            f"Unexpected v316 payload size for entity {record_index}: {end-start} "
            f"(expected {RELATION_PAYLOAD_BYTES})"
        )
    return {
        "offset": start,
        "bytes": end - start,
        "raw_hex": raw[start:end].hex(),
        "header_i32": header,
        "ranges_f32": ranges,
        "slots": slots,
    }


def _interesting(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    if any(payload["header_i32"]):
        return True
    if any(abs(v) > 1e-6 for v in payload["ranges_f32"] if math.isfinite(v)):
        return True
    for slot in payload["slots"]:
        if any(slot["ids"]) or abs(slot["value"]) > 1e-6:
            return True
    return False


def inspect_fpm(path: Path, include_all: bool = False) -> dict[str, Any]:
    with FpmArchive(path) as archive:
        ent = parse_map_ent(archive.read("map.ent"))
        ele = archive.read("map.ele")
        parsed = parse_map_ele(ele, ent["entries"])

    rows = []
    for entity in parsed["entities"]:
        raw = ele[entity["record_start_offset"] : entity["record_end_offset"]]
        rel = relationship_payload(raw, parsed["version"], entity["record_index"])
        if include_all or _interesting(rel):
            rows.append(
                {
                    "record_index": entity["record_index"],
                    "name": entity.get("name"),
                    "asset": entity.get("asset"),
                    "aimain": entity.get("aimain"),
                    "position": entity.get("position"),
                    "relationship": rel,
                }
            )
    return {
        "fpm": str(path.resolve()),
        "version": parsed["version"],
        "entity_count": parsed["entity_count"],
        "interesting_entity_count": len(rows),
        "entities": rows,
    }


def _entity_map(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(row["record_index"]): row for row in report["entities"]}


def compare_reports(base: dict[str, Any], reference: dict[str, Any], include_all: bool) -> dict[str, Any]:
    # For a clean capture, the manually edited map should preserve the baseline
    # prefix and append only the character/flag reference entities.  We still
    # compare by record index and make no stronger assumption than that.
    b = _entity_map(base)
    r = _entity_map(reference)
    changed = []
    for index in sorted(set(b) | set(r)):
        left = b.get(index)
        right = r.get(index)
        if left is None:
            changed.append({"kind": "new", "record_index": index, "reference": right})
            continue
        if right is None:
            changed.append({"kind": "missing", "record_index": index, "baseline": left})
            continue
        lrel = left.get("relationship")
        rrel = right.get("relationship")
        if lrel != rrel or left.get("name") != right.get("name") or left.get("asset") != right.get("asset"):
            changed.append(
                {
                    "kind": "changed",
                    "record_index": index,
                    "baseline": left,
                    "reference": right,
                }
            )
    if not include_all:
        # Include appended records even if their v316 payload happens to be zero so
        # flag asset/name/marker evidence is not hidden.
        base_count = int(base["entity_count"])
        known = {row["record_index"] for row in changed}
        for row in reference["entities"]:
            if row["record_index"] > base_count and row["record_index"] not in known:
                changed.append({"kind": "new", "record_index": row["record_index"], "reference": row})
        changed.sort(key=lambda row: row["record_index"])
    return {
        "baseline": base["fpm"],
        "reference": reference["fpm"],
        "baseline_entity_count": base["entity_count"],
        "reference_entity_count": reference["entity_count"],
        "entity_count_delta": int(reference["entity_count"]) - int(base["entity_count"]),
        "changed_record_count": len(changed),
        "changed_records": changed,
    }


def print_single(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - GameGuru MAX v316 relationship inspection")
    print(f"FPM: {report['fpm']}")
    print(f"ELE v{report['version']} | entities={report['entity_count']} | relationship rows={report['interesting_entity_count']}")
    for row in report["entities"]:
        rel = row.get("relationship") or {}
        active = [slot for slot in rel.get("slots", []) if any(slot["ids"]) or abs(slot["value"]) > 1e-6]
        print(
            f"  #{row['record_index']} {row.get('name')!r} asset={row.get('asset')!r} "
            f"aimain={row.get('aimain')!r} header={rel.get('header_i32')} ranges={rel.get('ranges_f32')}"
        )
        for slot in active:
            print(f"      slot {slot['slot']}: value={slot['value']:.6g} ids={slot['ids']}")


def print_diff(diff: dict[str, Any]) -> None:
    print("BLACK SIGNAL - native MAX relationship capture diff")
    print(f"Baseline:  {diff['baseline']}")
    print(f"Reference: {diff['reference']}")
    print(
        f"Entities: {diff['baseline_entity_count']} -> {diff['reference_entity_count']} "
        f"(delta {diff['entity_count_delta']:+d})"
    )
    print(f"Changed/new relationship records: {diff['changed_record_count']}")
    for row in diff["changed_records"]:
        side = row.get("reference") or row.get("baseline") or {}
        rel = side.get("relationship") or {}
        active = [slot for slot in rel.get("slots", []) if any(slot["ids"]) or abs(slot["value"]) > 1e-6]
        print(
            f"  {row['kind'].upper():7s} #{row['record_index']} {side.get('name')!r} "
            f"asset={side.get('asset')!r} aimain={side.get('aimain')!r} "
            f"header={rel.get('header_i32')} ranges={rel.get('ranges_f32')}"
        )
        for slot in active:
            print(f"      slot {slot['slot']}: value={slot['value']:.6g} ids={slot['ids']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Baseline FPM, or the only FPM when no reference is supplied")
    parser.add_argument("reference", type=Path, nargs="?", help="MAX-saved copy containing native Character/Flag links")
    parser.add_argument("--all", action="store_true", help="Include entities whose v316 payload appears empty")
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()

    try:
        base = inspect_fpm(args.baseline, include_all=args.all)
        if args.reference:
            ref = inspect_fpm(args.reference, include_all=True)
            report = {
                "baseline_report": base,
                "reference_report": ref if args.all else {
                    **ref,
                    "entities": [row for row in ref["entities"] if _interesting(row.get("relationship")) or row["record_index"] > base["entity_count"]],
                },
                "diff": compare_reports(base, ref, include_all=args.all),
            }
            print_diff(report["diff"])
        else:
            report = base
            print_single(report)

        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0
    except (FpmError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RELATIONSHIP ANALYSIS ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
