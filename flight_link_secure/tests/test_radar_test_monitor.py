"""Unit tests for radar FIR stress-test monitor helpers."""
import unittest

from app.services.radar_test_monitor import min_nm_to_resolved_path


class RadarTestMonitorHelpersTests(unittest.TestCase):
    def test_min_nm_on_segment_near_zero(self):
        path = [
            {"lat": 30.0, "lon": 70.0},
            {"lat": 31.0, "lon": 71.0},
        ]
        d = min_nm_to_resolved_path(30.5, 70.5, path)
        self.assertLess(d, 50.0)

    def test_min_nm_far_from_path(self):
        path = [
            {"lat": 30.0, "lon": 70.0},
            {"lat": 30.1, "lon": 70.1},
        ]
        d = min_nm_to_resolved_path(35.0, 75.0, path)
        self.assertGreater(d, 100.0)


if __name__ == "__main__":
    unittest.main()
