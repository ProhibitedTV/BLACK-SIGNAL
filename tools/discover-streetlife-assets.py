#!/usr/bin/env python3
"""Discover installed planter/tree assets for District 12 without vendoring DLC geometry.

The production map may reference locally installed GameGuru MAX assets, but BLACK SIGNAL
must not guess asset names or commit commercial geometry.  This preflight scans the local
entity bank, prefers Cyberpunk Streets planters, measures a small ranked set of tree/planter
meshes with MAX's bundled DBO2X converter, and emits only paths + bounds metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def _read_vertices(text: str) -> list[list[float]]:
    if "FrameTransformMatrix" in text:
        raise ValueError("converter output has unflattened transforms")
    vertices: list[list[float]] = []
    for match in re.finditer(r"\bMesh\s+\w+\s*\{\s*(\d+);", text):
        count = int(match[1])
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text[match.end():])
        if len(numbers) < count * 3:
            raise ValueError("truncated vertex array")
        vertices.extend([list(map(float, numbers[i:i + 3])) for i in range(0, count * 3, 3)])
    if not vertices:
        raise ValueError("no mesh vertices found")
    return vertices


def _model_path(fpe: Path, bank: Path) -> Path | None:
    try:
        text = fpe.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = re.search(r"(?im)^\s*model\s*=\s*([^\r\n;]+)", text)
    values: list[Path] = []
    if match:
        raw = match.group(1).strip().strip('"').replace("\\", "/")
        if raw.lower().startswith("entitybank/"):
            raw = raw[len("entitybank/"):]
        model = Path(raw)
        values.extend((fpe.parent / model.name, bank / model))
    values.append(fpe.with_suffix(".dbo"))
    for candidate in values:
        if candidate.exists() and candidate.suffix.lower() == ".dbo":
            return candidate
    return None


def _measure(converter: Path, mesh: Path, scratch: Path, ordinal: int) -> dict[str, Any]:
    scratch.mkdir(parents=True, exist_ok=True)
    converted = scratch / f"candidate-{ordinal:03d}.x"
    subprocess.run(
        [str(converter), str(mesh), str(converted), "-groups", "-o"],
        check=True,
        capture_output=True,
    )
    vertices = _read_vertices(converted.read_text(encoding="utf-8", errors="ignore"))
    low = [min(v[i] for v in vertices) for i in range(3)]
    high = [max(v[i] for v in vertices) for i in range(3)]
    return {
        "min": low,
        "max": high,
        "size": [high[i] - low[i] for i in range(3)],
        "mesh_sha256": hashlib.sha256(mesh.read_bytes()).hexdigest(),
    }


def _tree_name_score(path: Path) -> tuple[int, str]:
    value = str(path).lower().replace("\\", "/")
    score = 0
    for token, weight in (
        ("small", -50), ("young", -45), ("urban", -45), ("city", -40),
        ("ornamental", -40), ("street", -25), ("tree_01", -20), ("tree01", -20),
        ("large", 70), ("giant", 100), ("huge", 100), ("fallen", 100),
        ("stump", 100), ("log", 100), ("dead", 60), ("forest", 35),
    ):
        if token in value:
            score += weight
    return score, value


def _is_tree_candidate(path: Path) -> bool:
    """Require an actual tree token; do not mistake ``street`` for ``tree``.

    The original v10.4 preflight used ``"tree" in stem``.  Because the word
    ``street`` contains that substring, assets such as CS_Street_Electrical_Pole_01
    could enter the tree pool and even win on compact measured bounds.  Remove the
    lexical ``street`` token first, then require tree in what remains.
    """
    stem = path.stem.lower()
    reduced = stem.replace("street", "")
    if "tree" not in reduced:
        return False
    return not any(token in reduced for token in ("stump", "log", "fallen"))


def _planter_name_score(path: Path) -> tuple[int, str]:
    value = str(path).lower().replace("\\", "/")
    score = 0
    if path.name.lower() == "cs_planter_01.fpe":
        score -= 200
    if "cyberpunk streets booster pack" in value:
        score -= 100
    if "planter" in value:
        score -= 40
    if "large" in value or "huge" in value:
        score += 40
    return score, value


def _relative_asset(fpe: Path, bank: Path) -> str:
    rel = fpe.resolve().relative_to(bank.resolve())
    return str(rel).replace("/", "\\")


def _measure_candidates(
    candidates: list[Path], bank: Path, converter: Path, scratch: Path, limit: int
) -> list[dict[str, Any]]:
    measured: list[dict[str, Any]] = []
    for ordinal, fpe in enumerate(candidates[:limit]):
        mesh = _model_path(fpe, bank)
        if mesh is None:
            continue
        try:
            bounds = _measure(converter, mesh, scratch, ordinal)
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
        measured.append({
            "asset": _relative_asset(fpe, bank),
            "basename": fpe.name,
            "mesh": str(mesh),
            **bounds,
        })
    return measured


def _pick_planter(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("no measurable planter asset found")
    def score(row: dict[str, Any]) -> tuple[float, str]:
        sx, sy, sz = map(float, row["size"])
        footprint = max(sx, sz)
        # Favor a compact sidewalk planter; tolerate larger pack-authored containers.
        ideal_penalty = abs(footprint - 180.0) / 40.0 + abs(sy - 80.0) / 40.0
        if footprint > 500.0 or sy > 350.0:
            ideal_penalty += 50.0
        if row["basename"].lower() == "cs_planter_01.fpe":
            ideal_penalty -= 20.0
        if "Cyberpunk Streets Booster Pack".lower() in row["asset"].lower():
            ideal_penalty -= 10.0
        return ideal_penalty, row["asset"].lower()
    return min(rows, key=score)


def _pick_tree(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("no measurable tree asset found")

    # Defense in depth: discovery should already have filtered this list, but never
    # promote a non-tree row if future callers provide their own measured candidates.
    actual_trees = [row for row in rows if _is_tree_candidate(Path(str(row.get("basename") or "")))]
    if not actual_trees:
        raise ValueError("measured tree candidates contained no actual tree asset")

    def score(row: dict[str, Any]) -> tuple[float, str]:
        sx, sy, sz = map(float, row["size"])
        footprint = max(sx, sz)
        height = sy
        penalty = abs(height - 550.0) / 80.0 + footprint / 180.0
        if not (220.0 <= height <= 1000.0):
            penalty += 30.0
        if footprint > 650.0:
            penalty += 30.0
        name_score, _ = _tree_name_score(Path(row["basename"]))
        penalty += name_score / 20.0
        return penalty, row["asset"].lower()
    return min(actual_trees, key=score)


def discover(install: Path, scratch: Path) -> dict[str, Any]:
    bank = install / "Files" / "entitybank"
    converter = install / "Tools" / "DBO2X" / "dbo2x.exe"
    if not bank.is_dir():
        raise ValueError(f"entity bank not found: {bank}")
    if not converter.is_file():
        raise ValueError(f"DBO2X converter not found: {converter}")

    planter_candidates = sorted(
        [p for p in bank.rglob("*.fpe") if "planter" in p.name.lower()],
        key=_planter_name_score,
    )
    tree_candidates = sorted(
        [p for p in bank.rglob("*.fpe") if _is_tree_candidate(p)],
        key=_tree_name_score,
    )

    planters = _measure_candidates(planter_candidates, bank, converter, scratch / "planters", 20)
    trees = _measure_candidates(tree_candidates, bank, converter, scratch / "trees", 30)
    selected_planter = _pick_planter(planters)
    selected_tree = _pick_tree(trees)

    return {
        "policy": "v10.4-installed-measured-streetlife-assets",
        "entitybank": str(bank),
        "planter": selected_planter,
        "tree": selected_tree,
        "candidate_counts": {
            "planter_fpe": len(planter_candidates),
            "tree_fpe": len(tree_candidates),
            "measured_planters": len(planters),
            "measured_trees": len(trees),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = discover(args.install, args.scratch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Street-life planter: {result['planter']['asset']} size={result['planter']['size']}")
    print(f"Street-life city tree: {result['tree']['asset']} size={result['tree']['size']}")
    print(f"Street-life discovery -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
