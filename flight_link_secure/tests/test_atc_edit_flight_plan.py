"""In-place flight plan text update (ATC edit)."""
import unittest

from app import create_app
from app.extensions import db
from app.models import FlightPlan, TrackData, User
from app.services import atc_service


RAW_A = (
    "(FPL-EDIT1-IS\n"
    "-A320/M\n"
    "-OPLA2300\n"
    "-N0450F350 SULOM\n"
    "-EGLL0500)"
)
RAW_B = (
    "(FPL-EDIT1-IS\n"
    "-A320/M\n"
    "-OPLA2300\n"
    "-N0450F350 GUGAL\n"
    "-EGLL0500)"
)


class EditFlightPlanServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        u = User(username="atc_edit", role="atc")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
        self.user_id = u.id
        self.plan = FlightPlan(callsign="EDIT1", raw_flight_plan=RAW_A)
        db.session.add(self.plan)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_edit_updates_raw_text_in_place(self):
        out = atc_service.edit_flight_plan_post(self.plan, RAW_B)
        self.assertEqual(out["action"], "redirect")
        db.session.refresh(self.plan)
        self.assertIn("GUGAL", self.plan.raw_flight_plan)
        self.assertEqual(self.plan.callsign, "EDIT1")

    def test_edit_blocked_with_active_track(self):
        t = TrackData(
            flight_plan_id=self.plan.id,
            callsign="EDIT1",
            aircraft_type="A320",
            departure="OPLA",
            destination="EGLL",
            fir_entry="SULOM",
            speed="N0450",
            route="SULOM",
            eto_utc="0000",
            eto_pst="0500",
            cfl="350",
            ssr="1234",
            status="active",
            sent_to_defense=False,
            created_by=self.user_id,
        )
        db.session.add(t)
        db.session.commit()

        out = atc_service.edit_flight_plan_post(self.plan, RAW_B)
        self.assertEqual(out["action"], "render")
        db.session.refresh(self.plan)
        self.assertIn("SULOM", self.plan.raw_flight_plan)


if __name__ == "__main__":
    unittest.main()
