"""FIR entry extraction follows route token order when possible."""
import unittest

from modules.flight_plan_parser import FlightPlanParser


class FirEntryRouteOrderTests(unittest.TestCase):
    def test_route_order_prefers_first_fix_in_route(self):
        raw = (
            "(FPL-TEST01-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 GUGAL DCT SULOM DCT A466 DCT LAJAK\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "GUGAL")

    def test_sulom_before_gugal_in_route(self):
        raw = (
            "(FPL-TEST02-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 SULOM DCT GUGAL DCT\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "SULOM")

    def test_airway_m881_not_classified_as_mach_speed(self):
        raw = (
            "(FPL-PIA301-IS\n"
            "-A320/M\n"
            "-OPLA2300\n"
            "-N0450F350 SULOM A466 M881 LAJAK\n"
            "-EGLL0500)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.speed, "N0450")
        self.assertIn("M881", r.route)
        self.assertEqual(r.fir_entry, "SULOM")

    def test_nonstandard_n_speed_width_still_extracts_route_and_fir_entry(self):
        """N01220F370 is not ICAO 4-digit TAS; tolerant parser must still see GUGAL."""
        raw = (
            "(FPL-PIA402-IS -B789/H-SDE2E3FGHIRW/LB1 -OPLA2330 -N01220F370 "
            "GUGAL DCT M875 DCT M881 DCT LAJAK -EGLL0515 -REG/APABC123 RMK/TCAS EQUIPPED)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "GUGAL")
        self.assertEqual(r.speed, "N01220")
        self.assertIn("M881", r.route)

    def test_lajak_in_entry_points_first_in_route(self):
        raw = (
            "(FPL-LJK01-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 LAJAK DCT SIRKA DCT\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "LAJAK")

    def test_assvib_first_in_route(self):
        raw = (
            "(FPL-ASV01-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 ASSVIB DCT TELEM DCT\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "ASSVIB")

    def test_legacy_dodat_route_token_maps_to_dobat(self):
        raw = (
            "(FPL-DDT01-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 DODAT DCT SIRKA DCT\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "DOBAT")


if __name__ == "__main__":
    unittest.main()
