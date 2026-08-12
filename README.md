# Curbside Patterns: NYC Parking Analytics

Curbside Patterns is an end-to-end analysis of more than 7 million New York
City parking violation records. It uses Pandas to clean a 1.3 GB source file,
Python and SQLite to build a relational analytical database, SQL to combine
four datasets, and Matplotlib/Seaborn to communicate the results.

The parking records are enriched with daily weather, violation descriptions
and listed fine amounts, and Census Vintage 2025 population estimates for the
five boroughs. The workflow can be rerun from the source files without
committing generated gigabyte-scale outputs to Git.

## Questions

1. How did parking ticket volume change by month and day of week?
2. Which violation types accounted for the most tickets?
3. What vehicle characteristics appeared most often in ticket records?
4. How can weather, fine, and borough population data add context to the
   parking records?

## Key Findings

- The analysis contains 6,752,056 tickets dated from July 1, 2024 through
  June 30, 2025.
- October 2024 had the highest ticket volume among months with substantial
  source coverage, with 1,470,983 tickets.
- Violation code 36, photo school-zone speeding, was the most common violation
  with 2,186,706 tickets.
- Tuesday had the highest ticket volume at 1,137,301 records, while Sunday had
  the lowest at 641,048.
- Queens had the largest mapped borough total, followed by Manhattan and
  Brooklyn.
- Manhattan had the highest FY2025 population-adjusted rate at approximately
  1,099 issued violations per 1,000 residents.
- Toyota (`TOYOT`) was the most frequently recorded vehicle make, and model
  year 2023 was the most common plausible vehicle year.
- December 2024 through June 2025 contain very few records in the supplied
  source. Those months are documented but excluded from month-to-month
  interpretation.

These counts represent issued violations, not unique vehicles, drivers,
payments, or collected revenue. Fine totals are estimates based on the listed
schedule and should not be interpreted as actual collections.

The source does not include vehicle model. Vehicle analysis therefore uses
make, color, body type, and model year without attempting to infer a model.

## Project Structure

```text
nyc-parking-analytics/
  data/
    raw/                  Source datasets
    processed/            Cleaned parking CSV
    database/             Reproducible SQLite database
  notebooks/
    01_clean_nyc_parking_data.ipynb
    02_build_sqlite_database.ipynb
    03_recover_missing_boroughs.ipynb
    04_analyze_and_visualize.ipynb
  reports/
    ERD.md
    RUBRIC_AUDIT.md
  tests/                       Automated validation tests
  src/nycparking/
    core/                 Shared date-window helper
    geocoding/            Audited Geosupport borough recovery
    source_data.py        Verified GitHub Release downloader
    sqlite/               SQLite database builder
  clean_csv.py            Chunked parking-data cleaning script
  download_parking_data.py
  CAPSTONE_REQUIREMENTS.md
  CAPSTONE_GRADING_CHECKLIST.md
  requirements.txt
```

## Recovering Missing Boroughs with Geosupport

Run `notebooks/03_recover_missing_boroughs.ipynb` after notebooks 01 and 02. It is
a standalone, restart-safe workflow and does not depend on variables from
another notebook. The recovery order is:

1. preserve the original cleaned borough;
2. map official violation precinct/location values and validate street-code
   candidates with Geosupport;
3. resolve remaining repeated camera descriptions with exact known evidence,
   Function 2 intersections, Function 1N street names, and cross-street
   browsing;
4. apply `data/reference/manual_borough_lookup.csv` for reviewed descriptions;
5. combine approved results in SQLite and create `parking_analysis`.

Generated audit results are stored in `borough_geosupport_audit` and
`borough_description_audit`. Approved results are stored in
`borough_recovery`; remaining rows are available through the
`borough_unresolved` view. The workflow does not create separate ambiguous,
review, unmatched, accepted, and combined CSV files.

The notebook defaults to the installed Geosupport Desktop Python binding. On
Windows it auto-detects the normal per-user installation path. If Geosupport
is installed elsewhere, add the directory containing `Bin` and `Fls` to
`.env`:

```text
GEOSUPPORT_PATH=C:\Users\your_name\AppData\Local\Programs\Geosupport Desktop Edition
```

The remote Geoservice API remains available as a slower fallback with
`GEOSUPPORT_BACKEND=api`; it requires `GEOSERVICE_API_KEY` in `.env` and
caches responses in `data/processed/geosupport_cache.sqlite`. Never put the
real key in `.env.example`.

On the FY2025 source used for this project, the executed notebook reconciles
7,056,788 summons: 6,899,010 original boroughs, 157,364 recovered boroughs,
and 414 unresolved rows. All 7,056,788 summons remain in `parking_analysis`.

The weather, fine lookup, and Census extracts are small enough to keep in the
repository. The original parking CSV, cleaned CSV, and generated SQLite
database are excluded because each is approximately 1-1.5 GB. See
[data/README.md](data/README.md) for the complete inventory.

## Data Sources

| Dataset | Publisher | Project role | Join |
| --- | --- | --- | --- |
| [Parking Violations Issued - Fiscal Year 2025](https://data.cityofnewyork.us/City-Government/Parking-Violations-Issued-Fiscal-Year-2025/m5vz-tzqv) | NYC Department of Finance via NYC Open Data | Main fact dataset with individual tickets | Base table |
| [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) | Open-Meteo | Daily temperature, precipitation, wind, and weather condition | `issue_date = weather_date` |
| [Stipulated Fine and Fee Schedule](https://www.nyc.gov/assets/finance/downloads/pdf/tax_and_parking_program_operations/stipulated-fines-fee-schedule.pdf) | NYC Department of Finance | Violation descriptions and listed fine amounts | `violation_code` |
| [County Population Totals and Components of Change: 2020-2025](https://www.census.gov/data/tables/time-series/demo/popest/2020s-counties-total.html) | U.S. Census Bureau | Vintage 2025 population context for NYC counties/boroughs | normalized `borough` |

The joins add weather conditions by issue date, readable labels and listed
fine amounts by violation code, and population context for borough
comparisons. The SQLite `parking_enriched` view combines all four sources in
7,056,788 rows and 35 columns, well above the required 1,000 rows and 10
columns. The normalized 21-column parking fact table remains the source of
truth, so dimension values are not duplicated on disk. Of those view rows,
6,894,693 have non-null weather, violation-description, listed-fine, and
population fields from all four sources.

## Setup and Installation

Follow these instructions from a terminal opened at the repository root. The
repository root is the folder containing `README.md`, `requirements.txt`, and
`clean_csv.py`.

### 1. Prerequisites

Install the following before continuing:

- Python 3.11 or newer
- Git, if cloning the repository rather than downloading it
- At least 6 GB of free disk space for the 1.3 GB source CSV, cleaned CSV, and
  generated SQLite database
- An internet connection for the initial parking-data download and the Census
  refresh performed during the database build

Confirm that Python is available:

```text
python --version
```

On Windows, use `py --version` if `python` is not recognized.

### 2. Get the project and enter its directory

```text
git clone https://github.com/JaysonC41/parkinganalytics.git nyc-parking-analytics
cd nyc-parking-analytics
```

Skip the clone command if the repository is already on your computer, but make
sure the terminal is inside the project directory before running later steps.

### 3. Create and activate a virtual environment

The virtual environment keeps this project's packages separate from other
Python projects.

#### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
```

If PowerShell blocks the activation script, allow it for the current terminal
session and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

#### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export PYTHONPATH="$PWD/src"
```

After activation, the terminal prompt normally begins with `(.venv)`. The
`PYTHONPATH` command makes the package under `src/` importable. Run that command
again whenever a new terminal session is opened.

To leave the virtual environment on any operating system, run:

```text
deactivate
```

### 4. Download the required parking source

The three small supporting datasets are stored in `data/raw/`. The large
parking source is distributed as a compressed
[GitHub Release asset](https://github.com/JaysonC41/parkinganalytics/releases/tag/data-v1)
so it does not inflate normal Git history.

Download, verify, and extract it with:

```text
python download_parking_data.py
```

Notebook 01 runs the same downloader automatically when
`data/raw/nycparking2025.csv` is missing. The download is accepted only when
its SHA-256 checksum matches the value recorded in
`src/nycparking/source_data.py`.

The required input paths should now be:

```text
data/raw/nycparking2025.csv
data/raw/nyc_weather_daily.csv
data/raw/fines_extracted_fixed.csv
data/raw/nyc_census_borough.csv
```

Verify the large file on Windows PowerShell:

```powershell
Get-Item .\data\raw\nycparking2025.csv
```

Or on macOS and Linux:

```bash
ls -lh data/raw/nycparking2025.csv
```

The extracted parking CSV is 1,310,711,350 bytes (approximately 1.22 GiB).

### 5. Optional date configuration

The project already uses the default broad plausibility window of January 1,
2000 through December 31, 2025. No `.env` file is required for the standard
reproduction. To customize that cleaning window, copy `.env.example` to `.env`
and edit the two dates before cleaning the data:

```text
PARKING_MIN_ISSUE_DATE=2000-01-01
PARKING_MAX_ISSUE_DATE=2025-12-31
```

Notebook 04 applies the narrower official FY2025 analysis window regardless of
this broad cleaning window.

## Run and Reproduce the Project

Keep the virtual environment active and run each command from the repository
root.

### 1. Clean the parking CSV

```text
python download_parking_data.py
python clean_csv.py
```

The first command is safe to rerun and does nothing when the source already
exists. The cleaning command reads the source in chunks, standardizes fields,
removes invalid records and duplicate summons numbers, and creates:

```text
data/processed/parking_clean.csv
```

The current source produces 7,056,788 cleaned rows. Runtime varies by computer;
the script prints progress after every 100,000 source rows.

### 2. Build the SQLite database

Windows PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m nycparking.sqlite.build_database
```

macOS and Linux:

```bash
export PYTHONPATH="$PWD/src"
python -m nycparking.sqlite.build_database
```

The build downloads the current Census Vintage 2025 county extract, loads all
four datasets, creates tables and indexes, creates the 35-column
`parking_enriched` view, and runs relationship checks. It writes:

```text
data/database/nyc_parking.sqlite
```

A successful build ends with 7,056,788 parking rows, 35 enriched-view columns,
and zero foreign-key errors.

### 3. Open and run the notebooks

```text
jupyter notebook
```

If using VS Code instead, open the repository folder, open the notebook, click
the kernel name in the upper-right corner, and select the Python interpreter
inside `.venv`. You do not need to run the `jupyter notebook` command when VS
Code is managing the notebook session.

Open and run the notebooks in this order:

1. `notebooks/01_clean_nyc_parking_data.ipynb`
2. `notebooks/02_build_sqlite_database.ipynb`
3. `notebooks/03_recover_missing_boroughs.ipynb`
4. `notebooks/04_analyze_and_visualize.ipynb`

Use **Kernel > Restart Kernel and Run All Cells** for each notebook. Notebooks
01 and 02 create their generated outputs when missing and otherwise reuse them.
Notebook 03 reuses completed recovery audit tables when present; on a fresh
database it performs the documented Geosupport recovery workflow.

The final analysis and visualizations are in notebook 04. The relational design
and its reasoning are documented in [`reports/ERD.md`](reports/ERD.md).

### 4. Run the automated checks

With the virtual environment active and `PYTHONPATH` set as shown above, run:

```text
python -m pytest -q
```

The project currently contains 20 automated tests covering the verified source
download, Geosupport borough-validation helpers, and camera-description
recovery logic.

### Troubleshooting

- **Parking source download fails:** Confirm internet access and open the
  [`data-v1` release](https://github.com/JaysonC41/parkinganalytics/releases/tag/data-v1)
  to verify that `nycparking2025.csv.zip` is available.
- **Parking source checksum fails:** Delete the partial archive in `data/raw/`
  and rerun `python download_parking_data.py`. Do not bypass checksum
  verification.
- **`No module named nycparking`:** Confirm the virtual environment is active,
  return to the repository root, and set `PYTHONPATH` again using the command
  for your operating system.
- **`jupyter` is not recognized:** Reinstall the dependencies with
  `python -m pip install -r requirements.txt` while the virtual environment is
  active, then close and reactivate the environment.
- **Database build fails during the Census download:** Confirm internet access
  and rerun the build. The builder replaces the generated database each time.
- **Disk-space error:** Free at least 6 GB before running the cleaning and
  database-build steps.

## Database Design

`parking_violations` is the fact table. It connects to:

- `weather_daily` by `issue_date`
- `violation_lookup` by `violation_code`
- `census_borough` by `borough`

This design avoids repeating weather, fine, and population attributes across
millions of ticket rows. The database builder also creates indexes for the
fields used most often in joins and grouped analysis.

The `parking_enriched` SQL view uses three `LEFT JOIN` operations to provide a
combined analysis-ready dataset containing parking, weather, fine, and Census
fields. Notebook 02 validates the view's row and column count, displays a
15-column joined sample, and runs a four-source grouped query with a fiscal-year
filter, aggregation, `HAVING`, estimated fine exposure, and a
population-adjusted rate.

The database build validates row counts, unmatched dimension values, and
SQLite foreign keys. The current generated database reports zero foreign-key
errors.

## Requirement Coverage

The current repository covers the project requirements as follows:

- **Version control:** more than 10 command-line commits are present.
- **Data:** four meaningfully related sources combined in a 7,056,788-row,
  35-column SQL view.
- **Cleaning and EDA:** missing values, duplicate summons numbers, invalid
  dates, data types, borough normalization, derived date fields, grouped
  summaries, trends, and cross-variable comparisons.
- **SQLite and SQL:** one fact table, three dimensions, source metadata,
  documented ERD, indexes, validation queries, and three advanced analytical
  queries using joins, aggregation, a subquery, and `HAVING`.
- **Functions:** the SQLite builder alone contains 12 documented custom
  functions, exceeding the required three.
- **Visualizations:** line, bar, and heatmap charts, including a discrete
  year-by-year vehicle-model distribution, all with labels and written
  findings.
- **Storytelling:** four ordered notebooks explain cleaning, database design,
  borough recovery, analysis choices, limitations, and conclusions.

The detailed evidence matrix is available in
[`reports/RUBRIC_AUDIT.md`](reports/RUBRIC_AUDIT.md).



## Tools, Data Sources, and AI Assistance Declaration

This project uses Python, Pandas, SQLite, Jupyter Notebook, Matplotlib, Seaborn, Requests, and python-dotenv. Data sources are credited to the New York City Department of Finance, NYC Open Data, Open-Meteo, and the U.S. Census Bureau.

OpenAI ChatGPT and Codex were used for code review, debugging, editing, documentation support, and technical guidance. During development, the original parking-violations dataset exceeded 1 GB and required more memory than was practical to process as a single Pandas DataFrame. After the author encountered repeated memory and performance issues, ChatGPT demonstrated the general technique of reading and processing a large CSV file in smaller chunks.

The author studied that demonstration, applied the underlying concept to the project, and developed the project-specific functions used to clean, transform, deduplicate, and save the data incrementally. Although the final notebook code was written and adapted by the author rather than copied directly from an AI response, its design was informed by AI-assisted guidance. To maintain transparency and academic integrity, the author identifies this portion of the project as AI-assisted and conservatively cites the related code as AI-generated.

All analytical questions, data-cleaning decisions, transformations, validation procedures, interpretations, and final conclusions were drawn by the author. The author accepts full responsibility for the project’s accuracy, implementation, and final submitted work.
