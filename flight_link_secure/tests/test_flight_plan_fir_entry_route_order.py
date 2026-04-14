"""FIR entry extraction follows route token order when possible."""
import unittest

from app.services import route_builder
from app.services.kinematics import cumulative_nm_polyline
from modules.flight_plan_parser import FlightPlanParser

# ICAO-style transit example (field 9–18 style); RMK mentions SULOM/RAZEX; route uses SULOM/L509/LAJAK.
PAKTRN01_ICAO_FPL = (
    "(FPL-PAKTRN01-IS\n"
    "-B77W/H-SDE3FGHIRWXYZ/LB1\n"
    "-OMDB0800\n"
    "-N0450F360 A333 LAKET ASARI A466 SULOM L509 LAJAK N893 SASVI DCT NINUD\n"
    "-VIDP0150 OOMS\n"
    "-PBN/A1B1C1D1L1O1S2 NAV/RNP10 DOF/260414 REG/AP-BTX CALLSIGN/PAKTRN01\n"
    "-E/0700 P/18 R/200 S/FOB25000KG\n"
    "-COMM/CPDLC VHF HF SAT\n"
    "-DOF/260414 REG/AP-BTX EET/OPKR0035 OPKL0105\n"
    "-E/SEL/ABCD PER/D\n"
    "-ALTN/OPIS OOMS\n"
    "-RMK/TRANSIT FLIGHT ENTERING PAKISTAN FIR VIA SULOM, EXIT VIA RAZEX, "
    "ALL SYSTEMS NORMAL, NO DANGER CARGO\n"
    ")"
)


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

    def test_paktrn01_transit_full_message_parses(self):
        p = FlightPlanParser()
        r = p.parse(PAKTRN01_ICAO_FPL)
        self.assertIsNotNone(r, p.get_errors())
        self.assertEqual(r.callsign, "PAKTRN01")
        self.assertEqual(r.aircraft_type, "B77W")
        self.assertEqual(r.departure, "OMDB")
        self.assertEqual(r.destination, "VIDP")
        self.assertEqual(r.speed, "N0450")
        self.assertEqual(r.fir_entry, "SULOM")
        self.assertIn("SULOM", r.route)
        self.assertIn("L509", r.route)

    def test_paktrn01_route_simulated_path_non_degenerate(self):
        p = FlightPlanParser()
        r = p.parse(PAKTRN01_ICAO_FPL)
        self.assertIsNotNone(r)
        path = route_builder.build_simulated_route_path(r.fir_entry, r.route)
        self.assertGreaterEqual(len(path), 2, "SULOM + L509/LAJAK should yield a drawable path")
        _, total_nm = cumulative_nm_polyline(path)
        self.assertGreater(total_nm, 50.0, "L509 leg should add meaningful distance")

    def test_lajak_before_sulom_in_route_fir_entry_is_lajak(self):
        raw = (
            "(FPL-LASUL-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 LAJAK DCT SULOM A466 LAJAK\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.fir_entry, "LAJAK")

    def test_compact_fpl_eet_after_destination_still_vidp(self):
        """EET OPKR0035 style tokens after dest must not become destination."""
        raw = (
            "(FPL-EET01-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OMDB0800\n"
            "-N0450F350 SULOM A466 LAJAK\n"
            "-VIDP0150\n"
            "-PBN/A1 EET/OPKR0035 OPKL0105\n"
            "-REG/APABC RMK/TCAS)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.departure, "OMDB")
        self.assertEqual(r.destination, "VIDP")

    def test_rmk_space_cutoff_excludes_late_false_destination_pair(self):
        """` RMK ` cutoff: pair after RMK must not shift destination."""
        raw = (
            "(FPL-RMKCUT-IS\n"
            "-A320/M-SDE2E3FGHIRWY/LB1\n"
            "-OPLA2300\n"
            "-N0450F350 SULOM A466 LAJAK\n"
            "-EGLL0500\n"
            "-REG/APABC RMK/NOTE OPLA0500 ALTN INFO\n"
            "-EET/OPKR0035)"
        )
        p = FlightPlanParser()
        r = p.parse(raw)
        self.assertIsNotNone(r)
        self.assertEqual(r.departure, "OPLA")
        self.assertEqual(r.destination, "EGLL")


if __name__ == "__main__":
    unittest.main()
