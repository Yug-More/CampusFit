import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

import college_data as data


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "scorecard_sample.json"


def fixture_payload():
    with FIXTURE_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def api_response(payload):
    response = Mock(status_code=200)
    response.json.return_value = payload
    return response


@patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"})
class RetrievalTests(unittest.TestCase):
    @patch("college_data.requests.get")
    def test_successful_response_and_verified_parameters(self, get):
        payload = fixture_payload()
        get.return_value = api_response(payload)
        self.assertEqual(data.fetch_college_records(), payload["results"])
        args, kwargs = get.call_args
        self.assertEqual(args, (data.ENDPOINT,))
        self.assertEqual(kwargs["params"], {
            "fields": ",".join(data.REQUESTED_FIELDS), "school.operating": 1,
            "sort": "latest.student.size:desc", "page": 0, "per_page": 100,
        })
        self.assertEqual(kwargs["headers"], {"X-Api-Key": "test-only-placeholder"})
        self.assertEqual(kwargs["timeout"], 20)
        get.return_value.raise_for_status.assert_called_once()

    @patch("college_data.requests.get")
    def test_pagination_stops_at_total(self, get):
        records = fixture_payload()["results"][:1] * 100
        get.return_value = api_response({"results": records, "metadata": {"total": 100}})
        self.assertEqual(len(data.fetch_college_records()), 100)
        self.assertEqual(get.call_count, 1)

    @patch("college_data.requests.get")
    def test_pagination_stops_on_empty_page(self, get):
        get.side_effect = [api_response({"results": [{}] * 100}), api_response({"results": []})]
        self.assertEqual(len(data.fetch_college_records()), 100)
        self.assertEqual(get.call_args.kwargs["params"]["page"], 1)

    @patch("college_data.requests.get")
    def test_pagination_has_maximum(self, get):
        get.return_value = api_response({"results": [{}] * 100})
        self.assertEqual(len(data.fetch_college_records()), 300)
        self.assertEqual(get.call_count, 3)

    @patch("college_data.requests.get")
    def test_network_failures_do_not_expose_exception_details(self, get):
        for error in (requests.Timeout, requests.ConnectionError, requests.HTTPError):
            with self.subTest(error=error):
                get.side_effect = error("private-request-details")
                with self.assertRaises(ValueError) as caught:
                    data.fetch_college_records()
                self.assertNotIn("private-request-details", str(caught.exception))

    @patch("college_data.requests.get")
    def test_http_failure(self, get):
        get.return_value = api_response({})
        get.return_value.raise_for_status.side_effect = requests.HTTPError()
        with self.assertRaisesRegex(ValueError, "request failed"):
            data.fetch_college_records()

    @patch("college_data.requests.get")
    def test_rate_limit(self, get):
        get.return_value = Mock(status_code=429)
        with self.assertRaisesRegex(ValueError, "rate limit"):
            data.fetch_college_records()

    @patch("college_data.requests.get")
    def test_invalid_json(self, get):
        get.return_value = api_response({})
        get.return_value.json.side_effect = ValueError("invalid")
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            data.fetch_college_records()

    @patch("college_data.requests.get")
    def test_invalid_results_structure(self, get):
        for payload in (None, {}, {"results": {}}, {"results": [None]}):
            with self.subTest(payload=payload):
                get.return_value = api_response(payload)
                with self.assertRaises(ValueError):
                    data.fetch_college_records()

    @patch("college_data.requests.get")
    def test_empty_results(self, get):
        get.return_value = api_response({"results": []})
        with self.assertRaisesRegex(ValueError, "no colleges"):
            data.fetch_college_records()

    @patch("college_data.requests.get")
    def test_missing_key_never_requests_data(self, get):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "COLLEGE_SCORECARD_API_KEY"):
                data.fetch_college_records()
        get.assert_not_called()


class NormalizationTests(unittest.TestCase):
    def test_normal_record(self):
        record = data.normalize_college_record(fixture_payload()["results"][0])
        self.assertEqual(set(record), set(data.COLUMNS))
        self.assertEqual(record["name"], "Test Public College")
        self.assertEqual(record["tuition_in_state"], 5000)
        self.assertEqual(record["graduation_rate"], 0.65)

    def test_ownership_codes(self):
        for code, label in [(1, "Public"), (2, "Private nonprofit"), (3, "Private for-profit"), (9, "")]:
            record = {"id": 1, "school.name": "Test", "school.ownership": code}
            self.assertEqual(data.normalize_college_record(record)["institution_type"], label)

    def test_missing_values_and_less_than_four_year_rate(self):
        record = data.normalize_college_record(fixture_payload()["results"][1])
        self.assertIsNone(record["tuition_in_state"])
        self.assertIsNone(record["median_earnings"])
        self.assertEqual(record["city"], "")
        self.assertEqual(record["graduation_rate"], 0.4)

    def test_invalid_numbers_and_real_zero(self):
        for value in (None, "", "NULL", "PrivacySuppressed", -1, "nan", "inf", {}, True):
            self.assertIsNone(data.clean_number(value))
        self.assertEqual(data.clean_number(0), 0)
        self.assertIsNone(data.clean_number(1.1, maximum=1))
        self.assertIsNone(data.clean_number(1.5, whole_number=True))

    def test_incomplete_records_are_skipped_and_duplicates_removed(self):
        records = fixture_payload()["results"]
        normalized = data.normalize_college_records([None, {}, {"id": 5}, *records, records[0]])
        self.assertEqual(len(normalized), 2)
        with self.assertRaises(ValueError):
            data.normalize_college_records([None, {}])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.records = data.normalize_college_records(fixture_payload()["results"])
        self.metadata = data.create_metadata(len(self.records))

    def write_sample(self):
        data.save_college_records(self.records, self.directory / "sample_colleges.csv")
        data.save_metadata(self.metadata, self.directory / "sample_metadata.json")

    def test_csv_round_trip_and_exact_header(self):
        path = self.directory / "colleges.csv"
        data.save_college_records(self.records, path)
        self.assertEqual(path.read_text().splitlines()[0], ",".join(data.COLUMNS))
        self.assertEqual(data.load_college_records(path), self.records)
        self.assertIsNone(data.load_college_records(path)[1]["median_earnings"])

    def test_utf8_and_real_zero_survive_csv(self):
        self.records[0]["name"] = "Test Université"
        self.records[0]["tuition_in_state"] = 0
        path = self.directory / "colleges.csv"
        data.save_college_records(self.records, path)
        self.assertEqual(data.load_college_records(path), self.records)

    def test_invalid_save_preserves_old_csv(self):
        path = self.directory / "colleges.csv"
        data.save_college_records(self.records, path)
        original = path.read_bytes()
        for records in ([], [{}], self.records * 2):
            with self.subTest(records=records):
                with self.assertRaises(ValueError):
                    data.save_college_records(records, path)
                self.assertEqual(path.read_bytes(), original)

    def test_invalid_csv_is_rejected(self):
        path = self.directory / "colleges.csv"
        path.write_text("bad,columns\n1,2\n")
        with self.assertRaises(ValueError):
            data.load_college_records(path)
        data.save_college_records(self.records, path)
        path.write_text(path.read_text().replace("5000", "nan"))
        with self.assertRaises(ValueError):
            data.load_college_records(path)

    def test_metadata_round_trip(self):
        path = self.directory / "metadata.json"
        data.save_metadata(self.metadata, path)
        self.assertEqual(data.load_metadata(path), self.metadata)
        self.assertEqual(set(self.metadata), {"source", "endpoint", "retrieved_at", "record_count", "requested_fields", "scope_or_limit"})

    def test_invalid_metadata(self):
        path = self.directory / "metadata.json"
        for content in ("not json", "[]", "{}"):
            path.write_text(content)
            with self.assertRaises(ValueError):
                data.load_metadata(path)

    def test_runtime_cache_preference(self):
        self.write_sample()
        runtime_records = self.records[:1]
        data.publish_runtime_cache(runtime_records, data.create_metadata(1), self.directory)
        records, metadata, label, message = data.get_available_college_data(self.directory)
        self.assertEqual(records, runtime_records)
        self.assertEqual(label, "Runtime cache")
        self.assertEqual(metadata["record_count"], 1)

    def test_sample_fallback(self):
        self.write_sample()
        records, metadata, label, message = data.get_available_college_data(self.directory)
        self.assertEqual(records, self.records)
        self.assertEqual(label, "Sample fallback")

    def test_corrupt_runtime_falls_back(self):
        self.write_sample()
        (self.directory / "colleges.csv").write_text("broken")
        self.assertEqual(data.get_available_college_data(self.directory)[2], "Sample fallback")

    def test_missing_metadata_keeps_usable_records(self):
        self.write_sample()
        (self.directory / "sample_metadata.json").unlink()
        records, metadata, label, message = data.get_available_college_data(self.directory)
        self.assertEqual(records, self.records)
        self.assertEqual(metadata, {})
        self.assertIn("unavailable", message)

    def test_no_usable_files(self):
        self.assertEqual(data.get_available_college_data(self.directory)[0], [])

    @patch("college_data.requests.get")
    @patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"})
    def test_successful_refresh(self, get):
        get.return_value = api_response(fixture_payload())
        successful, message = data.refresh_college_data(self.directory)
        self.assertTrue(successful)
        self.assertIn("2 college records", message)
        self.assertEqual(data.load_college_records(self.directory / "colleges.csv"), self.records)
        self.assertEqual(data.load_metadata(self.directory / "metadata.json")["record_count"], 2)

    @patch("college_data.requests.get")
    @patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"})
    def test_failed_refresh_preserves_cache(self, get):
        data.publish_runtime_cache(self.records, self.metadata, self.directory)
        original = {name: (self.directory / name).read_bytes() for name in ("colleges.csv", "metadata.json")}
        for failure in (requests.Timeout(), requests.ConnectionError()):
            get.side_effect = failure
            self.assertFalse(data.refresh_college_data(self.directory)[0])
            for name, content in original.items():
                self.assertEqual((self.directory / name).read_bytes(), content)

    @patch("college_data.requests.get")
    @patch.dict(os.environ, {"COLLEGE_SCORECARD_API_KEY": "test-only-placeholder"})
    def test_invalid_and_empty_download_preserve_cache(self, get):
        data.publish_runtime_cache(self.records, self.metadata, self.directory)
        original = (self.directory / "colleges.csv").read_bytes()
        for payload in ({"results": []}, {"results": [{}]}):
            get.return_value = api_response(payload)
            self.assertFalse(data.refresh_college_data(self.directory)[0])
            self.assertEqual((self.directory / "colleges.csv").read_bytes(), original)

    def test_publish_failure_rolls_back_both_files(self):
        data.publish_runtime_cache(self.records, self.metadata, self.directory)
        original = {name: (self.directory / name).read_bytes() for name in ("colleges.csv", "metadata.json")}
        original_replace = os.replace

        def fail_metadata_publish(source, destination):
            if Path(destination) == self.directory / "metadata.json":
                raise OSError("test disk failure")
            return original_replace(source, destination)

        with patch("college_data.os.replace", side_effect=fail_metadata_publish):
            with self.assertRaises(OSError):
                data.publish_runtime_cache(self.records[:1], data.create_metadata(1), self.directory)
        for name, content in original.items():
            self.assertEqual((self.directory / name).read_bytes(), content)

    @patch("college_data.publish_runtime_cache", side_effect=OSError("private path"))
    @patch("college_data.fetch_college_records")
    def test_disk_error_has_safe_message(self, fetch, publish):
        fetch.return_value = fixture_payload()["results"]
        successful, message = data.refresh_college_data(self.directory)
        self.assertFalse(successful)
        self.assertNotIn("private path", message)
