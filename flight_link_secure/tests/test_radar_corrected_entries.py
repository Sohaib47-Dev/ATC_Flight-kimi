"""Tests for corrected FIR entry coordinates (radar_service)."""
import unittest

from app.services import radar_service


class CorrectedEntryPointsTests(unittest.TestCase):
    def test_resolve_sulom(self):
        la, lo = radar_service.resolve_fir_entry_lat_lon("SULOM")
        self.assertAlmostEqual(la, 31.338018132990058, places=9)
        self.assertAlmostEqual(lo, 74.47071723937988, places=9)

    def test_dodat_alias_to_dobat(self):
        la, lo = radar_service.resolve_fir_entry_lat_lon("DODAT")
        self.assertEqual(
            (la, lo),
            radar_service.CORRECTED_ENTRY_POINTS["DOBAT"],
        )

    def test_unknown_returns_none(self):
        self.assertIsNone(radar_service.resolve_fir_entry_lat_lon("NOTAPOINT"))

    def test_reget_not_in_corrected(self):
        self.assertIsNone(radar_service.resolve_fir_entry_lat_lon("REGET"))


if __name__ == "__main__":
    unittest.main()
