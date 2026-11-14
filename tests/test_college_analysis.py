import copy
import unittest

import pandas as pd

from college_analysis import (
    affordability_scores, build_college_table, earnings_scores, filter_by_institution_type,
    filter_by_state, graduation_scores, limit_results, normalize_weights, rank_colleges,
    simulate_rankings, to_number,
)


EQUAL_WEIGHTS = {"affordability": 1, "graduation": 1, "earnings": 1}


def synthetic_colleges():
    """Synthetic institutions for deterministic analysis tests only."""
    return [
        {"school_id": 1, "name": "Alpha College", "city": "Test City", "state": "CA",
         "institution_type": "Public", "student_size": 300,
         "tuition_in_state": 10000, "tuition_out_of_state": 20000,
         "graduation_rate": 0.5, "median_earnings": 40000},
        {"school_id": 2, "name": "Beta University", "city": "Test Town", "state": "NY",
         "institution_type": "Private nonprofit", "student_size": 100,
         "tuition_in_state": 20000, "tuition_out_of_state": 20000,
         "graduation_rate": 0.9, "median_earnings": 70000},
        {"school_id": 3, "name": "Gamma College", "city": "Test City", "state": "CA",
         "institution_type": "Private for-profit", "student_size": 200,
         "tuition_in_state": 30000, "tuition_out_of_state": 30000,
         "graduation_rate": 0.7, "median_earnings": 55000},
        {"school_id": 4, "name": "Delta College", "city": "", "state": "TX",
         "institution_type": "Public", "student_size": None,
         "tuition_in_state": 15000, "tuition_out_of_state": 25000,
         "graduation_rate": None, "median_earnings": 50000},
    ]


def ids(rows):
    return [row["school_id"] for row in rows]


class NumberAndWeightTests(unittest.TestCase):
    def test_to_number_keeps_missing_and_invalid_values_missing(self):
        for value in (None, "", "abc", "nan", "inf", True, [1]):
            self.assertIsNone(to_number(value), value)
        self.assertEqual(to_number("12.5"), 12.5)
        self.assertEqual(to_number(0), 0.0)

    def test_weights_are_normalized_to_shares(self):
        shares = normalize_weights({"affordability": 2, "graduation": "1", "earnings": 1.0})
        self.assertEqual(shares, {"affordability": 0.5, "graduation": 0.25, "earnings": 0.25})

    def test_all_zero_weights_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            normalize_weights({"affordability": 0, "graduation": 0, "earnings": 0})

    def test_negative_weight_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Graduation rate weight"):
            normalize_weights({"affordability": 1, "graduation": -1, "earnings": 1})

    def test_missing_or_invalid_weights_are_rejected(self):
        for bad_value in (None, "", "abc", "nan", "inf"):
            with self.assertRaises(ValueError):
                normalize_weights({"affordability": bad_value, "graduation": 1, "earnings": 1})


class CategoryScoreTests(unittest.TestCase):
    def assert_scores(self, scores, expected):
        self.assertEqual(len(scores), len(expected))
        for score, value in zip(scores, expected):
            self.assertAlmostEqual(score, value)

    def test_lower_tuition_receives_higher_affordability_score(self):
        scores = affordability_scores(pd.Series([10000.0, 20000.0, 30000.0]))
        self.assert_scores(scores, [100.0, 50.0, 0.0])

    def test_higher_graduation_rate_receives_higher_score(self):
        scores = graduation_scores(pd.Series([0.5, 0.9, 0.7]))
        self.assert_scores(scores, [0.0, 100.0, 50.0])

    def test_higher_earnings_receive_higher_score(self):
        scores = earnings_scores(pd.Series([40000.0, 70000.0, 55000.0]))
        self.assert_scores(scores, [0.0, 100.0, 50.0])

    def test_identical_values_receive_neutral_score_and_missing_stays_missing(self):
        scores = graduation_scores(pd.Series([0.6, None, 0.6], dtype="float64"))
        self.assertEqual(scores.iloc[0], 50.0)
        self.assertTrue(pd.isna(scores.iloc[1]))
        self.assertEqual(scores.iloc[2], 50.0)

    def test_empty_values_produce_no_scores(self):
        self.assertTrue(earnings_scores(pd.Series([], dtype="float64")).empty)


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.records = synthetic_colleges()

    def test_final_scores_follow_weighted_formula(self):
        result = simulate_rankings(
            self.records, {"affordability": 2, "graduation": 1, "earnings": 1},
        )
        scores = {row["school_id"]: row["score"] for row in result["colleges"]}
        self.assertAlmostEqual(scores[2], 75.0)
        self.assertAlmostEqual(scores[1], 50.0)
        self.assertAlmostEqual(scores[3], 25.0)

    def test_rankings_are_ordered_from_highest_to_lowest(self):
        result = simulate_rankings(self.records, {"affordability": 2, "graduation": 1, "earnings": 1})
        self.assertEqual(ids(result["colleges"]), [2, 1, 3])
        self.assertEqual([row["rank"] for row in result["colleges"]], [1, 2, 3])
        scores = [row["score"] for row in result["colleges"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_changing_weights_changes_the_ranking(self):
        affordable_first = simulate_rankings(
            self.records, {"affordability": 1, "graduation": 0, "earnings": 0},
        )
        earnings_first = simulate_rankings(
            self.records, {"affordability": 0, "graduation": 0, "earnings": 1},
        )
        self.assertEqual(affordable_first["colleges"][0]["school_id"], 1)
        self.assertEqual(earnings_first["colleges"][0]["school_id"], 2)

    def test_ties_are_broken_by_name(self):
        twin = dict(self.records[0], school_id=5, name="Aardvark College")
        result = simulate_rankings([self.records[0], twin], EQUAL_WEIGHTS)
        self.assertEqual(ids(result["colleges"]), [5, 1])

    def test_missing_positively_weighted_value_excludes_college(self):
        result = simulate_rankings(self.records, EQUAL_WEIGHTS)
        self.assertEqual(result["considered_count"], 4)
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(result["ranked_count"], 3)
        self.assertNotIn(4, ids(result["colleges"]))

    def test_missing_zero_weight_value_does_not_exclude_college(self):
        result = simulate_rankings(
            self.records, {"affordability": 1, "graduation": 0, "earnings": 1},
        )
        self.assertEqual(result["excluded_count"], 0)
        delta = [row for row in result["colleges"] if row["school_id"] == 4][0]
        self.assertIsNone(delta["graduation_rate"])

    def test_zero_tuition_is_a_real_value_not_missing_data(self):
        free_college = dict(self.records[0], school_id=6, name="Free College", tuition_in_state=0)
        result = simulate_rankings(
            [free_college, self.records[1]], {"affordability": 1, "graduation": 0, "earnings": 0},
        )
        self.assertEqual(result["excluded_count"], 0)
        self.assertEqual(result["colleges"][0]["school_id"], 6)
        self.assertAlmostEqual(result["colleges"][0]["score"], 100.0)

    def test_state_filter(self):
        table = build_college_table(self.records)
        self.assertEqual(filter_by_state(table, "CA")["school_id"].tolist(), [1, 3])
        self.assertEqual(len(filter_by_state(table, "")), 4)
        result = simulate_rankings(self.records, EQUAL_WEIGHTS, state="CA")
        self.assertEqual(result["considered_count"], 2)
        self.assertEqual(sorted(ids(result["colleges"])), [1, 3])

    def test_institution_type_filter(self):
        table = build_college_table(self.records)
        public = filter_by_institution_type(table, "Public")
        self.assertEqual(public["school_id"].tolist(), [1, 4])
        result = simulate_rankings(self.records, EQUAL_WEIGHTS, institution_type="Public")
        self.assertEqual(result["considered_count"], 2)
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(ids(result["colleges"]), [1])

    def test_result_limit(self):
        result = simulate_rankings(self.records, EQUAL_WEIGHTS, limit=2)
        self.assertEqual(len(result["colleges"]), 2)
        self.assertEqual(result["ranked_count"], 3)
        ranked = rank_colleges(build_college_table(self.records).assign(final_score=1.0))
        self.assertEqual(len(limit_results(ranked, None)), 4)

    def test_empty_input(self):
        result = simulate_rankings([], EQUAL_WEIGHTS)
        self.assertEqual(result["considered_count"], 0)
        self.assertEqual(result["excluded_count"], 0)
        self.assertEqual(result["colleges"], [])

    def test_no_matching_colleges(self):
        result = simulate_rankings(self.records, EQUAL_WEIGHTS, state="ZZ")
        self.assertEqual(result["considered_count"], 0)
        self.assertEqual(result["colleges"], [])

    def test_invalid_weights_raise_before_ranking(self):
        with self.assertRaises(ValueError):
            simulate_rankings(self.records, {"affordability": 0, "graduation": 0, "earnings": 0})

    def test_source_records_are_not_changed(self):
        original = copy.deepcopy(self.records)
        result = simulate_rankings(self.records, EQUAL_WEIGHTS)
        result["colleges"][0]["name"] = "Changed"
        self.assertEqual(self.records, original)

    def test_result_rows_keep_original_values_and_types(self):
        result = simulate_rankings(
            self.records, {"affordability": 1, "graduation": 0, "earnings": 0},
        )
        alpha = [row for row in result["colleges"] if row["school_id"] == 1][0]
        self.assertIs(type(alpha["tuition_in_state"]), int)
        self.assertEqual(alpha["tuition_in_state"], 10000)
        self.assertEqual(alpha["city"], "Test City")


if __name__ == "__main__":
    unittest.main()
