import unittest

from modules.flight_plan_form_io import build_icao_fpl, parse_raw_to_form_fields


class FlightPlanFormIoTests(unittest.TestCase):
    def test_build_icao_fpl_accepts_valid_identifiers(self):
        raw = build_icao_fpl(
            {
                "callsign": "PIA777",
                "aircraft_type": "B77W",
                "departure_aerodrome": "OPKC",
                "destination_aerodrome": "OPLA",
                "route": "SULOM DCT GUGAL",
            }
        )
        self.assertIn("(FPL-PIA777-", raw)
        self.assertIn("-B77W/", raw)
        self.assertIn("-OPKC", raw)
        self.assertIn("-OPLA", raw)

    def test_build_icao_fpl_rejects_invalid_identifiers(self):
        with self.assertRaises(ValueError):
            build_icao_fpl(
                {
                    "callsign": "A-123",
                    "aircraft_type": "B77W",
                    "departure_aerodrome": "OPKC",
                    "destination_aerodrome": "OPLA",
                    "route": "SULOM DCT GUGAL",
                }
            )
        with self.assertRaises(ValueError):
            build_icao_fpl(
                {
                    "callsign": "PIA777",
                    "aircraft_type": "ZZZZ",
                    "departure_aerodrome": "OPKC",
                    "destination_aerodrome": "OPLA",
                    "route": "SULOM DCT GUGAL",
                }
            )
        with self.assertRaises(ValueError):
            build_icao_fpl(
                {
                    "callsign": "PIA777",
                    "aircraft_type": "B77W",
                    "departure_aerodrome": "KHI",
                    "destination_aerodrome": "OPLA",
                    "route": "SULOM DCT GUGAL",
                }
            )

    def test_parse_raw_to_form_fields_reports_invalid_destination(self):
        raw = """(FPL-PIA777-IS
-B77W/H
-OPKC2300
-N0450F350 SULOM DCT GUGAL
-KHI0500
)"""
        fields, notes = parse_raw_to_form_fields(raw)
        self.assertEqual(fields["destination_aerodrome"], "")
        self.assertTrue(any("Destination line" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
