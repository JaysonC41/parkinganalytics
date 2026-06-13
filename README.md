# Curbside Patterns: NYC Parking Analytics

Curbside Patterns is an end-to-end analysis of more than 7 million New York
City parking violation records. It uses Pandas to clean a 1.3 GB source file,
Python and SQLite to build a relational analytical database, SQL to combine
four datasets, and Matplotlib/Seaborn to communicate the results.

The parking records are enriched with daily weather, violation descriptions
and listed fine amounts, and 2020 Census population data for the five boroughs.
The workflow is designed to be reproducible without committing generated
gigabyte-scale files to Git.

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
- Manhattan had the highest population-adjusted rate at approximately 1,097
  tickets per 1,000 residents in the full cleaned database.
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
    03_analyze_and_visualize.ipynb
  reports/
    ERD.md
    RUBRIC_AUDIT.md
  src/nycparking/
    sqlite/               SQLite database builder
  clean_csv.py            Chunked parking-data cleaning script
  requirements.txt
```

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
| [2020 Decennial Census API](https://www.census.gov/data/developers/data-sets/decennial-census.html) | U.S. Census Bureau | Population context for NYC counties/boroughs | normalized `borough` |

These joins are meaningful because they add conditions on the issue date,
meaning and listed cost to each violation code, and population context to
borough comparisons. The SQLite fact table contains 7,056,788 rows and 21
columns, comfortably exceeding the required 1,000 rows and 10 columns.

## Setup

Python 3.10 or newer is recommended.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
```

Deactivate the environment with:

```powershell
deactivate
```

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export PYTHONPATH="$PWD/src"
```

Deactivate the environment with:

```bash
deactivate
```

## Reproduce the Project

1. Download the NYC parking CSV from NYC Open Data and place it at
   `data/raw/nycparking2025.csv`. The smaller weather, fine, and Census inputs
   are included in `data/raw/`.
2. Activate the virtual environment and set `PYTHONPATH` as shown above.
3. Clean the parking source:

```bash
python clean_csv.py
```

4. Build the SQLite database:

```bash
python -m nycparking.sqlite.build_database
```

5. Start Jupyter and run the notebooks in order:

```bash
jupyter notebook
```

The final analysis is in
[`notebooks/03_analyze_and_visualize.ipynb`](notebooks/03_analyze_and_visualize.ipynb).
It includes a line chart, horizontal bar chart, heatmap, and additional vehicle
profile visualizations. The relational design and its reasoning are documented
in [`reports/ERD.md`](reports/ERD.md).

The database build refreshes the Census extract from the Census API. An
optional API key can be added to a local `.env` file:

```text
CENSUS_API_KEY=your_key_here
```

The Census endpoint can also be used without a key for this small request.

## Database Design

`parking_violations` is the fact table. It connects to:

- `weather_daily` by `issue_date`
- `violation_lookup` by `violation_code`
- `census_borough` by `borough`

This design avoids repeating weather, fine, and population attributes across
millions of ticket rows. The database builder also creates indexes for the
fields used most often in joins and grouped analysis.

The database build validates row counts, unmatched dimension values, and
SQLite foreign keys. The current generated database reports zero foreign-key
errors.

## Requirement Coverage

The project deliberately goes beyond the minimum technical requirements:

- **Version control:** 13 command-line commits are present; 10 are required.
- **Data:** four meaningfully related sources and more than 7 million rows.
- **Cleaning and EDA:** missing values, duplicate summons numbers, invalid
  dates, data types, borough normalization, derived date fields, grouped
  summaries, trends, and cross-variable comparisons.
- **SQLite and SQL:** one fact table, three dimensions, source metadata,
  documented ERD, indexes, validation queries, and three advanced analytical
  queries using joins, aggregation, a subquery, and `HAVING`.
- **Functions:** the SQLite builder alone contains 12 documented custom
  functions, exceeding the required three.
- **Visualizations:** line, bar, heatmap, and filled distribution charts, all
  with labels and written findings.
- **Storytelling:** three ordered notebooks explain cleaning, database design,
  analysis choices, limitations, and conclusions.

The detailed evidence matrix is available in
[`reports/RUBRIC_AUDIT.md`](reports/RUBRIC_AUDIT.md).

## Tools and Acknowledgements

This project uses Python, Pandas, SQLite, Jupyter, Matplotlib, Seaborn, Plotly,
Dash, Requests, SQLAlchemy, PyMySQL, Typer, and python-dotenv. Data is credited
to the NYC Department of Finance, NYC Open Data, Open-Meteo, and the U.S.
Census Bureau. AI assistance from OpenAI ChatGPT and Codex was used for code
review, debugging, editing support, and documentation. The analysis decisions,
validation, and final project responsibility remain with the author.
