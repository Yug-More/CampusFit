import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

import college_data as data
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


class ExplorerDataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        records = data.load_college_records(data.DATA_DIRECTORY / "sample_colleges.csv")
        metadata = data.load_metadata(data.DATA_DIRECTORY / "sample_metadata.json")
        data.save_college_records(records, self.path / "sample_colleges.csv")
        data.save_metadata(metadata, self.path / "sample_metadata.json")
        directory_patch = patch("college_data.DATA_DIRECTORY", self.path)
        directory_patch.start()
        self.addCleanup(directory_patch.stop)
        key_patch = patch.dict("os.environ", {}, clear=True)
        key_patch.start()
        self.addCleanup(key_patch.stop)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_sample_data_and_missing_values_display(self):
        page = self.client.get("/explorer").get_data(as_text=True)
        self.assertIn("Sample fallback", page)
        self.assertIn("Loaded records: 40", page)
        self.assertIn("Alabama", page)
        self.assertIn("Not available", page)
        self.assertIn('method="post"', page)
        self.assertIn("Refresh Data", page)

    def test_refresh_without_key(self):
        with patch("college_data.requests.get") as get:
            response = self.client.post("/explorer")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Set COLLEGE_SCORECARD_API_KEY", response.get_data(as_text=True))
        get.assert_not_called()
        self.assertFalse((self.path / "colleges.csv").exists())

    def test_successful_mocked_refresh_redirects_and_displays_runtime(self):
        payload = json.loads((Path(__file__).parent / "fixtures" / "scorecard_sample.json").read_text())
        response = Mock(status_code=200)
        response.json.return_value = payload
        with patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"}):
            with patch("college_data.requests.get", return_value=response):
                result = self.client.post("/explorer")
        self.assertEqual(result.status_code, 302)
        page = self.client.get(result.headers["Location"]).get_data(as_text=True)
        self.assertIn("Refresh successful", page)
        self.assertIn("Runtime cache", page)
        self.assertIn("Test Public College", page)
        self.assertIn("Not available", page)

    def test_failed_refresh_keeps_sample_visible(self):
        with patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"}):
            with patch("college_data.requests.get", side_effect=requests.Timeout("private details")):
                page = self.client.post("/explorer").get_data(as_text=True)
        self.assertIn("timed out", page)
        self.assertIn("Sample fallback", page)
        self.assertNotIn("private details", page)

    def test_html_is_escaped_and_zero_is_displayed(self):
        records = data.load_college_records(self.path / "sample_colleges.csv")[:1]
        records[0]["name"] = "<script>test</script>"
        records[0]["tuition_in_state"] = 0
        with patch("app.get_available_college_data", return_value=(records, {}, "Sample fallback", "")):
            page = self.client.get("/explorer").get_data(as_text=True)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn("$0", page)


if __name__ == "__main__":
    unittest.main()
