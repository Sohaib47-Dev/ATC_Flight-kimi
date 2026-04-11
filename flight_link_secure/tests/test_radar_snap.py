"""Tests for FIR polyline snapping (radar_service)."""
import unittest

from app.services.radar_service import snap_lat_lon_to_polyline


class SnapPolylineTests(unittest.TestCase):
    def test_snap_to_segment_endpoint(self):
        poly = [(0.0, 0.0), (0.0, 10.0)]
        la, lo = snap_lat_lon_to_polyline(0.0, 5.0, poly)
        self.assertAlmostEqual(la, 0.0)
        self.assertAlmostEqual(lo, 5.0)

    def test_snap_off_segment_clamped(self):
        poly = [(0.0, 0.0), (0.0, 2.0)]
        la, lo = snap_lat_lon_to_polyline(1.0, 5.0, poly)
        self.assertAlmostEqual(la, 0.0)
        self.assertAlmostEqual(lo, 2.0)

    def test_short_polyline_returns_original(self):
        la, lo = snap_lat_lon_to_polyline(3.0, 4.0, [(1.0, 1.0)])
        self.assertEqual(la, 3.0)
        self.assertEqual(lo, 4.0)


if __name__ == '__main__':
    unittest.main()
