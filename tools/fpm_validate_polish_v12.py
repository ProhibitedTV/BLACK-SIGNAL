"""Verify the incremental export against the user's saved baseline and its layout report."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import fpm_polish_city_v12 as polish
import fpm_city_extras as extras
from fpm_inspect import FpmArchive, FpmError


def _record_bytes(data, entity):
    return data[entity["record_start_offset"] : entity["record_end_offset"]]


def validate(candidate, source, layout_path=None):
    layout_path = layout_path or candidate.with_suffix(".report.json")
    report = json.loads(layout_path.read_text())
    rows = report["placements"]

    sd, sb, sp = polish.load_scene(source)
    cd, cb, cp = polish.load_scene(candidate)
    grouped = polish.is_grouped_baseline(sp)

    if report["source_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest():
        raise FpmError("Baseline changed")
    if report["sha256"] != hashlib.sha256(candidate.read_bytes()).hexdigest():
        raise FpmError("Candidate changed")
    if len(rows) + 1 != cp["entity_count"] or cp["version"] != 342 or cp["trailing_bytes"]:
        raise FpmError("Entity stream mismatch")

    source_count = sp["entity_count"]
    if grouped:
        if report.get("group_strategy") != polish.GROUPED_STRATEGY:
            raise FpmError("Grouped candidate does not declare the append-only source-preservation strategy")
        if report.get("source_entity_count") != source_count:
            raise FpmError("Grouped candidate source entity count does not match baseline")
        if report.get("native_group_count") != sp["entities"][0].get("v319_group_count", 0):
            raise FpmError("Grouped candidate native group count does not match baseline")
        if cp["entity_count"] < source_count:
            raise FpmError("Grouped candidate deleted source records")

        expected_indices = list(range(2, source_count + 1))
        source_prefix = rows[: source_count - 1]
        if [r.get("source_index") for r in source_prefix] != expected_indices:
            raise FpmError("Grouped candidate did not preserve baseline source record order")
        if any(r.get("source_index") is not None for r in rows[source_count - 1 :]):
            raise FpmError("Grouped source record found after appended V12 records")

        # Preserve the complete native MAX group-bearing baseline byte-for-byte.
        # We deliberately do not infer or rewrite opaque v319 IDs.
        for i in range(source_count):
            before = sp["entities"][i]
            after = cp["entities"][i]
            if before["record_sha256"] != after["record_sha256"]:
                raise FpmError(f"Grouped baseline record {i + 1} changed")
            if _record_bytes(sd, before) != _record_bytes(cd, after):
                raise FpmError(f"Grouped baseline record {i + 1} is not byte-identical")

        # New records must not contain their own v319 group table. The parser
        # already rejects non-first records with non-zero group_count, but keep
        # this explicit at the production boundary as well.
        for e in cp["entities"][source_count:]:
            if e.get("v319_group_count", 0):
                raise FpmError(f"Appended record {e['record_index']} contains unexpected group table data")

    lookup = {}
    for r, e in zip(rows, cp["entities"][1:]):
        if polish.city.key(e["asset"]) != r["asset"] or any(
            abs(e["position"][a] - r[a]) > 0.03 for a in ("x", "y", "z")
        ):
            raise FpmError("Transform mismatch")
        if abs((e["rotation_euler"]["y"] - r["yaw"] + 180) % 360 - 180) > 0.03:
            raise FpmError("Yaw mismatch")
        if r.get("source_index"):
            lookup[r["source_index"]] = e
            if grouped and e["record_index"] != r["source_index"]:
                raise FpmError(
                    f"Grouped source record {r['source_index']} shifted to {e['record_index']}"
                )
        if "scale" in r and any(
            abs(e["scale_xyz"][a] - 100 * (s - 1)) > 0.01
            for a, s in zip(("x", "y", "z"), r["scale"])
        ):
            raise FpmError("Scaled geometry mismatch")
        if r["group"] == "extras" and (
            e["name"] != r["name"] or e["aimain"] != extras.SCRIPT or e["staticflag"] != 0
        ):
            raise FpmError("Civilian binding mismatch")

    locked = set(report["protected_manual_records"])
    locked.update(
        e["record_index"]
        for e in sp["entities"]
        if polish.city.roads.road_kind(e.get("asset"))
        or polish.city.key(e.get("asset")) == "CS_Street_Crosswalk_Decal"
    )
    if grouped:
        # Append-only grouped mode protects every source record, not only roads
        # and manually changed records.
        locked.update(range(1, source_count + 1))

    for idx in locked:
        before = sp["entities"][idx - 1]
        if idx == 1:
            after = cp["entities"][0]
        else:
            after = lookup.get(idx)
        if not after or before["record_sha256"] != after["record_sha256"]:
            raise FpmError(f"Protected manual/infrastructure record changed: {idx}")

    if _record_bytes(sd, sp["entities"][0]) != _record_bytes(cd, cp["entities"][0]):
        raise FpmError("Player/global/group metadata changed")

    measured = json.loads((polish.ROOT / "docs/cybercity-kit-measurements.json").read_text())
    measured.update(json.loads((polish.ROOT / "docs/city-polish-measurements.json").read_text()))
    scene = []
    local = dict(measured)
    for i, source_row in enumerate(rows):
        r = dict(source_row)
        if "scale" in r:
            label = r["asset"] + "__" + str(i)
            b = copy.deepcopy(measured[r["asset"]])
            for axis, s in enumerate(r["scale"]):
                b["min"][axis] *= s
                b["max"][axis] *= s
            local[label] = b
            r["asset"] = label
        scene.append(r)

    extras.validate(
        scene,
        report["parcels"],
        local,
        polish.city.hero.world_bounds,
        polish.city.measured_city.intersects,
    )

    routes = candidate.with_suffix(".routes.lua")
    if not routes.exists():
        routes = polish.ROOT / "gameguru/Files/scriptbank/user/black_signal/bs_city_extra_routes.lua"
    if routes.read_text() != extras.render_lua(rows):
        raise FpmError("Pedestrian routes differ from map")

    for r in rows:
        if r["group"] not in ("upper-deck", "upper-stair"):
            continue
        p = min(
            report["parcels"],
            key=lambda p: (r["x"] - p["x"]) ** 2 + (r["z"] - (p["z"] + p["depth"] / 2)) ** 2,
        )
        sy = r.get("scale", [1, 1, 1])[1]
        bottom = r["y"] + 80 * sy
        top = r["y"] + 100 * sy
        if r["group"] == "upper-stair" and abs(bottom - p["ground"]) > 0.02:
            raise FpmError("Unsupported stair block")
        if r["group"] == "upper-deck" and abs(top - p["ground"] - 200) > 0.02:
            raise FpmError("Gallery floor seam")

    with FpmArchive(source) as a, FpmArchive(candidate) as b:
        before = {m["name"]: m["sha256"] for m in a.member_manifest()}
        after = {m["name"]: m["sha256"] for m in b.member_manifest()}
        if {n for n in before if before[n] != after[n]} - {"map.ele", "map.ent", "visuals.ini"}:
            raise FpmError("Unexpected archive member change")

    return dict(
        status="pass",
        entity_count=cp["entity_count"],
        source_entity_count=source_count,
        grouped_baseline=grouped,
        native_group_count=sp["entities"][0].get("v319_group_count", 0),
        group_strategy=polish.GROUPED_STRATEGY if grouped else "incremental-remap-not-required",
        protected_records=len(locked),
        extras=216,
        sha256=report["sha256"],
        native_review="pending",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("candidate", type=Path)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument(
        "--layout",
        type=Path,
        help="Candidate .report.json emitted by fpm_polish_city_v12.py (defaults beside candidate)",
    )
    p.add_argument("--report", type=Path, help="Write validation receipt JSON here")
    a = p.parse_args()
    result = validate(a.candidate, a.source, a.layout)
    if a.report:
        a.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
