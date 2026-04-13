"""Slim WebSocket payload for defense radar (no resolved_path)."""
import unittest

from app.services.simulation_service import defense_tracks_minimal_ws_payload


class DefenseWsPayloadTests(unittest.TestCase):
    def test_minimal_payload_omits_heavy_fields(self):
        full_rows = [
            {
                "id": 7,
                "lat": 30.1,
                "lon": 70.2,
                "cfl": 350,
                "callsign": "TST01",
                "aircraft_type": "A320",
                "departure": "OPLA",
                "destination": "EGLL",
                "fir_entry": "GUGAL",
                "route": "GUGAL DCT",
                "speed": "N0450",
                "eto_utc": "2300",
                "ssr": "1234",
                "created_at": "2026-01-01T00:00:00",
                "conflict": False,
                "sim_active": True,
                "status": "active",
                "sim_source": "server",
                "resolved_path": [{"lat": 30.0, "lon": 70.0}, {"lat": 31.0, "lon": 71.0}],
                "x": 100.0,
                "y": 200.0,
            }
        ]
        minimal = defense_tracks_minimal_ws_payload(full_rows)
        self.assertEqual(len(minimal), 1)
        m = minimal[0]
        self.assertEqual(m["id"], 7)
        self.assertEqual(m["lat"], 30.1)
        self.assertEqual(m["lon"], 70.2)
        self.assertEqual(m["cfl"], 350)
        self.assertEqual(m["callsign"], "TST01")
        self.assertEqual(m["sim_source"], "server")
        self.assertNotIn("resolved_path", m)
        self.assertNotIn("x", m)


if __name__ == "__main__":
    unittest.main()
