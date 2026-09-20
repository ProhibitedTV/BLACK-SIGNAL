#!/usr/bin/env python3
"""Author District 12's baseline street fabric directly into a generated FPM.

This builds on the read-only ELE traversal and raw-record clone work. It never
modifies the source FPM in place. The output is a separate compatibility artifact.

Baseline street fabric authored by this tool:
- yellow double center-line decals on straight road modules;
- crosswalk decals on four-way junction approaches;
- street-lamp meshes on a deterministic curb rhythm;
- GameGuru MAX dynamic street-light markers paired with lamp meshes;
- sidewalk lights;
- sidewalk guards / pedestrian rails;
- crosswalk blocker posts used as bollard/pole stops;
- electrical utility poles.

Template policy:
1. Prefer an exact placed record already in District 12.
2. Otherwise import an exact placed record from a same-ELE-version donor FPM.
3. For ordinary static DLC props only, a generic static target record may be
   reused with a new map.ent bank entry. This is explicitly reported as an
   experimental static-bank import and is never used for dynamic light markers.

Dynamic light markers require an exact same-version record because their light
state must remain engine-authored. If no donor record can be found, generation
fails rather than silently creating a fake light.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from fpm_inspect import BinaryReader, FpmArchive, FpmError, parse_map_ele, parse_map_ent
from fpm_clone_entity import ArchiveMember, verify_raw_ele_roundtrip, write_zipcrypto_archive


# Fixed placement-prefix offsets in every ELE v101+ record.
ELE_BANKINDEX_OFFSET = 0x04
ELE_X_OFFSET = 0x0C
ELE_Y_OFFSET = 0x10
ELE_Z_OFFSET = 0x14
ELE_RX_OFFSET = 0x18
ELE_RY_OFFSET = 0x1C
ELE_RZ_OFFSET = 0x20

# The pack scan on the BLACK SIGNAL workstation confirmed these exact assets.
ASSETS: dict[str, dict[str, Any]] = {
    "road_center_yellow": {
        "basename": "CS_Street_Double_Center_Line.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Double_Center_Line.fpe",
        "dynamic": False,
    },
    "crosswalk": {
        "basename": "CS_Street_Crosswalk_Decal.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Street Decals\CS_Street_Crosswalk_Decal.fpe",
        "dynamic": False,
    },
    "street_lamp": {
        "basename": "CS_Street_Lamp.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Street_Lamp.fpe",
        "dynamic": False,
    },
    "street_dynamic_light": {
        "basename": "CS_Street_Light_Marker.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Light_Marker.fpe",
        "dynamic": True,
    },
    "sidewalk_light": {
        "basename": "CS_Sidewalk_Light.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Sidewalk_Light.fpe",
        "dynamic": False,
    },
    "curb_guard": {
        "basename": "CS_Sidewalk_Guard.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Sidewalk_Guard.fpe",
        "dynamic": False,
    },
    "bollard_stop": {
        "basename": "CS_Street_Crosswalk_Metal_Blocker_Post.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Streets and Sidewalks\Streets\CS_Street_Crosswalk_Metal_Blocker_Post.fpe",
        "dynamic": False,
    },
    "utility_pole": {
        "basename": "CS_Street_Electrical_Pole_01.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Street_Electrical_Pole_01.fpe",
        "dynamic": False,
    },
    "plastic_divider": {
        "basename": "CS_Plastic_Divider_1.fpe",
        "path": r"Cyberpunk Streets Booster Pack\Misc\Sidewalk Misc\CS_Plastic_Divider_1.fpe",
        "dynamic": False,
        "optional": True,
    },
}

REQUIRED_ROLES = [
    "road_center_yellow",
    "crosswalk",
    "street_lamp",
    "street_dynamic_light",
    "sidewalk_light",
    "curb_guard",
    "bollard_stop",
    "utility_pole",
]


@dataclass
class Template:
    role: str
    asset_path: str
    parsed: dict[str, Any]
    raw_record: bytes
    source_fpm: str
    source_kind: str


@dataclass
class Placement:
    role: str
    x: float
    y: float
    z: float
    rx: float = 0.0
    ry: float | None = 0.0
    rz: float = 0.0
    note: str = ""


def norm(value: str | None) -> str:
    return (value or "").replace("/", "\\").lower()


def basename(value: str | None) -> str:
    return norm(value).rsplit("\\", 1)[-1]


def same_asset(value: str | None, wanted_basename: str) -> bool:
    return basename(value) == wanted_basename.lower()


def serialize_map_ent(paths: list[str]) -> bytes:
    out = bytearray(struct.pack("<i", len(paths)))
    for path in paths:
        out += path.encode("utf-8") + b"\r\n"
    return bytes(out)


def safe_template_entity(entity: dict[str, Any], dynamic: bool) -> tuple[bool, str]:
    reasons: list[str] = []
    if entity.get("record_index") == 1:
        reasons.append("record 1 owns global v319 group payload")
    if entity.get("v319_group_count", 0) != 0:
        reasons.append("group payload is non-zero")
    creation_id = entity.get("creation_of_group_id", -1)
    if creation_id not in (-1, 0):
        reasons.append(f"creationOfGroupID={creation_id}")
    if not dynamic and entity.get("staticflag") != 1:
        reasons.append(f"staticflag={entity.get('staticflag')} (need 1 for static prop)")
    return (len(reasons) == 0, ", ".join(reasons))


def record_uniqueelement_offset(raw_record: bytes) -> int:
    """Locate the v101 uniqueelement field inside one raw record."""
    r = BinaryReader(raw_record, 0x24)
    r.crlf_string("name")
    r.crlf_string("legacy aiinit")
    r.crlf_string("aimain")
    r.crlf_string("legacy aidestroy")
    r.i32("isobjective")
    r.crlf_string("usekey")
    r.crlf_string("ifused")
    r.crlf_string("ifusednear")
    return r.offset


def patch_record(
    template: Template,
    bankindex: int,
    placement: Placement,
) -> bytes:
    raw = bytearray(template.raw_record)
    entity = template.parsed
    requested_ry = entity["rotation_euler"]["y"] if placement.ry is None else placement.ry

    quat = entity.get("quaternion")
    if quat is not None and abs(float(quat.get("mode", 0.0))) > 0.0001:
        source_ry = float(entity["rotation_euler"]["y"])
        if abs(((requested_ry - source_ry + 180.0) % 360.0) - 180.0) > 0.01:
            raise FpmError(
                f"Cannot rotate {template.role} imported from {template.source_fpm}: "
                f"quatmode={quat.get('mode')} is active and the safe writer does not "
                "rewrite quaternion state yet."
            )

    struct.pack_into("<i", raw, ELE_BANKINDEX_OFFSET, bankindex)
    struct.pack_into("<f", raw, ELE_X_OFFSET, float(placement.x))
    struct.pack_into("<f", raw, ELE_Y_OFFSET, float(placement.y))
    struct.pack_into("<f", raw, ELE_Z_OFFSET, float(placement.z))
    struct.pack_into("<f", raw, ELE_RX_OFFSET, float(placement.rx))
    struct.pack_into("<f", raw, ELE_RY_OFFSET, float(requested_ry))
    struct.pack_into("<f", raw, ELE_RZ_OFFSET, float(placement.rz))

    # A cloned placed entity should not inherit a non-zero unique-element token.
    unique_offset = record_uniqueelement_offset(bytes(raw))
    old_unique = struct.unpack_from("<i", raw, unique_offset)[0]
    if old_unique != 0:
        struct.pack_into("<i", raw, unique_offset, 0)

    return bytes(raw)


def source_template_from_parsed(
    role: str,
    parsed: dict[str, Any],
    ele_data: bytes,
    source_fpm: Path,
    source_kind: str,
) -> Template | None:
    spec = ASSETS[role]
    candidates = [
        e for e in parsed["entities"] if same_asset(e.get("asset"), spec["basename"])
    ]
    for entity in candidates:
        ok, _ = safe_template_entity(entity, bool(spec.get("dynamic")))
        if not ok:
            continue
        start = entity["record_start_offset"]
        end = entity["record_end_offset"]
        return Template(
            role=role,
            asset_path=entity["asset"],
            parsed=entity,
            raw_record=ele_data[start:end],
            source_fpm=str(source_fpm),
            source_kind=source_kind,
        )
    return None


def find_generic_static_template(
    parsed: dict[str, Any], ele_data: bytes, source_fpm: Path
) -> Template:
    preferred = ["CS_Street_Lamp.fpe", "CS_Planter_01.fpe", "CS_Trash_Can.fpe"]
    for wanted in preferred:
        for entity in parsed["entities"]:
            if not same_asset(entity.get("asset"), wanted):
                continue
            ok, _ = safe_template_entity(entity, False)
            if not ok:
                continue
            start = entity["record_start_offset"]
            end = entity["record_end_offset"]
            return Template(
                role="generic_static",
                asset_path=entity["asset"],
                parsed=entity,
                raw_record=ele_data[start:end],
                source_fpm=str(source_fpm),
                source_kind="generic-static-target",
            )
    raise FpmError("No safe generic static target record is available for static bank extension.")


def candidate_fpm_paths(roots: Iterable[Path], exclude: set[Path]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        files = [root] if root.is_file() else root.rglob("*.fpm")
        for path in files:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in exclude or resolved in seen:
                continue
            seen.add(resolved)
            found.append(resolved)
    return sorted(found, key=lambda p: str(p).lower())


def harvest_donors(
    roles: list[str],
    donor_roots: list[Path],
    target_version: int,
    exclude: set[Path],
) -> dict[str, Template]:
    remaining = set(roles)
    harvested: dict[str, Template] = {}
    for donor_path in candidate_fpm_paths(donor_roots, exclude):
        if not remaining:
            break
        try:
            with FpmArchive(donor_path) as archive:
                ent = parse_map_ent(archive.read("map.ent"))
                bank_names = {basename(e["path"]) for e in ent["entries"]}
                interested = [
                    role
                    for role in remaining
                    if ASSETS[role]["basename"].lower() in bank_names
                ]
                if not interested:
                    continue
                ele_data = archive.read("map.ele")
                parsed = parse_map_ele(ele_data, ent["entries"])
                if parsed["version"] != target_version:
                    continue
                for role in interested:
                    template = source_template_from_parsed(
                        role, parsed, ele_data, donor_path, "same-version-donor"
                    )
                    if template is not None:
                        harvested[role] = template
                        remaining.discard(role)
        except Exception:
            # Donor discovery is best-effort. The final missing-template report is
            # authoritative and keeps malformed/unrelated FPMs from aborting scans.
            continue
    return harvested


def rotate_local(local_x: float, local_z: float, yaw_deg: float) -> tuple[float, float]:
    r = math.radians(yaw_deg)
    c = math.cos(r)
    s = math.sin(r)
    return (local_x * c + local_z * s, -local_x * s + local_z * c)


def add_local(
    out: list[Placement],
    role: str,
    center: dict[str, float],
    yaw: float,
    local_x: float,
    local_z: float,
    y_offset: float,
    *,
    placement_yaw: float | None = None,
    note: str = "",
) -> None:
    ox, oz = rotate_local(local_x, local_z, yaw)
    out.append(
        Placement(
            role=role,
            x=center["x"] + ox,
            y=center["y"] + y_offset,
            z=center["z"] + oz,
            ry=yaw if placement_yaw is None else placement_yaw,
            note=note,
        )
    )


def is_straight_road(entity: dict[str, Any]) -> bool:
    p = norm(entity.get("asset"))
    return (
        "\\streets and sidewalks\\streets\\cs_street_straight" in p
        and not p.endswith("light_marker.fpe")
    )


def is_four_way(entity: dict[str, Any]) -> bool:
    return same_asset(entity.get("asset"), "CS_Street_4_Way_2.fpe")


def existing_near(
    parsed: dict[str, Any], role: str, x: float, z: float, radius: float
) -> bool:
    wanted = ASSETS[role]["basename"]
    rr = radius * radius
    for entity in parsed["entities"]:
        if not same_asset(entity.get("asset"), wanted):
            continue
        p = entity["position"]
        dx = p["x"] - x
        dz = p["z"] - z
        if dx * dx + dz * dz <= rr:
            return True
    return False


def build_street_plan(parsed: dict[str, Any]) -> list[Placement]:
    """Derive deterministic street fabric from the currently authored road network."""
    placements: list[Placement] = []
    straights = sorted(
        [e for e in parsed["entities"] if is_straight_road(e)],
        key=lambda e: (round(e["position"]["x"], 3), round(e["position"]["z"], 3), e["record_index"]),
    )

    for ordinal, road in enumerate(straights):
        p = road["position"]
        yaw = float(road["rotation_euler"]["y"])

        # Yellow center indication: one decal per authored straight module.
        add_local(
            placements,
            "road_center_yellow",
            p,
            yaw,
            0.0,
            0.0,
            2.0,
            note=f"straight road #{road['record_index']}",
        )

        # Low sidewalk lights establish continuity on both sides.
        for side in (-1.0, 1.0):
            add_local(
                placements,
                "sidewalk_light",
                p,
                yaw,
                side * 305.0,
                0.0,
                3.0,
                note=f"sidewalk light beside road #{road['record_index']}",
            )

        # Full lamps/real light markers every second module -> about 800 units on 4X roads.
        if ordinal % 2 == 0:
            for side in (-1.0, 1.0):
                ox, oz = rotate_local(side * 325.0, 0.0, yaw)
                lamp = Placement(
                    role="street_lamp",
                    x=p["x"] + ox,
                    y=p["y"],
                    z=p["z"] + oz,
                    ry=yaw,
                    note=f"lamp beside road #{road['record_index']}",
                )
                placements.append(lamp)
                placements.append(
                    Placement(
                        role="street_dynamic_light",
                        x=lamp.x,
                        y=lamp.y + 280.0,
                        z=lamp.z,
                        # Dynamic marker orientation is irrelevant; preserve donor/template orientation.
                        ry=None,
                        note=f"dynamic light paired with lamp beside road #{road['record_index']}",
                    )
                )

                # Guard rails share the lamp rhythm, offset slightly toward curb.
                add_local(
                    placements,
                    "curb_guard",
                    p,
                    yaw,
                    side * 285.0,
                    115.0,
                    0.0,
                    note=f"curb guard beside road #{road['record_index']}",
                )

        # Utility infrastructure is deliberate and sparser than lamps.
        if ordinal % 3 == 0:
            add_local(
                placements,
                "utility_pole",
                p,
                yaw,
                355.0,
                -90.0,
                0.0,
                note=f"utility pole beside road #{road['record_index']}",
            )

    # Hero four-way intersections get crossing marks and hard curb protection.
    junctions = [e for e in parsed["entities"] if is_four_way(e)]
    for junction in junctions:
        p = junction["position"]
        yaw = float(junction["rotation_euler"]["y"])
        for approach_yaw, lx, lz in (
            (yaw + 0.0, 0.0, 245.0),
            (yaw + 180.0, 0.0, -245.0),
            (yaw + 90.0, 245.0, 0.0),
            (yaw + 270.0, -245.0, 0.0),
        ):
            ox, oz = rotate_local(lx, lz, yaw)
            placements.append(
                Placement(
                    role="crosswalk",
                    x=p["x"] + ox,
                    y=p["y"] + 2.0,
                    z=p["z"] + oz,
                    ry=approach_yaw % 360.0,
                    note=f"crosswalk at junction #{junction['record_index']}",
                )
            )

        for sx in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                ox, oz = rotate_local(sx * 280.0, sz * 280.0, yaw)
                placements.append(
                    Placement(
                        role="bollard_stop",
                        x=p["x"] + ox,
                        y=p["y"],
                        z=p["z"] + oz,
                        ry=yaw,
                        note=f"crossing blocker post at junction #{junction['record_index']}",
                    )
                )

    # Avoid placing a second copy where the authored level already has the same asset.
    deduped: list[Placement] = []
    for placement in placements:
        if existing_near(parsed, placement.role, placement.x, placement.z, 45.0):
            continue
        deduped.append(placement)
    return deduped


def archive_members_with_replacements(
    source: FpmArchive, replacements: dict[str, bytes]
) -> list[ArchiveMember]:
    members: list[ArchiveMember] = []
    for info in source.zip.infolist():
        key = info.filename.replace("\\", "/").lower()
        payload = replacements.get(key, source.read(info.filename))
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


def compile_street_fabric(
    source_path: Path,
    output_path: Path,
    donor_roots: list[Path],
    allow_generic_static_import: bool,
    max_placements: int,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise FpmError("Output must differ from source; in-place FPM writes are forbidden.")

    with FpmArchive(source_path) as source:
        ent = parse_map_ent(source.read("map.ent"))
        if ent["encoding"] != "crlf":
            raise FpmError("Street-fabric writer currently requires CRLF map.ent encoding.")
        ele_data = source.read("map.ele")
        parsed = parse_map_ele(ele_data, ent["entries"])
        verify_raw_ele_roundtrip(ele_data, parsed)
        source_manifest = {row["name"]: row["sha256"] for row in source.member_manifest()}

        templates: dict[str, Template] = {}
        for role in REQUIRED_ROLES:
            t = source_template_from_parsed(
                role, parsed, ele_data, source_path, "target"
            )
            if t is not None:
                templates[role] = t

        missing = [role for role in REQUIRED_ROLES if role not in templates]
        donor_templates = harvest_donors(
            missing,
            donor_roots,
            parsed["version"],
            {source_path, output_path},
        )
        templates.update(donor_templates)

        # Static pack props may be imported with a generic static record if no
        # same-version donor exists. Dynamic light markers are never synthesized.
        generic_template: Template | None = None
        static_imported: list[str] = []
        if allow_generic_static_import:
            for role in REQUIRED_ROLES:
                if role in templates or ASSETS[role].get("dynamic"):
                    continue
                if generic_template is None:
                    generic_template = find_generic_static_template(parsed, ele_data, source_path)
                spec = ASSETS[role]
                templates[role] = Template(
                    role=role,
                    asset_path=spec["path"],
                    parsed=generic_template.parsed,
                    raw_record=generic_template.raw_record,
                    source_fpm=str(source_path),
                    source_kind="generic-static-bank-extension",
                )
                static_imported.append(role)

        still_missing = [role for role in REQUIRED_ROLES if role not in templates]
        if still_missing:
            lines = [
                f"{role}: {ASSETS[role]['basename']}"
                for role in still_missing
            ]
            raise FpmError(
                "Required street-fabric template(s) could not be sourced. "
                "Dynamic light markers require an exact same-version donor record. "
                "Missing: " + "; ".join(lines)
            )

        placements = build_street_plan(parsed)
        if len(placements) > max_placements:
            raise FpmError(
                f"Street plan generated {len(placements)} placements, exceeding "
                f"--max-placements={max_placements}."
            )

        bank_paths = [entry["path"] for entry in ent["entries"]]
        bank_lookup = {norm(path): i + 1 for i, path in enumerate(bank_paths)}
        role_bankindex: dict[str, int] = {}
        for role, template in templates.items():
            asset_path = template.asset_path
            # Generic imports use the canonical desired asset path rather than
            # the generic source record's original bank path.
            if template.source_kind == "generic-static-bank-extension":
                asset_path = ASSETS[role]["path"]
            key = norm(asset_path)
            if key not in bank_lookup:
                bank_paths.append(asset_path)
                bank_lookup[key] = len(bank_paths)
            role_bankindex[role] = bank_lookup[key]

        new_records: list[bytes] = []
        mutation_rows: list[dict[str, Any]] = []
        for placement in placements:
            template = templates[placement.role]
            record = patch_record(template, role_bankindex[placement.role], placement)
            new_records.append(record)
            mutation_rows.append(
                {
                    "role": placement.role,
                    "asset": ASSETS[placement.role]["basename"],
                    "bankindex": role_bankindex[placement.role],
                    "x": placement.x,
                    "y": placement.y,
                    "z": placement.z,
                    "ry": placement.ry,
                    "template_source": template.source_kind,
                    "template_fpm": template.source_fpm,
                    "note": placement.note,
                }
            )

        new_ele = bytearray(ele_data)
        struct.pack_into("<i", new_ele, 4, parsed["entity_count"] + len(new_records))
        for record in new_records:
            new_ele += record
        new_ent = serialize_map_ent(bank_paths)

        members = archive_members_with_replacements(
            source,
            {"map.ent": new_ent, "map.ele": bytes(new_ele)},
        )

    write_zipcrypto_archive(output_path, members)

    # Structural verification of the generated FPM.
    with FpmArchive(output_path) as generated:
        gent = parse_map_ent(generated.read("map.ent"))
        gele_data = generated.read("map.ele")
        gparsed = parse_map_ele(gele_data, gent["entries"])
        generated_manifest = {row["name"]: row["sha256"] for row in generated.member_manifest()}

    expected_count = parsed["entity_count"] + len(new_records)
    if gparsed["entity_count"] != expected_count:
        raise FpmError(
            f"Generated entity count {gparsed['entity_count']} != expected {expected_count}."
        )
    if not gparsed["fully_traversed"] or gparsed["trailing_bytes"] != 0:
        raise FpmError("Generated map.ele did not traverse exactly to EOF.")

    changed_members = sorted(
        name
        for name, sha in generated_manifest.items()
        if source_manifest.get(name) != sha
    )
    allowed = {
        name
        for name in generated_manifest
        if name.replace("\\", "/").lower() in {"map.ent", "map.ele"}
    }
    if set(changed_members) - allowed:
        raise FpmError(
            "Generated FPM changed unrelated decrypted members: "
            + ", ".join(sorted(set(changed_members) - allowed))
        )

    return {
        "source_fpm": str(source_path),
        "output_fpm": str(output_path),
        "ele_version": parsed["version"],
        "old_entity_count": parsed["entity_count"],
        "new_entity_count": gparsed["entity_count"],
        "added_entities": len(new_records),
        "old_bank_count": ent["count"],
        "new_bank_count": gent["count"],
        "generic_static_import_roles": static_imported,
        "template_sources": {
            role: {
                "asset": ASSETS[role]["basename"],
                "source_kind": templates[role].source_kind,
                "source_fpm": templates[role].source_fpm,
            }
            for role in REQUIRED_ROLES
        },
        "changed_decrypted_members": changed_members,
        "placements": mutation_rows,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def print_report(report: dict[str, Any]) -> None:
    print("BLACK SIGNAL - authored District 12 street fabric")
    print(f"Source: {report['source_fpm']}")
    print(f"Output: {report['output_fpm']}")
    print(f"ELE version: {report['ele_version']}")
    print(
        f"Entities: {report['old_entity_count']} -> {report['new_entity_count']} "
        f"(+{report['added_entities']})"
    )
    print(f"Entity bank: {report['old_bank_count']} -> {report['new_bank_count']}")
    print()
    print("Template sources:")
    for role, row in report["template_sources"].items():
        print(f"  {role:22} {row['source_kind']:30} {row['asset']}")
    if report["generic_static_import_roles"]:
        print()
        print("[WARN] Experimental generic-static bank imports:")
        for role in report["generic_static_import_roles"]:
            print(f"  - {role}: {ASSETS[role]['basename']}")
        print("       Validate these meshes/collision visually in MAX before production use.")
    print()
    print("[PASS] Generated FPM reopens and complete ELE traversal ends exactly at EOF.")
    print("[PASS] Only decrypted map.ent/map.ele payloads changed.")
    print(f"SHA-256: {report['sha256']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_fpm", type=Path)
    parser.add_argument("output_fpm", type=Path)
    parser.add_argument(
        "--donor-root",
        action="append",
        default=[],
        type=Path,
        help="FPM file or directory recursively scanned for same-version exact asset records",
    )
    parser.add_argument(
        "--no-generic-static-import",
        action="store_true",
        help="Require exact target/donor records for every static street-fabric asset",
    )
    parser.add_argument("--max-placements", type=int, default=1200)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)

    try:
        report = compile_street_fabric(
            args.source_fpm,
            args.output_fpm,
            args.donor_root,
            not args.no_generic_static_import,
            args.max_placements,
        )
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
        return 0
    except (FpmError, OSError, ValueError, struct.error) as exc:
        print(f"FPM STREET FABRIC ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
