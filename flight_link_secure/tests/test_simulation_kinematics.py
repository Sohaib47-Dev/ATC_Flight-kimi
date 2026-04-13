"""Kinematics helpers for server radar simulation."""
import unittest

from app.services import kinematics


class KinematicsTests(unittest.TestCase):
    def test_knots_to_nm_per_sec(self):
        self.assertAlmostEqual(kinematics.knots_to_nm_per_sec(450), 0.125, places=6)

    def test_parse_speed_n(self):
        self.assertEqual(kinematics.parse_speed_to_knots("N0450"), 450)

    def test_parse_speed_n_tolerant_digit_count(self):
        self.assertEqual(kinematics.parse_speed_to_knots("N01220"), 1220)

    def test_latlon_to_svg_corners(self):
        x0, y0 = kinematics.latlon_to_svg_xy(kinematics.LAT_MIN, kinematics.LON_MIN)
        self.assertGreater(x0, 0)
        self.assertGreater(y0, 0)

    def test_interpolate_polyline(self):
        pts = [(0.0, 0.0), (0.0, 1.0)]
        cum, total = kinematics.cumulative_nm_polyline(pts)
        la, lo = kinematics.interpolate_along_polyline(pts, cum, total / 2)
        self.assertAlmostEqual(la, 0.0, places=5)
        self.assertGreater(abs(lo), 0)


if __name__ == "__main__":
    unittest.main()
