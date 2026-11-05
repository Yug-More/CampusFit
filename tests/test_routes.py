import unittest

from app import app


class RouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_home_redirects_to_explorer(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/explorer")
        self.assertEqual(self.client.get("/", follow_redirects=True).status_code, 200)

    def test_explorer_returns_successfully(self):
        self.assertEqual(self.client.get("/explorer").status_code, 200)

    def test_explorer_contains_page_title(self):
        response = self.client.get("/explorer")
        self.assertIn("CampusFit College Explorer", response.get_data(as_text=True))

    def test_simulator_returns_successfully(self):
        self.assertEqual(self.client.get("/simulator").status_code, 200)

    def test_simulator_is_temporary_placeholder(self):
        response = self.client.get("/simulator")
        page = response.get_data(as_text=True)
        self.assertIn("Temporary placeholder", page)
        self.assertIn("Decision Simulator is under development", page)


if __name__ == "__main__":
    unittest.main()
