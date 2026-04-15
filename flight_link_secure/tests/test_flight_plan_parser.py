import unittest

from modules.flight_plan_parser import FlightPlanParser


VALID_FPL = """(FPL-PIA777-IS
-B77W/H-SDE2E3FGHIRW/LB1
-OPKC2300
-N0450F350 SULOM DCT GUGAL
-OPLA0500
-DOF/260415
)"""


class FlightPlanParserTests(unittest.TestCase):
    def test_valid_plan_is_parsed(self):
        parser = FlightPlanParser()
        parsed = parser.parse(VALID_FPL)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.callsign, "PIA777")
        self.assertEqual(parsed.aircraft_type, "B77W")
        self.assertEqual(parsed.departure, "OPKC")
        self.assertEqual(parsed.destination, "OPLA")

    def test_invalid_aircraft_type_is_rejected(self):
        parser = FlightPlanParser()
        raw = VALID_FPL.replace("-B77W/H", "-ZZZZ/H")
        parsed = parser.parse(raw)
        self.assertIsNone(parsed)
        self.assertIn("Could not extract aircraft type", ", ".join(parser.get_errors()))

    def test_invalid_destination_code_is_rejected(self):
        parser = FlightPlanParser()
        raw = VALID_FPL.replace("-OPLA0500", "-KHI0500")
        parsed = parser.parse(raw)
        self.assertIsNone(parsed)
        self.assertIn("Could not extract destination aerodrome", ", ".join(parser.get_errors()))


if __name__ == "__main__":
    unittest.main()
