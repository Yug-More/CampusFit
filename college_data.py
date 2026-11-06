import math
import os

import requests


ENDPOINT = "https://api.data.gov/ed/collegescorecard/v1/schools"
PAGE_SIZE = 100
MAX_PAGES = 3
TIMEOUT_SECONDS = 20
FIELD_MAP = {
    "school_id": "id",
    "name": "school.name",
    "city": "school.city",
    "state": "school.state",
    "institution_type": "school.ownership",
    "student_size": "latest.student.size",
    "tuition_in_state": "latest.cost.tuition.in_state",
    "tuition_out_of_state": "latest.cost.tuition.out_of_state",
    "median_earnings": "latest.earnings.10_yrs_after_entry.median",
}
GRADUATION_FIELDS = [
    "latest.completion.completion_rate_4yr_150nt",
    "latest.completion.completion_rate_less_than_4yr_150nt",
]
REQUESTED_FIELDS = list(FIELD_MAP.values()) + GRADUATION_FIELDS
COLUMNS = [
    "school_id", "name", "city", "state", "institution_type", "student_size",
    "tuition_in_state", "tuition_out_of_state", "graduation_rate", "median_earnings",
]
OWNERSHIP_TYPES = {1: "Public", 2: "Private nonprofit", 3: "Private for-profit"}


def fetch_college_records():
    """Fetch at most three pages; never include credentials in error messages."""
    api_key = os.environ.get("COLLEGE_SCORECARD_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("Set COLLEGE_SCORECARD_API_KEY to refresh data. Local data is still available.")
    college_records = []
    for page in range(MAX_PAGES):
        parameters = {
            "fields": ",".join(REQUESTED_FIELDS),
            "school.operating": 1,
            "sort": "id:asc",
            "page": page,
            "per_page": PAGE_SIZE,
        }
        try:
            response = requests.get(
                ENDPOINT, params=parameters,
                headers={"X-Api-Key": api_key}, timeout=TIMEOUT_SECONDS,
            )
            if response.status_code == 429:
                raise ValueError("The data service rate limit was reached. Please try again later.")
            response.raise_for_status()
        except requests.Timeout:
            raise ValueError("The data service timed out. Please try again later.") from None
        except requests.ConnectionError:
            raise ValueError("Could not connect to the data service. Please try again later.") from None
        except requests.RequestException:
            raise ValueError("The data service request failed. Please try again later.") from None
        try:
            payload = response.json()
        except ValueError:
            raise ValueError("The data service returned invalid JSON.") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("The data service returned an unexpected results format.")
        page_records = payload["results"]
        if not all(isinstance(record, dict) for record in page_records):
            raise ValueError("The data service returned malformed records.")
        college_records.extend(page_records)
        if len(page_records) < PAGE_SIZE:
            break
        metadata = payload.get("metadata", {})
        total = metadata.get("total") if isinstance(metadata, dict) else None
        if isinstance(total, int) and len(college_records) >= total:
            break
    if not college_records:
        raise ValueError("The data service returned no colleges. Existing local data was kept.")
    return college_records


def clean_text(value):
    if not isinstance(value, str) or value.strip() in ("NULL", "PrivacySuppressed"):
        return ""
    return value.strip()


def clean_number(value, whole_number=False, maximum=None):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    if maximum is not None and number > maximum:
        return None
    if whole_number:
        return int(number) if number.is_integer() else None
    return number


def normalize_college_record(record):
    """Require an ID and name; leave unavailable or invalid measures missing."""
    if not isinstance(record, dict):
        return None
    school_id = clean_number(record.get("id"), whole_number=True)
    name = clean_text(record.get("school.name"))
    if not school_id or not name:
        return None
    normalized = {"school_id": school_id, "name": name}
    for column in ("city", "state"):
        normalized[column] = clean_text(record.get(FIELD_MAP[column]))
    ownership = clean_number(record.get("school.ownership"), whole_number=True)
    normalized["institution_type"] = OWNERSHIP_TYPES.get(ownership, "")
    for column in ("student_size", "tuition_in_state", "tuition_out_of_state", "median_earnings"):
        normalized[column] = clean_number(record.get(FIELD_MAP[column]), whole_number=True)
    graduation_rate = clean_number(record.get(GRADUATION_FIELDS[0]), maximum=1)
    if graduation_rate is None:
        graduation_rate = clean_number(record.get(GRADUATION_FIELDS[1]), maximum=1)
    normalized["graduation_rate"] = graduation_rate
    return normalized


def normalize_college_records(records):
    college_records = []
    seen_ids = set()
    for record in records:
        normalized = normalize_college_record(record)
        if normalized is not None and normalized["school_id"] not in seen_ids:
            college_records.append(normalized)
            seen_ids.add(normalized["school_id"])
    if not college_records:
        raise ValueError("No usable college records were found. Existing local data was kept.")
    return college_records
