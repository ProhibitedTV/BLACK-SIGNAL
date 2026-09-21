#!/usr/bin/env python3
"""Compatibility front-end for the District 12 city-mass compiler.

The stock CyberCity level is authored from many closely spaced modular pieces.
A single 525-unit connected-component radius can chain neighboring buildings
across sidewalks/streets into one huge component, which then gets rejected by
the city-mass size guard. This wrapper learns a useful clustering radius from
the actual level instead of assuming one radius fits the kit.

It also permits ordinary placed building pieces that carry MAX editor grouping
metadata. We clone their exact raw records and preserve that metadata; record 1
and records carrying the global v319 group table remain excluded.

The real CyberCity map.ent stores DLC paths relative to entitybank (for example
``Cyberpunk Streets Booster Pack\\Buildings\\...``), while some dependency lists
prefix the same path with ``entitybank\\``. Normalize both forms before classifying
roads/buildings so the production compiler does not silently see zero candidates.
"""
from __future__ import annotations

import sys

import fpm_author_city_mass as city


_original_cluster_entities = city.cluster_entities


def _pack_relative(asset: str | None) -> str:
    p = city.norm(asset).lstrip("\\")
    if p.startswith("entitybank\\"):
        p = p[len("entitybank\\") :]
    return p


def _is_road(entity: dict) -> bool:
    p = _pack_relative(entity.get("asset"))
    return (
        p.startswith("cyberpunk streets booster pack\\streets and sidewalks\\streets\\cs_street_")
        and "light_marker" not in p
    )


def _is_foreground_building(entity: dict) -> bool:
    p = _pack_relative(entity.get("asset"))
    if not p.startswith("cyberpunk streets booster pack\\"):
        return False
    return "\\buildings\\" in ("\\" + p) or "\\store fronts\\" in ("\\" + p)


def _is_background_building(entity: dict) -> bool:
    p = _pack_relative(entity.get("asset"))
    return p.startswith("cyberpunk streets booster pack\\background buildings\\")


def _cloneable_city_piece(entity: dict) -> bool:
    if int(entity.get("record_index", 0)) == 1:
        return False
    if int(entity.get("v319_group_count", 0) or 0) != 0:
        return False
    # MAX levels can contain structural pieces with either 0 or 1 here after
    # editor/group operations. Both are exact placed records from the exemplar.
    if int(entity.get("staticflag", 0)) not in (0, 1):
        return False
    return True


def _valid_cluster(cluster: city.Cluster, kind: str) -> bool:
    if kind == "foreground":
        return (
            len(cluster.entities) >= 4
            and cluster.width <= 2200.0
            and cluster.depth <= 2200.0
        )
    return len(cluster.entities) >= 2


def _adaptive_cluster_entities(entities: list[dict], kind: str, _requested_radius: float) -> list[city.Cluster]:
    # Cyber City modular pieces are much closer together than the road-module
    # spacing. Try several local radii and select the partition that preserves
    # the largest number of useful authored assemblies without chaining the city
    # into one giant component.
    radii = (110.0, 140.0, 175.0, 210.0, 250.0, 300.0, 360.0, 430.0)
    best_clusters: list[city.Cluster] | None = None
    best_score: tuple[int, int, int] | None = None
    best_radius = 0.0

    for radius in radii:
        clusters = _original_cluster_entities(entities, kind, radius)
        valid = [c for c in clusters if _valid_cluster(c, kind)]
        covered = sum(len(c.entities) for c in valid)
        # Favor many useful assemblies first, then entity coverage; finally
        # prefer the tighter radius when scores are equal.
        score = (len(valid), covered, -int(radius))
        if best_score is None or score > best_score:
            best_score = score
            best_clusters = clusters
            best_radius = radius

    assert best_clusters is not None
    useful = sum(1 for c in best_clusters if _valid_cluster(c, kind))
    print(
        f"Adaptive {kind} clustering: radius={best_radius:.0f}, "
        f"components={len(best_clusters)}, useful={useful}"
    )
    return best_clusters


def main(argv: list[str] | None = None) -> int:
    city.is_road = _is_road
    city.is_foreground_building = _is_foreground_building
    city.is_background_building = _is_background_building
    city.safe_static = _cloneable_city_piece
    city.cluster_entities = _adaptive_cluster_entities
    return city.main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
