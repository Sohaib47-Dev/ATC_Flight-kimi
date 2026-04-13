"""ATC deactivate-track route and service."""
import unittest
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import FlightPlan, TrackData, User


class DeactivateTrackServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(username='atc1', role='atc')
        self.user.set_password('pw')
        db.session.add(self.user)
        db.session.commit()
        plan = FlightPlan(callsign='TST01', raw_flight_plan='(FPL-TST01-IS\n-A320/M\n-OPLA2300\n-N0450F350 SULOM\n-EGLL0500)')
        db.session.add(plan)
        db.session.commit()
        self.track = TrackData(
            flight_plan_id=plan.id,
            callsign='TST01',
            aircraft_type='A320',
            departure='OPLA',
            destination='EGLL',
            fir_entry='SULOM',
            speed='N0450',
            route='SULOM',
            eto_utc='0100',
            eto_pst='0600',
            cfl='350',
            ssr='1234',
            status='active',
            created_by=self.user.id,
        )
        db.session.add(self.track)
        db.session.commit()
        self.track_id = self.track.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_deactivate_success(self):
        from app.services import atc_service

        t = atc_service.deactivate_track(self.track_id, self.user)
        self.assertEqual(t.status, 'terminated')
        self.assertIsNotNone(t.completed_at)

    def test_deactivate_not_found(self):
        from app.services import atc_service

        with self.assertRaises(atc_service.TrackNotFoundError):
            atc_service.deactivate_track(99999, self.user)

    def test_deactivate_already_inactive(self):
        from app.services import atc_service

        atc_service.deactivate_track(self.track_id, self.user)
        with self.assertRaises(atc_service.TrackAlreadyInactiveError):
            atc_service.deactivate_track(self.track_id, self.user)


class DeactivateTrackRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.user = User(username='atc2', role='atc')
        self.user.set_password('pw')
        db.session.add(self.user)
        db.session.commit()
        plan = FlightPlan(callsign='TST02', raw_flight_plan='(FPL-TST02-IS\n-A320/M\n-OPLA2300\n-N0450F350 SULOM\n-EGLL0500)')
        db.session.add(plan)
        db.session.commit()
        self.track = TrackData(
            flight_plan_id=plan.id,
            callsign='TST02',
            aircraft_type='A320',
            departure='OPLA',
            destination='EGLL',
            fir_entry='SULOM',
            speed='N0450',
            route='SULOM',
            eto_utc='0100',
            eto_pst='0600',
            cfl='350',
            ssr='5678',
            status='active',
            created_by=self.user.id,
        )
        db.session.add(self.track)
        db.session.commit()
        self.track_id = self.track.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

    def test_route_success_json(self):
        self._login()
        rv = self.client.post(f'/atc/deactivate-track/{self.track_id}')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'"ok":true', rv.data)
        with self.app.app_context():
            t = TrackData.query.get(self.track_id)
            self.assertEqual(t.status, 'terminated')

    def test_route_already_inactive(self):
        self._login()
        self.client.post(f'/atc/deactivate-track/{self.track_id}')
        rv = self.client.post(f'/atc/deactivate-track/{self.track_id}')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Track is already inactive', rv.data)

    def test_route_not_found(self):
        self._login()
        rv = self.client.post('/atc/deactivate-track/99999')
        self.assertEqual(rv.status_code, 404)


if __name__ == '__main__':
    unittest.main()
