"""ICAO structured form build/parse helpers."""
import unittest

from modules.flight_plan_form_io import build_icao_fpl, parse_raw_to_form_fields
from modules.flight_plan_parser import FlightPlanParser

RAW_MIN = (
    "(FPL-EDIT1-IS\n"
    "-A320/M\n"
    "-OPLA2300\n"
    "-N0450F350 SULOM\n"
    "-EGLL0500)"
)


class FlightPlanFormIoTests(unittest.TestCase):
    def test_build_requires_core_fields(self):
        with self.assertRaises(ValueError):
            build_icao_fpl({"callsign": "X", "aircraft_type": "A320", "departure_aerodrome": "OPLA", "route": "SULOM"})
        with self.assertRaises(ValueError):
            build_icao_fpl(
                {
                    "callsign": "AB12",
                    "aircraft_type": "A320",
                    "departure_aerodrome": "OPLA",
                    "destination_aerodrome": "EGLL",
                    "route": "",
                }
            )

    def test_roundtrip_minimal_matches_parser(self):
        fields, _notes = parse_raw_to_form_fields(RAW_MIN)
        rebuilt = build_icao_fpl(fields)
        p = FlightPlanParser()
        r = p.parse(rebuilt)
        self.assertIsNotNone(r)
        self.assertEqual(r.callsign, "EDIT1")
        self.assertEqual(r.departure, "OPLA")
        self.assertEqual(r.destination, "EGLL")
        self.assertEqual(r.fir_entry, "SULOM")
        self.assertIn("SULOM", r.route)

    def test_build_then_parse_equipment_line(self):
        d = {
            "callsign": "ABC12",
            "flight_rules": "I",
            "type_of_flight": "S",
            "aircraft_type": "B77W",
            "wake_turbulence": "H",
            "equipment": "SDE2FGHIRW/LB1",
            "departure_aerodrome": "OMDB",
            "departure_time_utc": "0800",
            "cruise_speed": "N0490",
            "flight_level": "F370",
            "route": "DCT PETAR",
            "destination_aerodrome": "EGLL",
            "destination_time_utc": "0500",
        }
        raw = build_icao_fpl(d)
        self.assertIn("-B77W/H-SDE2FGHIRW/LB1", raw)
        p = FlightPlanParser()
        self.assertIsNotNone(p.parse(raw))
