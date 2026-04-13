"""Server-side radar simulation advance + API payload."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import FlightPlan, TrackData, User


class SimulationServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        u = User(username="def1", role="defense")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
        plan = FlightPlan(
            callsign="SIM1",
            raw_flight_plan="(FPL-SIM1-IS\n-A320/M\n-OPLA2300\n-N0450F350 SULOM\n-EGLL0500)",
        )
        db.session.add(plan)
        db.session.commit()
        self.track = TrackData(
            flight_plan_id=plan.id,
            callsign="SIM1",
            aircraft_type="A320",
            departure="OPLA",
            destination="EGLL",
            fir_entry="GUGAL",
            speed="N0450",
            route="GUGAL M875 M881 LAJAK",
            eto_utc="0000",
            eto_pst="0500",
            cfl="350",
            ssr="4321",
            status="active",
            sent_to_defense=True,
            created_by=u.id,
        )
        db.session.add(self.track)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_advance_payload_has_server_fields(self):
        from app.services import simulation_service

        with self.app.test_request_context("/"):
            rows = simulation_service.advance_defense_tracks_and_build_payload()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["sim_source"], "server")
        self.assertIn("x", r)
        self.assertIn("y", r)
        self.assertIn("lat", r)
        self.assertIn("lon", r)
        self.assertIn("resolved_path", r)
        self.assertIsInstance(r["resolved_path"], list)
        self.assertGreater(len(r["resolved_path"]), 1)
        self.assertIn("conflict", r)
        self.assertFalse(r["conflict"])


class SimulationRealtimeMotionTests(unittest.TestCase):
    """Two simulated radar polls with faked wall clock so ``dt`` > 0 and the track moves."""

    def setUp(self):
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        u = User(username="def_motion", role="defense")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
        plan = FlightPlan(
            callsign="MOVE1",
            raw_flight_plan="(FPL-MOVE1-IS\n-A320/M\n-OPLA2300\n-N0450F350 GUGAL\n-EGLL0500)",
        )
        db.session.add(plan)
        db.session.commit()
        self.track = TrackData(
            flight_plan_id=plan.id,
            callsign="MOVE1",
            aircraft_type="A320",
            departure="OPLA",
            destination="EGLL",
            fir_entry="GUGAL",
            speed="N0450",
            route="GUGAL M875 M881 LAJAK",
            eto_utc="0000",
            eto_pst="0500",
            cfl="350",
            ssr="9999",
            status="active",
            sent_to_defense=True,
            created_by=u.id,
        )
        db.session.add(self.track)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_aircraft_advances_along_route_between_polls(self):
        """First poll: ``dt==0`` (anchor time). Second poll: +180s → distance along path increases."""
        from app.services import kinematics
        from app.services import simulation_service

        t0 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(seconds=180)

        with self.app.test_request_context("/"):
            with patch.object(simulation_service, "_now_utc", side_effect=[t0, t1]):
                r1 = simulation_service.advance_defense_tracks_and_build_payload()[0]
                r2 = simulation_service.advance_defense_tracks_and_build_payload()[0]

        self.assertGreater(r1["path_total_nm"], 0, "route must resolve to a multi-point path")
        self.assertAlmostEqual(r1["along_nm"], 0.0, places=4)
        self.assertGreater(r2["along_nm"], 18.0, "450 kt for 180s ≈ 22.5 NM along track")
        nm_moved = kinematics.haversine_nm(r1["lat"], r1["lon"], r2["lat"], r2["lon"])
        self.assertGreater(nm_moved, 10.0, "position must move on the map between polls")


class SimulationDegenerateRouteTests(unittest.TestCase):
    """Empty / non-airway route used to yield one path vertex and zero ``along_nm`` advance."""

    def setUp(self):
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        u = User(username="def_deg", role="defense")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
        plan = FlightPlan(
            callsign="DEG1",
            raw_flight_plan="(FPL-DEG1-IS\n-A320/M\n-OPLA2300\n-N0450F350 SULOM\n-EGLL0500)",
        )
        db.session.add(plan)
        db.session.commit()
        self.track = TrackData(
            flight_plan_id=plan.id,
            callsign="DEG1",
            aircraft_type="A320",
            departure="OPLA",
            destination="EGLL",
            fir_entry="SULOM",
            speed="N0450",
            route="",
            eto_utc="0000",
            eto_pst="0500",
            cfl="350",
            ssr="1111",
            status="active",
            sent_to_defense=True,
            created_by=u.id,
        )
        db.session.add(self.track)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_degenerate_route_advances_between_polls(self):
        from app.services import simulation_service

        t0 = datetime(2026, 7, 1, 8, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(seconds=120)

        with self.app.test_request_context("/"):
            with patch.object(simulation_service, "_now_utc", side_effect=[t0, t1]):
                r1 = simulation_service.advance_defense_tracks_and_build_payload()[0]
                r2 = simulation_service.advance_defense_tracks_and_build_payload()[0]

        self.assertGreaterEqual(len(r1["resolved_path"]), 2, "fallback segment should yield >= 2 vertices")
        self.assertGreater(r1["path_total_nm"], 0, "path length must be non-zero for sim advance")
        self.assertAlmostEqual(r1["along_nm"], 0.0, places=4)
        self.assertGreater(r2["along_nm"], r1["along_nm"], "track must advance along fallback segment")
        self.assertLessEqual(r2["along_nm"], r1["path_total_nm"] + 0.05, "along_nm clamps to path length")
        self.assertGreater(r2["along_nm"], 2.0, "120s at 450kt exceeds ~3 NM segment — should reach path end")


if __name__ == "__main__":
    unittest.main()
