import math

import pandas as pd

from college_data import COLUMNS


WEIGHT_LABELS = {
    "affordability": "Affordability",
    "graduation": "Graduation rate",
    "earnings": "Median earnings",
}
SCORE_FIELDS = {
    "affordability": "tuition_in_state",
    "graduation": "graduation_rate",
    "earnings": "median_earnings",
}
NEUTRAL_SCORE = 50.0


def to_number(value):
    """Return a finite float, or None for missing, boolean, or invalid values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return number


def build_college_table(college_records):
    """Copy the loader's records into a DataFrame; missing scoring values become NaN."""
    table = pd.DataFrame(college_records, columns=COLUMNS)
    for field in SCORE_FIELDS.values():
        table[field] = table[field].map(to_number).astype("float64")
    return table


def filter_by_state(table, state):
    if not state:
        return table
    return table[table["state"] == state]


def filter_by_institution_type(table, institution_type):
    if not institution_type:
        return table
    return table[table["institution_type"] == institution_type]


def required_fields(weight_shares):
    return [SCORE_FIELDS[category] for category, share in weight_shares.items() if share > 0]


def keep_complete_colleges(table, weight_shares):
    """Drop colleges missing a value that a weight above zero depends on."""
    return table.dropna(subset=required_fields(weight_shares))


def min_max_scores(values, higher_is_better=True):
    """Scale values from 0 to 100 within the colleges being compared."""
    lowest = values.min()
    highest = values.max()
    if lowest == highest:
        neutral = values.copy()
        neutral[values.notna()] = NEUTRAL_SCORE
        return neutral
    if higher_is_better:
        return (values - lowest) / (highest - lowest) * 100
    return (highest - values) / (highest - lowest) * 100


def affordability_scores(tuition):
    """Lower in-state tuition earns a higher score."""
    return min_max_scores(tuition, higher_is_better=False)


def graduation_scores(graduation_rates):
    return min_max_scores(graduation_rates)


def earnings_scores(median_earnings):
    return min_max_scores(median_earnings)


def normalize_weights(weights):
    """Turn the three weights into shares that add up to 1, or raise ValueError."""
    numbers = {}
    for category, label in WEIGHT_LABELS.items():
        number = to_number(weights.get(category))
        if number is None or number < 0:
            raise ValueError(f"{label} weight must be a non-negative number.")
        numbers[category] = number
    total = sum(numbers.values())
    if total == 0:
        raise ValueError("At least one weight must be greater than zero.")
    return {category: number / total for category, number in numbers.items()}


def calculate_final_scores(table, weight_shares):
    """Score each weighted category, then add the weighted scores into a final score."""
    scored = table.copy()
    scored["final_score"] = 0.0
    if weight_shares["affordability"] > 0:
        scored["affordability_score"] = affordability_scores(scored["tuition_in_state"])
        scored["final_score"] += scored["affordability_score"] * weight_shares["affordability"]
    if weight_shares["graduation"] > 0:
        scored["graduation_score"] = graduation_scores(scored["graduation_rate"])
        scored["final_score"] += scored["graduation_score"] * weight_shares["graduation"]
    if weight_shares["earnings"] > 0:
        scored["earnings_score"] = earnings_scores(scored["median_earnings"])
        scored["final_score"] += scored["earnings_score"] * weight_shares["earnings"]
    return scored


def rank_colleges(scored):
    """Order colleges from highest to lowest final score, breaking ties by name."""
    ranked = scored.sort_values(["final_score", "name"], ascending=[False, True])
    ranked["rank"] = range(1, len(ranked) + 1)
    return ranked


def limit_results(ranked, limit):
    """Keep the top `limit` colleges; None keeps every ranked college."""
    if limit is None:
        return ranked
    return ranked.head(limit)


def build_result_rows(ranked, college_records):
    """Pair each ranked row with a copy of its original record for display."""
    rows = []
    for position in ranked.index:
        college = dict(college_records[position])
        college["rank"] = int(ranked.loc[position, "rank"])
        college["score"] = float(ranked.loc[position, "final_score"])
        rows.append(college)
    return rows


def simulate_rankings(college_records, weights, state="", institution_type="", limit=None):
    """Filter, score, and rank colleges by the user's weights without changing the records."""
    weight_shares = normalize_weights(weights)
    table = build_college_table(college_records)
    table = filter_by_state(table, state)
    table = filter_by_institution_type(table, institution_type)
    complete = keep_complete_colleges(table, weight_shares)
    ranked = rank_colleges(calculate_final_scores(complete, weight_shares))
    return {
        "weights": weight_shares,
        "considered_count": len(table),
        "excluded_count": len(table) - len(complete),
        "ranked_count": len(ranked),
        "colleges": build_result_rows(limit_results(ranked, limit), college_records),
    }
