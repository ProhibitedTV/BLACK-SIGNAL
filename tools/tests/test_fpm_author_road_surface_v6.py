import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fpm_author_road_surface_v6 as surface


STRAIGHT = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_Straight_4X.fpe"
FOURWAY = "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Streets\\CS_Street_4_Way_2.fpe"


def road(asset: str, *, x=0.0, y=0.0, z=0.0, yaw=0.0, index=1) -> dict:
    return {
        "asset": asset,
        "position": {"x": x, "y": y, "z": z},
        "rotation_euler": {"x": 0.0, "y": yaw, "z": 0.0},
        "record_index": index,
    }


def member(
    role: str,
    *,
    kind="straight4",
    local_x=0.0,
    local_z=0.0,
    y_offset=1.0,
    relative_yaw=0.0,
    detail_index=10,
    road_index=5,
) -> surface.SurfaceMember:
    return surface.SurfaceMember(
        role=role,
        road_kind=kind,
        asset_path=surface.SURFACE_ASSETS[role]["path"],
        parsed={},
        raw_record=b"",
        local_x=local_x,
        y_offset=y_offset,
        local_z=local_z,
        relative_yaw=relative_yaw,
        donor_detail_record_index=detail_index,
        donor_road_record_index=road_index,
    )


class DonorCalibratedRoadSurfaceTests(unittest.TestCase):
    def test_placement_replays_exact_donor_local_transform(self):
        exemplar = member(
            "road_wear_01",
            local_x=137.25,
            local_z=-44.5,
            y_offset=2.75,
            relative_yaw=17.0,
        )
        target = road(STRAIGHT, x=1000.0, y=20.0, z=2000.0, yaw=90.0, index=77)
        placed = surface.placement_for_member(exemplar, target, "test")
        self.assertAlmostEqual(placed.x, 955.5, places=4)
        self.assertAlmostEqual(placed.z, 1862.75, places=4)
        self.assertAlmostEqual(placed.y, 22.75, places=4)
        self.assertAlmostEqual(placed.ry, 107.0, places=4)

    def test_plan_keeps_arbitrary_donor_wear_offset_without_lane_guessing(self):
        exemplar = member("road_wear_04", local_x=143.125, local_z=51.75, detail_index=41)
        target = road(STRAIGHT, x=300.0, y=5.0, z=700.0, yaw=0.0, index=9)
        plan = surface.plan_surface_details({"entities": [target]}, [exemplar])
        wear = [item for item in plan if item.member.role == "road_wear_04"]
        self.assertEqual(len(wear), 1)
        self.assertAlmostEqual(wear[0].x, 443.125, places=4)
        self.assertAlmostEqual(wear[0].z, 751.75, places=4)

    def test_approach_uses_donor_member_from_matching_half_of_road(self):
        forward = member(
            "road_arrow_straight",
            local_x=80.0,
            local_z=95.0,
            detail_index=101,
        )
        backward = member(
            "road_arrow_right",
            local_x=-82.0,
            local_z=-97.0,
            detail_index=102,
        )
        target = road(STRAIGHT, x=0.0, z=500.0, yaw=0.0, index=11)
        junction = road(FOURWAY, x=0.0, z=0.0, yaw=0.0, index=12)
        plan = surface.plan_surface_details(
            {"entities": [target, junction]},
            [forward, backward],
        )
        arrows = [item for item in plan if item.member.role in surface.ARROW_ROLES]
        self.assertEqual(len(arrows), 1)
        self.assertEqual(arrows[0].member.donor_detail_record_index, 102)
        self.assertAlmostEqual(arrows[0].x, -82.0, places=4)
        self.assertAlmostEqual(arrows[0].z, 403.0, places=4)

    def test_catalog_separates_forward_and_backward_authored_markings(self):
        rows = [
            member("road_arrow_left", local_z=30.0, detail_index=1),
            member("road_arrow_right", local_z=-30.0, detail_index=2),
            member("road_slow", local_z=45.0, detail_index=3),
            member("road_only", local_z=-45.0, detail_index=4),
        ]
        catalog = surface._catalog(rows)["straight4"]
        self.assertEqual([m.donor_detail_record_index for m in catalog["arrow_forward"]], [1])
        self.assertEqual([m.donor_detail_record_index for m in catalog["arrow_backward"]], [2])
        self.assertEqual([m.donor_detail_record_index for m in catalog["text_forward"]], [3])
        self.assertEqual([m.donor_detail_record_index for m in catalog["text_backward"]], [4])

    def test_v6_strips_old_surface_assets_but_not_v4_structural_assets(self):
        self.assertTrue(
            surface._strip_owned_surface_detail(
                {"asset": surface.SURFACE_ASSETS["road_wear_01"]["path"]}
            )
        )
        self.assertFalse(
            surface._strip_owned_surface_detail(
                {
                    "asset": "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Street Decals\\CS_Street_Double_Center_Line.fpe"
                }
            )
        )
        self.assertFalse(
            surface._strip_owned_surface_detail(
                {
                    "asset": "Cyberpunk Streets Booster Pack\\Streets and Sidewalks\\Street Decals\\CS_Street_Crosswalk_Decal.fpe"
                }
            )
        )

    def test_plan_is_repeatable_when_target_entity_order_changes(self):
        members = [
            member("road_wear_01", local_x=10.0, local_z=20.0, detail_index=1),
            member("road_wear_02", local_x=-10.0, local_z=-20.0, detail_index=2),
        ]
        roads = [
            road(STRAIGHT, x=0.0, z=500.0, index=11),
            road(STRAIGHT, x=0.0, z=900.0, index=12),
        ]
        first = surface.plan_surface_details({"entities": roads}, members)
        second = surface.plan_surface_details({"entities": list(reversed(roads))}, members)
        sig = lambda plan: sorted(
            (
                item.member.role,
                round(item.x, 3),
                round(item.z, 3),
                round(item.ry, 3),
                item.target_road_record_index,
            )
            for item in plan
        )
        self.assertEqual(sig(first), sig(second))


if __name__ == "__main__":
    unittest.main()
