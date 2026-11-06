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
        self.assertIn("Amridge University", page)
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

    def test_failed_refresh_keeps_runtime_cache_and_metadata_visible(self):
        records = data.load_college_records(self.path / "sample_colleges.csv")[:1]
        metadata = data.create_metadata(1)
        data.publish_runtime_cache(records, metadata, self.path)
        original = {name: (self.path / name).read_bytes() for name in ("colleges.csv", "metadata.json")}
        with patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"}):
            with patch("college_data.requests.get", side_effect=requests.ConnectionError("private details")):
                response = self.client.post("/explorer")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Runtime cache", page)
        self.assertIn(records[0]["name"], page)
        self.assertIn(metadata["retrieved_at"], page)
        self.assertNotIn("private details", page)
        for name, content in original.items():
            self.assertEqual((self.path / name).read_bytes(), content)

    def test_metadata_display_and_unavailable_timestamp(self):
        metadata = data.load_metadata(self.path / "sample_metadata.json")
        page = self.client.get("/explorer").get_data(as_text=True)
        self.assertIn("Retrieved (UTC): " + metadata["retrieved_at"], page)
        (self.path / "sample_metadata.json").unlink()
        page = self.client.get("/explorer").get_data(as_text=True)
        self.assertIn("Retrieved (UTC): Not available", page)
        self.assertIn("Retrieval details are unavailable", page)
        self.assertIn("Loaded records: 40", page)

    def test_explorer_handles_no_usable_local_dataset(self):
        (self.path / "sample_colleges.csv").unlink()
        response = self.client.get("/explorer")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("No college records are available", page)
        self.assertIn("Loaded records: 0", page)
        self.assertIn("Unavailable", page)

    def test_html_is_escaped_and_zero_is_displayed(self):
        records = data.load_college_records(self.path / "sample_colleges.csv")[:1]
        records[0]["name"] = "<script>test</script>"
        records[0]["tuition_in_state"] = 0
        with patch("app.get_available_college_data", return_value=(records, {}, "Sample fallback", "")):
            page = self.client.get("/explorer").get_data(as_text=True)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn("$0", page)


class ExplorerFilterRouteTests(unittest.TestCase):
    def setUp(self):
        from test_college_filters import test_colleges
        self.records = test_colleges()
        loader_patch = patch("app.get_available_college_data", return_value=(
            self.records, {"retrieved_at": "2026-11-05T12:00:00+00:00"}, "Sample fallback", "",
        ))
        loader_patch.start()
        self.addCleanup(loader_patch.stop)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_query_selections_remain_displayed(self):
        query = {"name": "Alpha", "state": "CA", "institution_type": "Public",
                 "maximum_tuition": "1000", "minimum_graduation": "50",
                 "sort": "tuition_asc", "limit": "10"}
        page = self.client.get("/explorer", query_string=query).get_data(as_text=True)
        for value in ("Alpha", "1000", "50"):
            self.assertIn(f'value="{value}"', page)
        for value in ("CA", "Public", "tuition_asc", "10"):
            self.assertIn(f'value="{value}" selected', page)
        self.assertIn("Matching records: 1", page)
        self.assertIn("Displayed results: 1", page)
        self.assertNotIn("beta University</th>", page)

    def test_reset_url_has_no_query_parameters(self):
        page = self.client.get("/explorer?state=CA").get_data(as_text=True)
        self.assertIn('href="/explorer">Reset Filters</a>', page)
        reset_page = self.client.get("/explorer").get_data(as_text=True)
        self.assertIn("Matching records: 4", reset_page)
        self.assertIn('<form method="get" action="/explorer">', reset_page)
        self.assertIn('<form method="post" action="/explorer">', reset_page)

    def test_dollar_percentage_and_enrollment_formatting(self):
        self.records[0]["student_size"] = 12345
        self.records[0]["tuition_out_of_state"] = 45678
        page = self.client.get("/explorer").get_data(as_text=True)
        for value in ("$1,000", "$45,678", "$30,000", "50.0%", "12,345", "$0", "Not available"):
            self.assertIn(value, page)

    def test_invalid_values_are_shown_without_crashing(self):
        query = {"maximum_tuition": "-5", "minimum_graduation": "101", "state": "ZZ",
                 "institution_type": "Unknown", "sort": "random", "limit": "999"}
        response = self.client.get("/explorer", query_string=query)
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for message in ("non-negative number", "0 to 100", "selected state", "selected institution type", "Unknown sort", "Unknown results limit"):
            self.assertIn(message, page)
        self.assertIn('value="-5"', page)
        self.assertIn("Matching records: 4", page)

    def test_no_matches_message(self):
        page = self.client.get("/explorer?name=nonexistent").get_data(as_text=True)
        self.assertIn("No colleges match these filters", page)
        self.assertIn("Matching records: 0", page)

    def test_unknown_query_values_are_escaped(self):
        page = self.client.get("/explorer", query_string={"state": "<script>"}).get_data(as_text=True)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)

    def test_route_sorts_then_limits_and_counts_all_matches(self):
        self.records.extend(dict(self.records[0], school_id=number, name=f"Extra {number}") for number in range(5, 20))
        page = self.client.get("/explorer?sort=tuition_desc&limit=10").get_data(as_text=True)
        self.assertIn("Loaded records: 19", page)
        self.assertIn("Matching records: 19", page)
        self.assertIn("Displayed results: 10", page)
        self.assertLess(page.index("beta University</th>"), page.index("Alpha College</th>"))


if __name__ == "__main__":
    unittest.main()
