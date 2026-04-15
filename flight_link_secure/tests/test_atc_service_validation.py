import unittest

from app import create_app
from app.extensions import db
from app.models import FlightPlan, TrackData, User
from app.services import atc_service


VALID_FPL = """(FPL-PIA777-IS
-B77W/H-SDE2E3FGHIRW/LB1
-OPKC2300
-N0450F350 SULOM DCT GUGAL
-OPLA0500
-DOF/260415
)"""


class AtcServiceValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        user = User(username="tester", role="atc")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_add_flight_plan_rejects_invalid_callsign(self):
        result = atc_service.add_flight_plan_post("A-123", VALID_FPL, False)
        self.assertEqual(result["action"], "render")
        self.assertEqual(FlightPlan.query.count(), 0)

    def test_add_flight_plan_accepts_valid_and_persists(self):
        result = atc_service.add_flight_plan_post("PIA777", VALID_FPL, False)
        self.assertEqual(result["action"], "redirect")
        self.assertEqual(FlightPlan.query.count(), 1)

    def test_get_api_flight_plan_rejects_bad_callsign_input(self):
        ok, payload, code = atc_service.get_api_flight_plan("BAD-INPUT")
        self.assertFalse(ok)
        self.assertEqual(code, 400)
        self.assertIn("Callsign", payload["error"])

    def test_estimate_submission_rejects_invalid_parsed_identifiers(self):
        fp = FlightPlan(callsign="PIA777", raw_flight_plan=VALID_FPL)
        db.session.add(fp)
        db.session.commit()

        parsed_data = {
            "callsign": "PIA777",
            "aircraft_type": "ZZZZ",
            "departure": "OPKC",
            "destination": "OPLA",
            "fir_entry": "SULOM",
            "speed": "N0450",
            "route": "SULOM DCT GUGAL",
        }
        outcome = atc_service.process_estimates_submission(parsed_data, fp.id, self.user_id, "1200", "350", "4451")
        self.assertFalse(outcome["submitted"])
        self.assertFalse(outcome["validation_result"]["valid"])
        self.assertEqual(TrackData.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
