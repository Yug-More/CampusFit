import math


SORT_OPTIONS = {
    "name": "College name: A–Z",
    "tuition_asc": "In-state tuition: Low to high",
    "tuition_desc": "In-state tuition: High to low",
    "graduation_desc": "Graduation rate: High to low",
    "earnings_desc": "Median earnings: High to low",
    "size_desc": "Student size: High to low",
}
RESULT_LIMITS = {"10": "10", "20": "20", "50": "50", "all": "All"}
SORT_FIELDS = {
    "tuition_asc": "tuition_in_state",
    "tuition_desc": "tuition_in_state",
    "graduation_desc": "graduation_rate",
    "earnings_desc": "median_earnings",
    "size_desc": "student_size",
}


def get_filter_options(college_records):
    states = sorted({record["state"] for record in college_records if record["state"]})
    institution_types = sorted({record["institution_type"] for record in college_records
                                if record["institution_type"]})
    return states, institution_types


def validate_number(value, label, messages, maximum=None):
    if not value:
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        number = math.nan
    if not math.isfinite(number) or number < 0 or (maximum is not None and number > maximum):
        if maximum is None:
            messages.append(f"{label} must be a non-negative number. This filter was ignored.")
        else:
            messages.append(f"{label} must be a number from 0 to {maximum}. This filter was ignored.")
        return None
    return number


def validate_filters(query, states, institution_types):
    """Keep submitted values for the form, while returning safe filter values."""
    selected = {}
    for field in ("name", "state", "institution_type", "maximum_tuition", "minimum_graduation"):
        selected[field] = query.get(field, "").strip()
    selected["sort"] = query.get("sort", "name").strip()
    selected["limit"] = query.get("limit", "20").strip()
    filters = dict(selected)
    messages = []
    for field, choices, label in (
        ("state", states, "state"),
        ("institution_type", institution_types, "institution type"),
    ):
        if selected[field] and selected[field] not in choices:
            messages.append(f"The selected {label} is unavailable in this dataset. This filter was ignored.")
            filters[field] = ""
    filters["maximum_tuition"] = validate_number(
        selected["maximum_tuition"], "Maximum in-state tuition", messages,
    )
    minimum_percentage = validate_number(
        selected["minimum_graduation"], "Minimum graduation rate", messages, maximum=100,
    )
    filters["minimum_graduation"] = None
    if minimum_percentage is not None:
        filters["minimum_graduation"] = minimum_percentage / 100
    if selected["sort"] not in SORT_OPTIONS:
        messages.append("Unknown sort option. Results are sorted by college name.")
        filters["sort"] = "name"
    if selected["limit"] not in RESULT_LIMITS:
        messages.append("Unknown results limit. Showing at most 20 results.")
        filters["limit"] = "20"
    return selected, filters, messages


def filter_colleges(college_records, filters):
    matching = []
    search_name = filters.get("name", "").strip().casefold()
    for college in college_records:
        if search_name not in college["name"].casefold():
            continue
        if filters.get("state") and college["state"] != filters["state"]:
            continue
        if filters.get("institution_type") and college["institution_type"] != filters["institution_type"]:
            continue
        maximum_tuition = filters.get("maximum_tuition")
        if maximum_tuition is not None:
            if college["tuition_in_state"] is None or college["tuition_in_state"] > maximum_tuition:
                continue
        minimum_graduation = filters.get("minimum_graduation")
        if minimum_graduation is not None:
            if college["graduation_rate"] is None or college["graduation_rate"] < minimum_graduation:
                continue
        matching.append(college)
    return matching


def sort_colleges(college_records, sort_option):
    by_name = sorted(college_records, key=lambda college: college["name"].casefold())
    if sort_option == "name":
        return by_name
    field = SORT_FIELDS[sort_option]
    available = [college for college in by_name if college[field] is not None]
    missing = [college for college in by_name if college[field] is None]
    available.sort(key=lambda college: college[field], reverse=sort_option != "tuition_asc")
    return available + missing


def limit_colleges(college_records, limit):
    if limit == "all":
        return list(college_records)
    return college_records[:int(limit)]
