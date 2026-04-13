"""Pairwise separation."""
import unittest

from app.services.separation_engine import SEPARATION_THRESHOLD_NM, TrackSnapshot, find_conflict_ids


class SeparationEngineTests(unittest.TestCase):
    def test_same_fl_close_triggers(self):
        a = TrackSnapshot(id=1, lat=30.0, lon=70.0, cfl=350)
        b = TrackSnapshot(id=2, lat=30.05, lon=70.05, cfl=350)
        ids = find_conflict_ids([a, b])
        self.assertEqual(ids, {1, 2})

    def test_different_fl_no_trigger(self):
        a = TrackSnapshot(id=1, lat=30.0, lon=70.0, cfl=350)
        b = TrackSnapshot(id=2, lat=30.0, lon=70.0, cfl=360)
        self.assertEqual(find_conflict_ids([a, b]), set())

    def test_far_apart_no_trigger(self):
        a = TrackSnapshot(id=1, lat=30.0, lon=70.0, cfl=350)
        b = TrackSnapshot(id=2, lat=35.0, lon=75.0, cfl=350)
        ids = find_conflict_ids([a, b])
        self.assertEqual(ids, set())
        self.assertGreater(
            __import__("app.services.kinematics", fromlist=["haversine_nm"]).haversine_nm(
                a.lat, a.lon, b.lat, b.lon
            ),
            SEPARATION_THRESHOLD_NM,
        )


if __name__ == "__main__":
    unittest.main()
