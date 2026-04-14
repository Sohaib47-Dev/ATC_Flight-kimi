"""Route compilation from radar_airways.json."""
import unittest

from app.services import route_builder
from app.services.kinematics import cumulative_nm_polyline, haversine_nm


class RouteBuilderTests(unittest.TestCase):
    def test_build_path_gugal_airways(self):
        path = route_builder.build_simulated_route_path(
            "GUGAL",
            "GUGAL M875 M881 LAJAK",
        )
        self.assertGreaterEqual(len(path), 3)
        self.assertAlmostEqual(path[0][0], 30.045302068536934, places=5)

    def test_path_fingerprint_stable(self):
        p1 = route_builder.build_simulated_route_path("SULOM", "SULOM A466 LAJAK")
        h1 = route_builder.path_fingerprint(p1)
        h2 = route_builder.path_fingerprint(list(p1))
        self.assertEqual(h1, h2)

    def test_build_path_sulom_l509_lajak_uses_airway_polyline(self):
        path = route_builder.build_simulated_route_path("SULOM", "SULOM L509 LAJAK")
        self.assertGreaterEqual(len(path), 4, "L509 must expand via airspace_route_rules")
        _, total_nm = cumulative_nm_polyline(path)
        self.assertGreater(total_nm, 100.0, "L509 leg should add substantial track distance")

    def test_build_path_merun_l750_biros_uses_airway_polyline(self):
        path = route_builder.build_simulated_route_path("MERUN", "MERUN L750 BIROS")
        self.assertGreaterEqual(len(path), 3, "L750 must expand via airspace_route_rules")
        _, total_nm = cumulative_nm_polyline(path)
        self.assertGreater(total_nm, 150.0, "L750 leg should add substantial track distance")

    def test_vikit_rk_l750_biros_skips_merun_vertex(self):
        """Filed join at RK: do not run L750 from MERUN after VIKIT (trim airway at anchor)."""
        path = route_builder.build_simulated_route_path("VIKIT", "VIKIT RK L750 BIROS")
        self.assertGreaterEqual(len(path), 3)
        wps = route_builder.all_waypoints_latlon()
        rk = wps["RK"]
        merun = wps["MERUN"]
        self.assertLess(
            haversine_nm(path[1][0], path[1][1], rk[0], rk[1]),
            1.0,
            "second vertex should be RK on L750, not MERUN",
        )
        self.assertGreater(
            haversine_nm(path[1][0], path[1][1], merun[0], merun[1]),
            5.0,
            "second vertex must not be MERUN (old full-L750-from-start behavior)",
        )

    def test_sulom_a466_m875_chain_uses_jhang_not_gugal(self):
        """Direct A466 then M875: trim M875 from end of A466 (JHANG), not from GUGAL."""
        path = route_builder.build_simulated_route_path("SULOM", "SULOM A466 M875 LAJAK")
        self.assertGreaterEqual(len(path), 4)
        wps = route_builder.all_waypoints_latlon()
        jh = wps["JHANG"]
        gg = wps["GUGAL"]
        self.assertLess(haversine_nm(path[1][0], path[1][1], jh[0], jh[1]), 1.0)
        self.assertGreater(haversine_nm(path[1][0], path[1][1], gg[0], gg[1]), 50.0)

    def test_sulom_a466_jhang_m875_hangu_lajak_non_degenerate(self):
        path = route_builder.build_simulated_route_path(
            "SULOM",
            "SULOM A466 JHANG M875 HANGU LAJAK",
        )
        self.assertGreaterEqual(len(path), 5)
        _, total_nm = cumulative_nm_polyline(path)
        self.assertGreater(total_nm, 200.0)

    def test_g325_bidirectional_same_track_length(self):
        fwd = route_builder.build_simulated_route_path("PURPA", "PURPA G325 ASSVIB")
        rev = route_builder.build_simulated_route_path("ASSVIB", "ASSVIB G325 PURPA")
        self.assertGreaterEqual(len(fwd), 3)
        self.assertGreaterEqual(len(rev), 3)
        _, total_fwd = cumulative_nm_polyline(fwd)
        _, total_rev = cumulative_nm_polyline(rev)
        self.assertAlmostEqual(total_fwd, total_rev, delta=2.0)

        purpa = route_builder.resolve_fir_entry_lat_lon("PURPA")
        assvib = route_builder.resolve_fir_entry_lat_lon("ASSVIB")
        assert purpa is not None and assvib is not None
        self.assertLess(
            haversine_nm(fwd[-1][0], fwd[-1][1], assvib[0], assvib[1]),
            1.0,
            "forward path should end near ASSVIB",
        )
        self.assertLess(
            haversine_nm(rev[-1][0], rev[-1][1], purpa[0], purpa[1]),
            1.0,
            "reverse path should end near PURPA",
        )
        self.assertGreater(
            haversine_nm(fwd[1][0], fwd[1][1], rev[1][0], rev[1][1]),
            50.0,
            "second vertices should lie on opposite legs of G325",
        )

    def test_slice_falls_back_to_route_start_when_fir_token_not_in_route(self):
        """MERUN omitted from route text: slice from 0; orient L750 from resolved MERUN."""
        path = route_builder.build_simulated_route_path("MERUN", "L750 BIROS")
        self.assertGreaterEqual(len(path), 3)
        _, total_nm = cumulative_nm_polyline(path)
        self.assertGreater(total_nm, 150.0)


if __name__ == "__main__":
    unittest.main()
