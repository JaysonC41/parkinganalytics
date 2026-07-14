# Project Requirements Audit

This matrix maps the published project requirements to evidence in the repo.
I used it as a final submission check; the actual analysis narrative is in the
notebooks.

| Requirement | Evidence | Status |
| --- | --- | --- |
| At least 10 command-line commits | The `main` branch contained 20 commits before this final update; local metadata does not show GitHub's web-flow identity. | Exceeded |
| At least 2 meaningfully combined datasets | The `parking_enriched` SQL view joins parking, weather, fine schedule, and Census data by date, violation code, and borough. | Exceeded |
| At least 1,000 rows and 10 columns | Notebook 02 validates that `parking_enriched` contains 7,056,788 combined rows and 35 columns. | Exceeded |
| Sources cited and credited | Root `README.md`, `data/README.md`, notebook 02, and `source_metadata` include publishers and links. | Met |
| Pandas cleaning and wrangling | Notebook 01 and `clean_csv.py` use chunked Pandas processing. | Met |
| Missing values | Blank strings become `pd.NA`; required identifiers/dates are removed when invalid; analysis reports vehicle-field completeness. | Met |
| Duplicates | Duplicate `summons_number` values are removed within and across chunks. | Met |
| Data types | Dates and numeric identifiers are explicitly parsed; SQLite integer columns use nullable integer conversion. | Met |
| Transformations | Columns are normalized, boroughs mapped, and year/month/weekday fields derived. | Exceeded |
| At least 3 EDA techniques | Missing-value profiling, grouped frequency analysis, time trends, pivot tables, population-adjusted rates, and cross-variable heatmaps. | Exceeded |
| Relational design explained | `reports/ERD.md` documents the fact/dimension design and key choices. | Met |
| ERD included | Mermaid ERD in `reports/ERD.md` and notebook 02 relationship diagram. | Met |
| SQLite3 built with Python | `src/nycparking/sqlite/build_database.py` builds and validates the database. | Met |
| At least 3 intermediate/advanced SQL queries | Notebook 02 includes weather, fine exposure, population-rate, and four-source queries using multi-table joins, aggregation, a subquery, and `HAVING`. | Exceeded |
| At least 3 custom functions | The SQLite builder contains 12 documented functions; additional functions support cleaning and the earlier ETL workflow. | Exceeded |
| At least 3 chart types | Notebook 03 includes line, horizontal/vertical bar, heatmap, and filled distribution charts. | Exceeded |
| Clear visual design | Charts include titles, axis labels, number formatting, consistent themes, and written findings. | Met |
| Markdown reasoning and conclusions | All three notebooks include explanatory Markdown before major steps and conclusion sections. | Met |
| Professional README | Unique title, questions, findings, source links, setup for Windows/macOS/Linux, run instructions, limitations, and acknowledgements. | Met |
| `requirements.txt` | Dependency file is present at repository root. | Met |
| Data or reproduction path | Small inputs are versioned; the README links the downloadable large source and documents cleaning/database commands. | Met |
| Relative paths | Scripts and notebooks derive paths from the project root; no user-specific runtime path is required. | Met |

## Validation Snapshot

- SQLite tables: `parking_violations`, `weather_daily`, `violation_lookup`,
  `census_borough`, and `source_metadata`; combined view: `parking_enriched`
- Parking rows: 7,056,788
- Parking columns: 21
- Combined view rows: 7,056,788
- Combined view columns: 35
- Rows with non-null weather, violation description, listed fine, and
  population fields: 6,894,693
- Foreign-key errors: 0
- Weather matches: 7,056,788
- Violation lookup matches: 7,056,788
- Mapped borough/Census matches: 6,899,010

The 157,778 records without a borough match have a missing or unmapped source
county value. They are retained for non-borough analysis and excluded from
population-rate comparisons.

## Known Limitations

- The supplied fiscal-year file has substantial coverage from July through
  November 2024 and sparse records afterward. Notebook 03 avoids interpreting
  sparse months as a real enforcement decline.
- Vehicle model is not present in the source. Vehicle comparisons use make,
  standardized color, body type, and model year.
- Ticket counts are not counts of unique vehicles or drivers.
- Listed fine exposure is not actual revenue or collections.
- Census population is a July 1, 2025 estimate and provides context rather
  than a causal explanation.
