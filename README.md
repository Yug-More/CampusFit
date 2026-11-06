
# CampusFit

**San José State University | CS 122 — Advanced Programming with Python**

**Authors:** Yug Amol More and Sean Aminov

## Project Overview

CampusFit is a Python-based web application designed to help students explore and compare colleges based on their personal preferences and goals. The application will use publicly available data from the U.S. Department of Education's College Scorecard to provide information about tuition costs, graduation rates, locations, and student outcomes. Students will be able to search for colleges, filter their options, and compare institutions using different criteria. One of the main features will be a What-If Decision Simulator, which allows users to adjust their priorities and see how their college rankings change. Our goal is to make the college selection process easier to understand by presenting useful information through organized comparisons and visualizations.

## Project Outline

### 1. Interface Plan

We plan to develop the application using Python and Flask, with a web interface that allows students to interact with the collected college data.

The interface will include two main pages:

- **College Explorer:** Allows users to search for colleges, apply filters, and view information about individual institutions.
- **Decision Simulator:** Allows users to adjust factors such as affordability, graduation rates, and potential earnings to generate personalized college comparisons.

We also plan to include search fields, dropdown menus, sliders, buttons, and other interactive elements to make the application easy to navigate.

### 2. Data Collection and Storage Plan
**Responsible: Yug Amol More (Author #1)**

- Retrieve publicly available college information using the U.S. Department of Education's College Scorecard API.
- Collect relevant data, including institution names, locations, tuition costs, graduation rates, and available earnings information.
- Use Python to retrieve and organize the data into a consistent structure.
- Handle missing or incomplete values to keep the information suitable for comparisons.
- Store the collected data locally in CSV or JSON format for use throughout the application.
- Make the organized data accessible to the College Explorer and Decision Simulator pages.

### 3. Data Analysis and Visualization Plan
**Responsible: Sean Aminov (Author #2)**

- Use Python, Pandas, and NumPy to analyze the college data collected from the College Scorecard API.
- Compare institutions based on factors such as tuition costs, graduation rates, and available earnings information.
- Develop a weighted scoring system that ranks colleges according to the user's selected preferences and priorities.
- Implement a What-If Decision Simulator that recalculates college rankings when users adjust the importance of different factors.
- Use Matplotlib to create visualizations, including bar charts and comparison graphs, to highlight differences between colleges.
- Display the analysis results through the Flask interface to help students understand the trade-offs between affordability, academic outcomes, and potential earnings.

## Technologies

The following technologies are planned for the project:

- **Python:** Data collection, processing, and application logic
- **Flask:** Web application and user interface
- **Pandas:** Data organization and manipulation
- **NumPy:** Numerical calculations and data analysis
- **Matplotlib:** Data visualization
- **CSV / JSON:** Local data storage
- **College Scorecard API:** Publicly available college information

## Current implementation status

Yug's College Explorer now loads local College Scorecard records and provides a
POST-based **Refresh Data** action. Retrieval, normalization, CSV/JSON storage,
sample fallback, College Explorer filters, sorting, and result limits are
implemented. Sean's Decision Simulator is still a temporary placeholder;
analysis, scoring, and visualization remain reserved for Sean.

### Setup and run

Use Python 3.10 or newer (tested with Python 3.13.2).

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

On Windows, activate with `.venv\Scripts\activate` instead. Open
<http://127.0.0.1:5000/explorer>. No API key is needed to view the committed sample.
The only direct dependencies are Flask and requests.

To enable refresh, obtain a private key through the
[official College Scorecard documentation](https://collegescorecard.ed.gov/data/api-documentation/).
Set it in your terminal before starting Flask:

```bash
export COLLEGE_SCORECARD_API_KEY="YOUR_PRIVATE_KEY"
```

In PowerShell, use `$env:COLLEGE_SCORECARD_API_KEY="YOUR_PRIVATE_KEY"`.
Do not commit a key or environment file. The application reads the environment
with `os.environ.get`; it does not automatically read `.env` files. Requests send
the key in the `X-Api-Key` header, never in stored URLs or metadata.

Run all deterministic tests without live API requests:

```bash
python -m unittest discover -s tests -v
```

### Files and local data contract

- `app.py`: Flask routes and data-to-template connection.
- `college_data.py`: retrieval, cleaning, validation, storage, loading, and refresh.
- `college_filters.py`: query validation, filtering, sorting, and result limiting.
- `templates/` and `static/css/`: shared layout, Explorer, simulator placeholder, and styling.
- `data/sample_colleges.csv` and `data/sample_metadata.json`: committed official sample.
- `data/colleges.csv` and `data/metadata.json`: generated runtime files, ignored by Git.
- `tests/`: unittest tests and a small, explicitly synthetic JSON fixture.
- `docs/data_contract.md`: the supported loader contract and integration example.

CSV files use UTF-8 and a header with exactly these columns, in this order:

```text
school_id,name,city,state,institution_type,student_size,tuition_in_state,tuition_out_of_state,graduation_rate,median_earnings
```

Sean should call `get_available_college_data()` to receive
`(records, metadata, source, message)` with runtime/sample fallback. The full
[data contract](docs/data_contract.md) documents parameters, return types, field
meanings, paths, and a runnable usage example. For explicitly chosen CSV files,
`load_college_records(path)` returns just the records and does not provide fallback.
IDs, enrollment, tuition, and earnings load as integers; graduation rates are
fractions from 0 to 1; missing numbers are `None`; text values are strings.
No scoring or analysis is performed by either loader.

Metadata contains `source`, `endpoint`, `retrieved_at` (ISO 8601 UTC),
`record_count`, `requested_fields`, and `scope_or_limit`. Retrieval time describes
when CampusFit obtained the snapshot, not the year each measure was collected.

### Official source and verified fields

Verified on November 5, 2026 using the official
[API documentation](https://collegescorecard.ed.gov/data/api-documentation/),
[data dictionary](https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx)
(`Institution_Data_Dictionary` and `Most_Recent_Inst_Cohort_Map`), and
[institution technical documentation](https://collegescorecard.ed.gov/files/InstitutionDataDocumentation.pdf).
The endpoint is `https://api.data.gov/ed/collegescorecard/v1/schools`.

API-to-CSV mappings:

- `id` → `school_id`: IPEDS institution identifier (UNITID).
- `school.name` → `name`; `school.city` → `city`; `school.state` → `state`.
- `school.ownership` → `institution_type`: 1 = Public, 2 = Private nonprofit,
  3 = Private for-profit. Unknown ownership remains missing.
- `latest.student.size` → `student_size`: undergraduate certificate/degree-seeking enrollment.
- `latest.cost.tuition.in_state` → `tuition_in_state`: in-state tuition and fees in dollars.
- `latest.cost.tuition.out_of_state` → `tuition_out_of_state`: out-of-state tuition and fees in dollars.
- `latest.completion.completion_rate_4yr_150nt` or
  `latest.completion.completion_rate_less_than_4yr_150nt` → `graduation_rate`:
  first-time, full-time degree/certificate-seeking students completing at the
  institution within 150% of normal time. Use the four-year value when available,
  otherwise the less-than-four-year value; do not average them.
- `latest.earnings.10_yrs_after_entry.median` → `median_earnings`: median annual
  earnings of working, non-enrolled students ten years after entry. Earnings
  cover undergraduate Title IV federal-aid recipients, not all students or only graduates.

The dictionary's most-recent map identifies completion cohorts as fall 2019 /
academic year 2019–20 for four-year institutions and fall 2022 / academic year
2022–23 for shorter institutions, reported in IPEDS 2025–26. The earnings measure
pools 2011–12 and 2012–13 entry cohorts, measured in calendar years 2022 and 2023,
inflation-adjusted to 2024 dollars. These are verification-time definitions;
`latest` can change with later releases and mixes reporting years across metrics.

### Scope, sample, and refresh behavior

A refresh requests only the 11 mapped source fields, filters `school.operating=1`,
and sorts `latest.student.size:desc`. This exact descending student-size syntax is
explicitly supported in the official API documentation (Sorting section), verified
on November 5, 2026. Pagination starts at page 0 with `per_page=100`; it stops after
three pages (at most 300 records), a short/empty page, or the reported total.
Each request has a 20-second timeout. This selects up to 300 of the largest
currently operating institutions across the country by undergraduate enrollment,
including institutions with online enrollment. It is not a complete or
representative national dataset and favors large institutions. Filters operate
only on loaded local data, not on the entire API.

The committed sample contains 40 real official API records: the 30 largest
operating institutions by `latest.student.size:desc`, plus the first 10 operating
private nonprofit/for-profit institutions by ID (`school.ownership=2,3`) to
demonstrate ownership and missing-value variety. Values are unchanged from the
official source apart from the documented normalization; sample rows are ordered
by college name. The sample covers 16 states (AL, AZ, CA, FL, GA, ID, IN, MD, MI,
NH, OH, PA, TX, UT, VA, WV), all three ownership types, different costs and outcomes,
and genuinely missing measures. Two small requests used the public
`DEMO_KEY`, permitted for initial exploration by the
[api.data.gov developer manual](https://api.data.gov/docs/developer-manual/)
(30 requests/hour and 50/day per IP). This key is never an application default.
The snapshot was retrieved November 5, 2026 Pacific time; its UTC metadata timestamp
is `2026-11-06T00:33:21.684883+00:00`.

Missing, suppressed, nonnumeric, nonfinite, or out-of-range numerical values become
`None`, are written as blank CSV cells, and display as **Not available**. Missing
text becomes an empty string. Genuine zeroes remain zeroes. Records without a
positive institution ID or name are skipped; duplicate IDs retain the first valid
record. Invalid saved CSV files are rejected rather than silently trusted.

The loader prefers usable runtime CSV data, then the committed sample. Missing or
invalid metadata does not discard otherwise usable records; retrieval details are
shown as unavailable. With no API key, local data remains usable and refresh
explains how to configure a key.

Refresh downloads and validates records before preparing both runtime files.
Writes use temporary files and replacement; a caught publication failure restores
previous files. Timeouts, connection/HTTP failures (including rate limits), invalid
JSON, unexpected structures, and unusable/empty results leave the old cache intact.
A successful POST redirects back to the Explorer; failed refreshes show a safe
message alongside available local data. Error messages omit raw request details.

This is a local class-project workflow: simultaneous refreshes and interruption
between the two file replacements are not coordinated as a database transaction.
Use one local application process. Sean's analysis, scoring, simulator, and
visualizations remain reserved for Sean and are not implemented by this work.

### College Explorer controls

The filter form uses GET, so submitted selections appear in a reproducible URL.
Controls use only the currently loaded dataset:

- **College name:** partial, case-insensitive search; surrounding spaces are ignored.
- **State:** all states or one abbreviation; choices come from the complete loaded
  dataset and are sorted alphabetically.
- **Institution type:** all types or one ownership type; choices come from loaded
  records and are sorted consistently.
- **Maximum in-state tuition:** a non-negative dollar amount, including fees.
  Colleges at or below the amount match. This deliberately uses only in-state
  tuition, never out-of-state tuition. Missing in-state tuition is excluded when
  the filter is active, including when the maximum is zero.
- **Minimum graduation rate (%):** a number from 0 through 100, converted to a
  decimal fraction for comparison. For example, 60 means 60%, compared with 0.60.
  Colleges at or above the rate match; missing rates are excluded when active.
- **Sort results:** college name A–Z; in-state tuition low to high or high to low;
  graduation rate, median earnings, or student size high to low. Numeric sorts
  place missing values last in either direction. Equal numeric values use college
  name as the secondary order.
- **Results limit:** 10, 20 (default), 50, or All matching local records. Filtering
  and sorting happen before the display limit is applied.
- **Apply Filters:** submits the GET form and keeps submitted selections visible.
- **Reset Filters:** a native button submits a separate empty GET form to
  `/explorer`, clearing query parameters and restoring the default college-name
  sort and 20-result limit; it does not erase cached data.
- **Refresh Data:** remains a separate POST action. It downloads the documented
  large-institution subset, then redirects to the default Explorer after success.

Invalid numeric inputs are shown with short messages and that filter is ignored.
Unknown states/types are ignored with a message; unknown sort/limit selections
fall back to college name/20. Other valid filters still apply. An empty result
shows a helpful message. Missing values display as **Not available**, money uses
dollar signs and commas, enrollment uses commas, and graduation rates use
percentages. Formatting does not change saved values. The page reports the loaded,
matching, and displayed counts, along with source and retrieval time. Filters do
not make API calls. The results table scrolls horizontally on narrow screens and
supports keyboard focus.

Example URL (after starting the local app):

<http://127.0.0.1:5000/explorer?name=Arizona&state=AZ&institution_type=Public&maximum_tuition=13000&minimum_graduation=60&sort=tuition_asc&limit=10>

Run the complete offline test suite with
`python -m unittest discover -s tests -v`. It covers query validation, combined
filters, all sort/limit options, missing values, display formatting, reset, and
existing retrieval/refresh behavior. Broader dataset coverage and integration with
Sean's future analysis should be reviewed separately before submission.


### Yug's rubric checklist

This checks the responsibility list supplied for Yug, not a claim about a final
course grade or completion of Sean's work.

- [x] Live web-data access: requests-based official Scorecard retrieval with a timeout.
- [x] Official source and exact API fields identified above and in the data contract.
- [x] Local organization: validated CSV records and separate metadata JSON.
- [x] Committed official sample and runtime-to-sample fallback without a key.
- [x] College Explorer route with functional controls and updated results/counts.
- [x] Missing data stays missing, with honest display and active-filter behavior.
- [x] Portable paths anchored to the module; no personal path configuration needed.
- [x] Python requirement, installation, API-key, run, and test instructions provided.
- [x] Dataset limitations, demo, integration contract, and future improvements documented.
- [x] Sean's planned analysis and visualization preserved; simulator remains under development.

**Functional widget count: 10.** The counted widgets are College name, State,
Institution type, Maximum in-state tuition, Minimum graduation rate, Sort results,
Results limit, Apply Filters, Reset Filters, and Refresh Data. These are seven
input/select controls and three native buttons. Site navigation links, static
text, tables, and counts are excluded.

### Short demo for Yug

1. Open `/explorer` using the run instructions above.
2. Explain that the source is the official U.S. Department of Education College Scorecard.
3. Show the current source, UTC retrieval time, and loaded-record count.
4. Search for `Arizona` to demonstrate partial, case-insensitive matching.
5. Combine State `AZ` and Institution type `Public`; explain that both conditions apply.
6. Change sorting to median earnings high to low and the results limit to 10.
7. Use Reset Filters to restore the default unfiltered view.
8. Explain the committed sample fallback. Without a key, Refresh Data gives setup
   guidance and retains local data; with a configured key, it downloads the bounded
   large-institution subset. Automated refresh demonstrations use mocked responses.

### Review notes and future improvements

Yug's implementation uses only Flask and requests as direct dependencies, plus
standard-library modules and unittest. No database, framework, analysis libraries,
or simulator implementation is included. Existing course plans above describe
future shared work, not installed dependencies or completed features.

The local CSV workflow does not coordinate concurrent refreshes or guarantee a
transaction across CSV and metadata after an abrupt process interruption. Keep
one local application process. Missing outcomes, different reporting years, and
the large-institution selection remain comparison limitations.

Future improvements, outside this handoff, could include a separately approved
broader data-selection strategy, explicit per-metric reporting-year information,
and a documented missing-data policy for Sean's analysis. Sean should integrate
through the loader rather than duplicating CSV parsing. Partner review should
confirm that contract and the course rubric before merging; no simulator, scoring,
or chart work was added here.
