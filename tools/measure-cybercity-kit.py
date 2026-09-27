"""Measure installed meshes with MAX's bundled DBO2X converter; never vendor assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

NAMES = (
    "CS_Wall_01", "CS_Wall_Corner_01", "CS_Walls_01_Window_With_Bars",
    "CS_Wall_01_Entry_01", "CS_Wall_01_Entry_04", "CS_Roof_Tile_2x2",
    "CS_Roof_Tile_4x4", "CS_Wall_01_Overhang", "CS_Wall_01_Overhang_Corner",
    "CS_Street_Straight_4X", "CS_Street_4_Way_2", "CS_Street_T-Intersect_3",
    "CS_Street_Curve_1", "CS_Sidewalk_Straight_Edge", "CS_Sidewalk_Corner1_DropCurb",
    "CS_Sidewalk_Tile_4x4", "CS_Sidewalk_Tile", "CS_Street_Lamp",
    # Ground-floor shop overlay used by the v10.2 frontage pass.  The
    # Neon_Opposite variant is intentionally not measured/placed because its
    # signage transform failed native visual review.
    "CS_Store_Front_02_Corner_With_Window",
    "CS_Store_Front_01", "CS_Store_Front_01_Blue", "CS_Store_Front_01_Entrance",
    "CS_Store_Front_01_Sign", "CS_Wall_01_NeonDecor_01_Sign_02_Computers",
    "CS_Neon_01", "CS_Neon_02", "CS_Neon_03", "CS_Neon_04", "CS_Neon_05",
    "CS_Dumpster_Closed", "CS_Trashbag_01", "CS_Trashbag_02", "CS_Trashbag_03",
    "CS_Box_01", "CS_Box_02", "CS_Cardboard", "CS_Bottle_Can_Cluster_01",
    "CS_Newspaper_01", "CS_Newspaper_02", "CS_Can_01", "CS_Can_03",
    "CS_AirCon_01", "CS_AirCon_01_Stand", "CS_ATM", "CS_ATM_Screen",
    "CS_Bus_Stop", "CS_Bus_Stop_Neon_Sign", "CS_Bench", "CS_Trash_Can",
    "CS_Graffiti_01", "CS_Graffiti_02", "CS_Fireplug",
    "CS_Planter_01", "CS_Sidewalk_Light", "CS_Stop_Light",
)


def read_vertices(text: str) -> list[list[float]]:
    if "FrameTransformMatrix" in text:
        raise ValueError("Converter output has unflattened transforms; refusing guessed bounds")
    vertices = []
    for match in re.finditer(r"\bMesh\s+\w+\s*\{\s*(\d+);", text):
        count = int(match[1])
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text[match.end():])
        if len(numbers) < count * 3:
            raise ValueError("Truncated vertex array")
        vertices.extend([list(map(float, numbers[i:i+3])) for i in range(0, count*3, 3)])
    if not vertices:
        raise ValueError("No mesh vertices found")
    return vertices


def measure(root: Path, scratch: Path) -> dict:
    scratch.mkdir(parents=True, exist_ok=True)
    bank = root / "Files/entitybank"
    report = {}
    for name in NAMES:
        matches = list((bank / "Cyberpunk Streets Booster Pack").rglob(name + ".dbo"))
        if len(matches) != 1:
            raise ValueError(f"Expected one installed {name}: {matches}")
        mesh = matches[0]
        converted = scratch / (name + ".x")
        subprocess.run([str(root / "Tools/DBO2X/dbo2x.exe"), str(mesh), str(converted), "-groups", "-o"],
                       check=True, capture_output=True)
        vertices = read_vertices(converted.read_text())
        low = [min(v[i] for v in vertices) for i in range(3)]
        high = [max(v[i] for v in vertices) for i in range(3)]
        report[name] = {"min": low, "max": high,
                        "size": [high[i]-low[i] for i in range(3)],
                        "mesh_sha256": hashlib.sha256(mesh.read_bytes()).hexdigest(),
                        "asset": str(mesh.relative_to(bank).with_suffix(".fpe"))}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, default=Path(".black-signal/mesh-audit"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.install, args.scratch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Measured {len(result)} meshes -> {args.output}")
