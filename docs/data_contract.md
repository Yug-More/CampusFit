# College data contract for Sean

Use the loader in `college_data.py` rather than parsing CSV again. It restores
numeric types, validates records, and handles runtime-cache/sample selection.
This contract supplies data only; analysis, scoring, and visualization belong to Sean.

## Supported entry point

`get_available_college_data(data_directory=None)` performs local reads only. It
never calls the API, requires no key, and does not write files.

- Omit `data_directory` for normal use. Paths are anchored to `college_data.py`,
  so changing the process working directory does not change the default files.
- Alternatively pass a `pathlib.Path` or directory string. Both runtime and sample
  files are then looked up in that directory; it does not also search the default.
- The return value is `(records, metadata, source, message)`.
- `records` is a list of dictionaries, with the exact keys below. It contains all
  loaded records, before Explorer filtering, sorting, or display limits.
- `metadata` is a dictionary, or `{}` when unavailable, invalid, or inconsistent
  with the loaded record count. Use `len(records)` for the actual count.
- `source` is `"Runtime cache"`, `"Sample fallback"`, or `"Unavailable"`.
- `message` is a human-readable status string, possibly empty. Do not parse it to
  decide which source was used; use `source` and `records` instead.
- If neither CSV is usable, the return is an empty list, empty metadata dictionary,
  `"Unavailable"`, and a helpful message. The caller should handle the empty list.

Valid usage, without assuming a particular sample result:

```python
from college_data import get_available_college_data

college_records, metadata, data_source, status_message = get_available_college_data()
if not college_records:
    print(status_message)
else:
    print("Loaded records:", len(college_records))
    print("Data source:", data_source)
    print("Retrieved:", metadata.get("retrieved_at", "Not available"))
    for college in college_records:
        if college["graduation_rate"] is not None:
            print(college["name"], college["graduation_rate"] * 100)
```

`load_college_records(path)` is also available for an explicitly chosen CSV file.
It returns just the list of dictionaries and raises file/validation errors for
unusable input; it does not provide fallback. Prefer the high-level loader above
for the simulator. Neither function filters or ranks colleges. Avoid writing
analysis output over these source files.

## Exact columns and Python types

CSV headers use this exact order; dictionary keys have the same names:

1. `school_id`: positive `int`, required. IPEDS institution identifier from `id`.
2. `name`: nonempty `str`, required. Institution name from `school.name`.
3. `city`: `str`, possibly empty. City from `school.city`.
4. `state`: `str`, possibly empty. State abbreviation from `school.state`.
5. `institution_type`: `str`, possibly empty. From `school.ownership`:
   1 → `Public`, 2 → `Private nonprofit`, 3 → `Private for-profit`.
   Unknown or missing codes become an empty string.
6. `student_size`: non-negative `int` or `None`. Undergraduate certificate/degree-
   seeking enrollment from `latest.student.size`, not total graduate enrollment.
7. `tuition_in_state`: non-negative `int` or `None`. In-state tuition and fees in
   dollars from `latest.cost.tuition.in_state`; not net price, housing, or total cost.
8. `tuition_out_of_state`: non-negative `int` or `None`. Out-of-state tuition and
   fees in dollars from `latest.cost.tuition.out_of_state`.
9. `graduation_rate`: `float` from 0 through 1, or `None`. First use valid
   `latest.completion.completion_rate_4yr_150nt`; otherwise use valid
   `latest.completion.completion_rate_less_than_4yr_150nt`. They are alternatives,
   not averaged. A value of 0.60 means 60%; do not treat it as 0.60 percent.
10. `median_earnings`: non-negative `int` or `None`. Annual dollar earnings from
    `latest.earnings.10_yrs_after_entry.median`, for working, non-enrolled students
    ten years after entry. It covers undergraduate Title IV federal-aid recipients,
    not all students, only graduates, or a prediction of future personal earnings.

Completion measures concern first-time, full-time degree/certificate-seeking
undergraduates completing at that institution within 150% of normal time. The
four-year and shorter-program measures describe different cohorts/program lengths.
The verification-time cohort years and official dictionary links are documented
in the [README](../README.md#official-source-and-verified-fields). The `latest`
source fields can come from different reporting years and change after releases.

## Missing values and validation

CSV missing cells are blank. Loaded numeric missing values are `None`; text missing
values are `""`. Genuine numeric zeroes remain zeroes: test `value is not None`,
not `if value`, before including a measure. Do not substitute zero for missing
values or convert display strings such as `Not available` into analysis data.

Normalization preserves missing/suppressed values as missing, converts invalid or
out-of-range numeric measures to missing, skips records without an ID/name, and
keeps the first valid record per ID. Saved CSVs must match the columns and numeric
ranges and contain unique IDs; an invalid runtime CSV triggers sample fallback.
Display formatting occurs in Jinja and does not change this numeric contract.

## File locations and metadata

Locations below are relative to the repository root:

- Runtime cache: `data/colleges.csv`; runtime metadata: `data/metadata.json`.
- Committed fallback: `data/sample_colleges.csv`; metadata: `data/sample_metadata.json`.

A usable runtime CSV takes priority, including when no key is configured. If it is
missing or invalid, the loader tries the committed sample. A metadata problem does
not discard usable CSV records. Both runtime files are prepared and validated
before publication; ordinary refresh failures preserve existing data. The two
files are not a database transaction, so avoid simultaneous refreshes and account
for process interruption as described in the README.

Metadata fields are `source` (data-provider description), `endpoint` (key-free API
endpoint), `retrieved_at` (ISO 8601 UTC retrieval timestamp), `record_count` (integer
saved count), `requested_fields` (list of API field names), and `scope_or_limit`
(scope description). Retrieval time is not the reporting year of each measure.
No API key or credential-bearing request URL is stored in these files.

## Dataset limitations

Refresh uses `school.operating=1` and `sort=latest.student.size:desc`, at most three
pages of 100 records. It favors large undergraduate institutions, including online
institutions, and is neither every U.S. institution nor a representative sample.
The committed sample contains 40 official records across 16 states, including a
small private-institution supplement. See sample metadata for its retrieval time
and selection method. Missing outcomes, different cohorts, and mixed reporting
years limit comparisons. Sean must choose and document his own analysis policy
for missing data without changing Yug's source records.
