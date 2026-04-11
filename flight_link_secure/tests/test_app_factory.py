"""Smoke tests for application factory and URL map (stdlib unittest — no pytest required)."""
import unittest

from app import create_app


class AppFactoryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()

    def test_create_app_testing(self):
        self.assertTrue(self.app.config['TESTING'])

    def test_index_returns_200(self):
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)

    def test_login_page_get(self):
        rv = self.client.get('/login')
        self.assertEqual(rv.status_code, 200)

    def test_known_routes_registered(self):
        rules = {str(r.rule) for r in self.app.url_map.iter_rules()}
        self.assertIn('/', rules)
        self.assertIn('/login', rules)
        self.assertIn('/admin/dashboard', rules)
        self.assertIn('/atc/dashboard', rules)
        self.assertIn('/defense/dashboard', rules)
        self.assertIn('/api/defense/tracks', rules)


if __name__ == '__main__':
    unittest.main()
