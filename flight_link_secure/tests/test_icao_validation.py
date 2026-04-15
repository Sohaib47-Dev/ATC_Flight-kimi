import unittest

from modules.icao_validation import (
    validate_aircraft_type,
    validate_callsign,
    validate_icao_airport,
)


class IcaoValidationTests(unittest.TestCase):
    def test_callsign_valid_formats(self):
        for callsign in ("PIA777", "N123AB", "APABC", "AIC52A"):
            ok, _ = validate_callsign(callsign)
            self.assertTrue(ok, callsign)

    def test_callsign_invalid_formats(self):
        for callsign in ("AB", "PI@777", "TOOLONG8", "A-123"):
            ok, _ = validate_callsign(callsign)
            self.assertFalse(ok, callsign)

    def test_aircraft_type_validation(self):
        for ac in ("A320", "B77W", "EC35", "C172"):
            ok, _ = validate_aircraft_type(ac)
            self.assertTrue(ok, ac)
        for ac in ("1234", "A3200", "ZZZZ", "A"):
            ok, _ = validate_aircraft_type(ac)
            self.assertFalse(ok, ac)

    def test_airport_validation(self):
        self.assertTrue(validate_icao_airport("OPKC")[0])
        self.assertFalse(validate_icao_airport("KHI")[0])
        self.assertFalse(validate_icao_airport("12KC")[0])


if __name__ == "__main__":
    unittest.main()
