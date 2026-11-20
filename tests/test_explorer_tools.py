import copy
import csv
import io
from html.parser import HTMLParser
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app import app
from college_data import COLUMNS
from college_filters import filter_colleges, get_filter_options, validate_filters
from test_college_filters import test_colleges


class LinkReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            self.links.append(dict(attributes).get("href", ""))


class CollegeProfileTests(unittest.TestCase):
    def setUp(self):
        self.records = test_colleges()
        loader = patch("app.get_available_college_data", return_value=(self.records, {}, "Sample fallback", ""))
        loader.start()
        self.addCleanup(loader.stop)
        network = patch("college_data.requests.get")
        self.network = network.start()
        self.addCleanup(network.stop)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_valid_profile_shows_existing_details_without_changing_records(self):
        self.records[0]["student_size"] = 12345
        original = copy.deepcopy(self.records)
        response = self.client.get("/college/1")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for value in ("Alpha College", "Test City", "CA", "Public", "12,345", "$1,000", "$5,000", "50.0%", "$30,000"):
            self.assertIn(value, page)
        self.assertEqual(self.records, original)
        self.network.assert_not_called()

    def test_missing_profile_values_are_not_replaced_with_zero(self):
        page = self.client.get("/college/3").get_data(as_text=True)
        self.assertGreaterEqual(page.count("Not available"), 6)
        self.assertNotIn("$0", page)

    def test_real_zero_values_are_displayed(self):
        page = self.client.get("/college/4").get_data(as_text=True)
        self.assertIn("$0", page)
        self.assertIn("0.0%", page)
        self.assertNotIn("Not available", page)

    def test_unknown_profile_is_helpful_and_404(self):
        response = self.client.get("/college/999999")
        self.assertEqual(response.status_code, 404)
        page = response.get_data(as_text=True)
        self.assertIn("College not found", page)
        self.assertIn("currently loaded dataset", page)
        self.assertIn("Back to College Explorer", page)
        self.assertNotIn("Traceback", page)

    def test_non_integer_profile_id_is_404(self):
        self.assertEqual(self.client.get("/college/not-a-number").status_code, 404)

    def test_profile_escapes_name_and_location(self):
        self.records[0]["name"] = "<script>name</script>"
        self.records[0]["city"] = '<img src=x onerror="bad">'
        page = self.client.get("/college/1").get_data(as_text=True)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;img", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img", page)

    def test_explorer_links_profiles_and_preserves_safe_back_query(self):
        query = {"state": "CA", "sort": "size_desc", "limit": "10"}
        page = self.client.get("/explorer", query_string=query).get_data(as_text=True)
        reader = LinkReader()
        reader.feed(page)
        profile = next(link for link in reader.links if urlparse(link).path == "/college/1")
        self.assertEqual(parse_qs(urlparse(profile).query)["state"], ["CA"])
        detail = self.client.get(profile).get_data(as_text=True)
        reader = LinkReader()
        reader.feed(detail)
        back = next(link for link in reader.links if urlparse(link).path == "/explorer" and "state=" in link)
        self.assertEqual(parse_qs(urlparse(back).query)["sort"], ["size_desc"])
        self.assertEqual(parse_qs(urlparse(back).query)["limit"], ["10"])

    def test_back_link_cannot_be_changed_into_external_redirect(self):
        response = self.client.get("/college/1", query_string={"_external": "true", "_scheme": "https", "next": "https://example.invalid"})
        page = response.get_data(as_text=True)
        self.assertIn('href="/explorer">Back to College Explorer', page)
        self.assertNotIn("example.invalid", page)


class CityEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.records = test_colleges()
        self.states, self.types = get_filter_options(self.records)

    def apply_filters(self, query):
        selected, filters, messages = validate_filters(query, self.states, self.types)
        return filter_colleges(self.records, filters), selected, messages

    def ids(self, query):
        return [record["school_id"] for record in self.apply_filters(query)[0]]

    def test_city_search_is_partial_case_insensitive_and_trimmed(self):
        for value in ("cit", "CITY", "  city  "):
            with self.subTest(value=value):
                self.assertEqual(self.ids({"city": value}), [1, 4])
        self.assertEqual(self.ids({"city": "town"}), [2])

    def test_minimum_enrollment_is_inclusive(self):
        self.assertEqual(self.ids({"minimum_size": "100"}), [1, 2])
        self.assertEqual(self.ids({"minimum_size": "300"}), [1])

    def test_maximum_enrollment_is_inclusive(self):
        self.assertEqual(self.ids({"maximum_size": "100"}), [2, 4])
        self.assertEqual(self.ids({"maximum_size": "0"}), [4])

    def test_both_enrollment_bounds_work_with_other_filters(self):
        query = {"minimum_size": "100", "maximum_size": "300", "state": "CA", "city": "CITY", "minimum_graduation": "50"}
        self.assertEqual(self.ids(query), [1])
        self.assertEqual(self.ids({"minimum_size": "100", "maximum_size": "100"}), [2])

    def test_missing_enrollment_is_kept_unless_size_filter_is_active(self):
        self.assertEqual(self.ids({}), [1, 2, 3, 4])
        self.assertNotIn(3, self.ids({"minimum_size": "0"}))
        self.assertNotIn(3, self.ids({"maximum_size": "999999"}))

    def test_invalid_enrollment_values_are_reported_and_ignored(self):
        for field in ("minimum_size", "maximum_size"):
            for value in ("-1", "bad", "nan", "inf", "1e999"):
                with self.subTest(field=field, value=value):
                    matches, selected, messages = self.apply_filters({field: value})
                    self.assertEqual(matches, self.records)
                    self.assertEqual(selected[field], value)
                    self.assertIn("non-negative number", messages[0])

    def test_reversed_bounds_are_ignored_without_losing_other_filters(self):
        matches, selected, messages = self.apply_filters({"minimum_size": "300", "maximum_size": "100", "state": "CA"})
        self.assertEqual([record["school_id"] for record in matches], [1, 3])
        self.assertIn("Both enrollment filters were ignored", messages[0])
        self.assertEqual(selected["minimum_size"], "300")

    def test_fractional_bounds_do_not_round_saved_enrollment(self):
        self.assertEqual(self.ids({"minimum_size": "100.5", "maximum_size": "300"}), [1])

    def test_city_and_enrollment_values_remain_in_form_and_profile_back_link(self):
        with patch("app.get_available_college_data", return_value=(self.records, {}, "Sample fallback", "")):
            client = app.test_client()
            query = {"city": "Test", "minimum_size": "100", "maximum_size": "300"}
            page = client.get("/explorer", query_string=query).get_data(as_text=True)
            for value in ("Test", "100", "300"):
                self.assertIn(f'value="{value}"', page)
            reader = LinkReader()
            reader.feed(page)
            profile = next(link for link in reader.links if urlparse(link).path == "/college/1")
            detail = client.get(profile).get_data(as_text=True)
            reader = LinkReader()
            reader.feed(detail)
            back = next(link for link in reader.links if urlparse(link).path == "/explorer" and "city=" in link)
            self.assertEqual(parse_qs(urlparse(back).query)["city"], ["Test"])
            self.assertEqual(parse_qs(urlparse(back).query)["minimum_size"], ["100"])
            self.assertEqual(parse_qs(urlparse(back).query)["maximum_size"], ["300"])

    def test_no_city_match_uses_existing_empty_message(self):
        with patch("app.get_available_college_data", return_value=(self.records, {}, "Sample fallback", "")):
            page = app.test_client().get("/explorer?city=nonexistent").get_data(as_text=True)
        self.assertIn("No colleges match these filters", page)

    def test_invalid_bounds_show_route_validation(self):
        with patch("app.get_available_college_data", return_value=(self.records, {}, "Sample fallback", "")):
            response = app.test_client().get("/explorer?minimum_size=300&maximum_size=100")
        self.assertEqual(response.status_code, 200)
        self.assertIn("must not exceed", response.get_data(as_text=True))


class CollegeExportTests(unittest.TestCase):
    def setUp(self):
        self.records = test_colleges()
        loader = patch("app.get_available_college_data", return_value=(self.records, {}, "Sample fallback", ""))
        loader.start()
        self.addCleanup(loader.stop)
        network = patch("college_data.requests.get")
        self.network = network.start()
        self.addCleanup(network.stop)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def export_rows(self, query=None):
        response = self.client.get("/explorer/export", query_string=query or {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        reader = csv.DictReader(io.StringIO(response.get_data(as_text=True)))
        return response, reader.fieldnames, list(reader)

    def test_csv_headers_mime_and_fixed_filename(self):
        response, fields, rows = self.export_rows()
        self.assertEqual(fields, COLUMNS)
        self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="campusfit_colleges.csv"')
        self.assertEqual(len(rows), 4)
        self.network.assert_not_called()

    def test_city_filter_changes_exported_rows(self):
        response, fields, rows = self.export_rows({"city": "  TOWN "})
        self.assertEqual([row["school_id"] for row in rows], ["2"])

    def test_enrollment_filter_changes_exported_rows(self):
        response, fields, rows = self.export_rows({"minimum_size": "100", "maximum_size": "300"})
        self.assertEqual([row["school_id"] for row in rows], ["1", "2"])

    def test_existing_filters_and_new_filters_combine(self):
        query = {"name": "college", "city": "city", "state": "CA", "institution_type": "Public",
                 "maximum_tuition": "1000", "minimum_graduation": "50", "minimum_size": "300"}
        response, fields, rows = self.export_rows(query)
        self.assertEqual([row["school_id"] for row in rows], ["1"])

    def test_sorting_changes_exported_order_and_keeps_missing_last(self):
        response, fields, rows = self.export_rows({"sort": "tuition_desc"})
        self.assertEqual([row["school_id"] for row in rows], ["2", "1", "4", "3"])

    def test_display_limit_does_not_limit_export(self):
        self.records.extend(dict(self.records[0], school_id=number, name=f"Test College {number}") for number in range(5, 30))
        response, fields, rows = self.export_rows({"limit": "10"})
        self.assertEqual(len(rows), 29)
        page = self.client.get("/explorer?limit=10").get_data(as_text=True)
        self.assertIn("Displayed results: 10", page)

    def test_csv_uses_raw_numbers_and_blank_missing_values(self):
        response, fields, rows = self.export_rows()
        by_id = {row["school_id"]: row for row in rows}
        self.assertEqual(by_id["1"]["tuition_in_state"], "1000")
        self.assertEqual(by_id["1"]["graduation_rate"], "0.5")
        self.assertEqual(by_id["1"]["median_earnings"], "30000")
        for field in ("student_size", "tuition_in_state", "tuition_out_of_state", "graduation_rate", "median_earnings"):
            self.assertEqual(by_id["3"][field], "")
            self.assertEqual(by_id["4"][field], "0")
        self.assertNotIn("$", response.get_data(as_text=True))
        self.assertNotIn("Not available", response.get_data(as_text=True))

    def test_csv_quotes_commas_quotes_newlines_and_preserves_unicode(self):
        self.records[0]["name"] = 'Test "Université", College\nCampus'
        response, fields, rows = self.export_rows({"state": "CA", "institution_type": "Public"})
        self.assertEqual(rows[0]["name"], self.records[0]["name"])
        self.assertIn('"Test ""Université"", College\nCampus"', response.get_data(as_text=True))

    def test_malicious_query_cannot_control_download_path_or_headers(self):
        query = {"filename": "../../bad.csv\r\nX-Injected: yes", "path": "../../bad", "name": "\r\nX-Injected: yes"}
        response, fields, rows = self.export_rows(query)
        self.assertEqual(rows, [])
        self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="campusfit_colleges.csv"')
        self.assertNotIn("X-Injected", response.headers)

    def test_export_never_opens_or_writes_a_file_and_preserves_records(self):
        original = copy.deepcopy(self.records)
        with patch("builtins.open", side_effect=AssertionError("Export must stay in memory")):
            with patch("pathlib.Path.open", side_effect=AssertionError("Export must stay in memory")):
                self.export_rows()
        self.assertEqual(self.records, original)
        self.network.assert_not_called()

    def test_invalid_filters_use_the_same_safe_defaults_as_explorer(self):
        query = {"minimum_size": "300", "maximum_size": "100", "state": "ZZ", "sort": "bad", "limit": "bad", "maximum_tuition": "bad"}
        response, fields, rows = self.export_rows(query)
        self.assertEqual([row["school_id"] for row in rows], ["1", "2", "4", "3"])
        page = self.client.get("/explorer", query_string=query).get_data(as_text=True)
        self.assertIn("Matching records: 4", page)
        self.assertIn("Both enrollment filters were ignored", page)

    def test_export_button_submits_the_existing_filter_form(self):
        page = self.client.get("/explorer?city=Test&minimum_size=100&sort=size_desc").get_data(as_text=True)
        self.assertIn('form="explorer-filters" formaction="/explorer/export"', page)
        self.assertIn("Export Matching Results", page)
        self.assertIn('value="Test"', page)
        self.assertIn('value="size_desc" selected', page)

    def test_empty_matches_or_dataset_export_only_header(self):
        response, fields, rows = self.export_rows({"city": "nonexistent"})
        self.assertEqual(rows, [])
        self.records.clear()
        response, fields, rows = self.export_rows()
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
