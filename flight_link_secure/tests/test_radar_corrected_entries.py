"""Tests for corrected FIR entry coordinates (radar_service)."""
import unittest

from app.services import radar_service


class CorrectedEntryPointsTests(unittest.TestCase):
    def test_resolve_sulom(self):
        la, lo = radar_service.resolve_fir_entry_lat_lon("SULOM")
        self.assertAlmostEqual(la, 30.509690024636008, places=9)
        self.assertAlmostEqual(lo, 73.93968505859375, places=9)

    def test_resolve_gugal(self):
        la, lo = radar_service.resolve_fir_entry_lat_lon("GUGAL")
        self.assertAlmostEqual(la, 30.045302068536934, places=9)
        self.assertAlmostEqual(lo, 73.4627399444580, places=9)

    def test_dodat_alias_to_dobat(self):
        la, lo = radar_service.resolve_fir_entry_lat_lon("DODAT")
        self.assertEqual(
            (la, lo),
            radar_service.CORRECTED_ENTRY_POINTS["DOBAT"],
        )

    def test_unknown_returns_none(self):
        self.assertIsNone(radar_service.resolve_fir_entry_lat_lon("NOTAPOINT"))

    def test_reget_resolves_via_fir_reference_marker(self):
        la, lo = radar_service.resolve_fir_entry_lat_lon("REGET")
        self.assertIsNotNone(la)
        self.assertAlmostEqual(la, 31.15090293190696, places=9)
        self.assertAlmostEqual(lo, 69.21194648742676, places=9)


if __name__ == "__main__":
    unittest.main()
