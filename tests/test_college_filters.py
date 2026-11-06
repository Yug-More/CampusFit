import copy
import unittest

from college_filters import (
    SORT_OPTIONS, filter_colleges, get_filter_options, limit_colleges,
    sort_colleges, validate_filters,
)


def test_colleges():
    """Synthetic institutions for deterministic filter tests only."""
    return [
        {"school_id": 1, "name": "Alpha College", "city": "Test City", "state": "CA",
         "institution_type": "Public", "student_size": 300,
         "tuition_in_state": 1000, "tuition_out_of_state": 5000,
         "graduation_rate": 0.5, "median_earnings": 30000},
        {"school_id": 2, "name": "beta University", "city": "Test Town", "state": "NY",
         "institution_type": "Private nonprofit", "student_size": 100,
         "tuition_in_state": 2000, "tuition_out_of_state": 2000,
         "graduation_rate": 0.8, "median_earnings": 10000},
        {"school_id": 3, "name": "Gamma College", "city": "", "state": "CA",
         "institution_type": "Private for-profit", "student_size": None,
         "tuition_in_state": None, "tuition_out_of_state": None,
         "graduation_rate": None, "median_earnings": None},
        {"school_id": 4, "name": "Delta College", "city": "Test City", "state": "TX",
         "institution_type": "Public", "student_size": 0,
         "tuition_in_state": 0, "tuition_out_of_state": 0,
         "graduation_rate": 0, "median_earnings": 0},
    ]


class CollegeFilterTests(unittest.TestCase):
    def setUp(self):
        self.records = test_colleges()
        self.states, self.types = get_filter_options(self.records)

    def apply_filters(self, query):
        selected, filters, messages = validate_filters(query, self.states, self.types)
        return filter_colleges(self.records, filters)

    def ids(self, records):
        return [record["school_id"] for record in records]

    def test_empty_filters_return_every_record(self):
        self.assertEqual(self.apply_filters({}), self.records)

    def test_case_insensitive_partial_name(self):
        self.assertEqual(self.ids(self.apply_filters({"name": "PHA"})), [1])

    def test_name_whitespace_is_trimmed(self):
        self.assertEqual(self.ids(self.apply_filters({"name": "  alpha  "})), [1])

    def test_state_filter(self):
        self.assertEqual(self.ids(self.apply_filters({"state": "CA"})), [1, 3])

    def test_institution_type_filter(self):
        self.assertEqual(self.ids(self.apply_filters({"institution_type": "Public"})), [1, 4])

    def test_maximum_tuition_is_inclusive_and_in_state_only(self):
        self.assertEqual(self.ids(self.apply_filters({"maximum_tuition": "1000"})), [1, 4])
        self.assertEqual(self.ids(self.apply_filters({"maximum_tuition": "0"})), [4])

    def test_missing_tuition_excluded_only_with_active_filter(self):
        self.assertIn(3, self.ids(self.apply_filters({})))
        self.assertNotIn(3, self.ids(self.apply_filters({"maximum_tuition": "100000"})))

    def test_graduation_percentage_conversion_and_inclusive_boundary(self):
        selected, filters, messages = validate_filters({"minimum_graduation": "50"}, self.states, self.types)
        self.assertEqual(filters["minimum_graduation"], 0.5)
        self.assertEqual(self.ids(filter_colleges(self.records, filters)), [1, 2])

    def test_missing_graduation_excluded_at_zero_percent(self):
        self.assertEqual(self.ids(self.apply_filters({"minimum_graduation": "0"})), [1, 2, 4])
        self.assertEqual(self.apply_filters({"minimum_graduation": "100"}), [])

    def test_combined_filters(self):
        query = {"name": "college", "state": "CA", "institution_type": "Public",
                 "maximum_tuition": "1000", "minimum_graduation": "50"}
        self.assertEqual(self.ids(self.apply_filters(query)), [1])

    def test_all_sort_options_and_missing_values_last(self):
        expected = {
            "name": [1, 2, 4, 3], "tuition_asc": [4, 1, 2, 3],
            "tuition_desc": [2, 1, 4, 3], "graduation_desc": [2, 1, 4, 3],
            "earnings_desc": [1, 2, 4, 3], "size_desc": [1, 2, 4, 3],
        }
        for option in SORT_OPTIONS:
            with self.subTest(option=option):
                self.assertEqual(self.ids(sort_colleges(self.records, option)), expected[option])

    def test_numeric_sort_handles_entirely_missing_column(self):
        for record in self.records:
            record["tuition_in_state"] = None
        self.assertEqual(self.ids(sort_colleges(self.records, "tuition_desc")), [1, 2, 4, 3])

    def test_each_result_limit(self):
        records = [{"school_id": number} for number in range(60)]
        for limit, expected in [("10", 10), ("20", 20), ("50", 50), ("all", 60)]:
            with self.subTest(limit=limit):
                limited = limit_colleges(records, limit)
                self.assertEqual(len(limited), expected)
                self.assertEqual(limited, records[:expected])

    def test_invalid_tuition_is_reported_and_ignored(self):
        for value in ("-1", "abc", "nan", "inf", "1e999"):
            with self.subTest(value=value):
                selected, filters, messages = validate_filters({"maximum_tuition": value}, self.states, self.types)
                self.assertEqual(selected["maximum_tuition"], value)
                self.assertIsNone(filters["maximum_tuition"])
                self.assertIn("Maximum in-state tuition", messages[0])
                self.assertEqual(filter_colleges(self.records, filters), self.records)

    def test_invalid_graduation_is_reported_and_ignored(self):
        for value in ("-1", "101", "abc", "nan", "inf"):
            with self.subTest(value=value):
                selected, filters, messages = validate_filters({"minimum_graduation": value}, self.states, self.types)
                self.assertEqual(selected["minimum_graduation"], value)
                self.assertIsNone(filters["minimum_graduation"])
                self.assertIn("0 to 100", messages[0])

    def test_unknown_selections_have_safe_defaults_and_messages(self):
        query = {"state": "ZZ", "institution_type": "Unknown", "sort": "random", "limit": "999"}
        selected, filters, messages = validate_filters(query, self.states, self.types)
        for field, value in query.items():
            self.assertEqual(selected[field], value)
        self.assertEqual(filters["state"], "")
        self.assertEqual(filters["institution_type"], "")
        self.assertEqual(filters["sort"], "name")
        self.assertEqual(filters["limit"], "20")
        self.assertEqual(len(messages), 4)

    def test_options_come_from_entire_dataset_sorted_without_blanks(self):
        self.records.append(dict(self.records[0], state="", institution_type=""))
        states, types = get_filter_options(self.records)
        self.assertEqual(states, ["CA", "NY", "TX"])
        self.assertEqual(types, ["Private for-profit", "Private nonprofit", "Public"])

    def test_empty_matches(self):
        self.assertEqual(self.apply_filters({"name": "does not exist"}), [])

    def test_empty_dataset(self):
        self.assertEqual(get_filter_options([]), ([], []))
        self.assertEqual(filter_colleges([], {}), [])
        self.assertEqual(sort_colleges([], "name"), [])
        self.assertEqual(limit_colleges([], "all"), [])

    def test_pipeline_does_not_change_source_records(self):
        original = copy.deepcopy(self.records)
        matches = self.apply_filters({"state": "CA"})
        limit_colleges(sort_colleges(matches, "tuition_asc"), "10")
        self.assertEqual(self.records, original)


if __name__ == "__main__":
    unittest.main()
