import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

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
DATA_DIRECTORY = Path(__file__).resolve().parent / "data"


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
            "sort": "latest.student.size:desc",
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


def validate_saved_record(record):
    """Validate the CSV contract and restore numeric types after reading."""
    if set(record) != set(COLUMNS):
        raise ValueError("College data has unexpected columns.")
    validated = dict(record)
    for column in ("name", "city", "state", "institution_type"):
        if not isinstance(record[column], str):
            raise ValueError("College data contains invalid text.")
        validated[column] = clean_text(record[column])
    for column in ("school_id", "student_size", "tuition_in_state", "tuition_out_of_state", "graduation_rate", "median_earnings"):
        value = record[column]
        number = clean_number(value, whole_number=column != "graduation_rate",
                              maximum=1 if column == "graduation_rate" else None)
        if value not in (None, "") and number is None:
            raise ValueError("College data contains an invalid numeric value.")
        validated[column] = number
    if not validated["school_id"] or not validated["name"]:
        raise ValueError("College data requires an ID and institution name.")
    if validated["institution_type"] not in ("", *OWNERSHIP_TYPES.values()):
        raise ValueError("College data has an unknown institution type.")
    return validated


def save_college_records(records, path):
    validated = [validate_saved_record(record) for record in records]
    if not validated or len({record["school_id"] for record in validated}) != len(validated):
        raise ValueError("College data must contain records with unique IDs.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as output:
            temporary_path = Path(output.name)
            writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(validated)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_college_records(path):
    with Path(path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != COLUMNS:
            raise ValueError("College data has unexpected columns.")
        records = [validate_saved_record(record) for record in reader]
    if not records or len({record["school_id"] for record in records}) != len(records):
        raise ValueError("College data is empty or contains duplicate IDs.")
    return records


def create_metadata(record_count):
    return {
        "source": "U.S. Department of Education College Scorecard",
        "endpoint": ENDPOINT,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "record_count": record_count,
        "requested_fields": REQUESTED_FIELDS,
        "scope_or_limit": f"Operating institutions; student size descending; at most {MAX_PAGES} pages of {PAGE_SIZE} records. Limited to large institutions, not a complete national dataset.",
    }


def save_metadata(metadata, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as output:
            temporary_path = Path(output.name)
            json.dump(metadata, output, indent=2)
            output.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_metadata(path):
    with Path(path).open(encoding="utf-8") as source:
        metadata = json.load(source)
    required = {"source", "endpoint", "retrieved_at", "record_count", "requested_fields", "scope_or_limit"}
    if not isinstance(metadata, dict) or not required.issubset(metadata):
        raise ValueError("Data metadata is incomplete.")
    if not isinstance(metadata["record_count"], int) or metadata["record_count"] < 1:
        raise ValueError("Data metadata has an invalid record count.")
    if not isinstance(metadata["retrieved_at"], str):
        raise ValueError("Data metadata has an invalid retrieval timestamp.")
    datetime.fromisoformat(metadata["retrieved_at"])
    return metadata


def get_available_college_data(data_directory=None):
    directory = Path(data_directory) if data_directory is not None else DATA_DIRECTORY
    messages = []
    for filename, metadata_name, label in (
        ("colleges.csv", "metadata.json", "Runtime cache"),
        ("sample_colleges.csv", "sample_metadata.json", "Sample fallback"),
    ):
        try:
            records = load_college_records(directory / filename)
        except (OSError, ValueError, csv.Error, UnicodeError):
            continue
        try:
            metadata = load_metadata(directory / metadata_name)
            if metadata["record_count"] != len(records):
                raise ValueError("Record count does not match.")
        except (OSError, ValueError, UnicodeError):
            metadata = {}
            messages.append("Retrieval details are unavailable for this local dataset.")
        if label == "Sample fallback":
            messages.append("Using the committed sample because no usable runtime cache was found.")
        if not os.environ.get("COLLEGE_SCORECARD_API_KEY", "").strip():
            messages.append("No API key is configured. Local data remains available; set COLLEGE_SCORECARD_API_KEY to refresh.")
        return records, metadata, label, " ".join(messages)
    return [], {}, "Unavailable", "No usable local college data was found. Restore the sample files or refresh with an API key."


def publish_runtime_cache(records, metadata, directory):
    """Prepare both files first and restore previous files on a write failure."""
    directory.mkdir(parents=True, exist_ok=True)
    filenames = ("colleges.csv", "metadata.json")
    with tempfile.TemporaryDirectory(dir=directory) as staging_directory:
        staging = Path(staging_directory)
        save_college_records(records, staging / filenames[0])
        save_metadata(metadata, staging / filenames[1])
        load_college_records(staging / filenames[0])
        load_metadata(staging / filenames[1])
        for filename in filenames:
            if (directory / filename).exists():
                shutil.copyfile(directory / filename, staging / (filename + ".backup"))
        replaced = []
        try:
            for filename in filenames:
                os.replace(staging / filename, directory / filename)
                replaced.append(filename)
        except OSError:
            for filename in replaced:
                backup = staging / (filename + ".backup")
                if backup.exists():
                    os.replace(backup, directory / filename)
                else:
                    (directory / filename).unlink(missing_ok=True)
            raise


def refresh_college_data(data_directory=None):
    directory = Path(data_directory) if data_directory is not None else DATA_DIRECTORY
    try:
        records = normalize_college_records(fetch_college_records())
        publish_runtime_cache(records, create_metadata(len(records)), directory)
    except ValueError as error:
        return False, str(error)
    except OSError:
        return False, "Could not save refreshed data. Please check local folder permissions."
    return True, f"Refresh successful: saved {len(records)} college records."
