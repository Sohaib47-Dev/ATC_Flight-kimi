"""Route compilation from radar_airways.json."""
import unittest

from app.services import route_builder


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


if __name__ == "__main__":
    unittest.main()
