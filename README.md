# Curbside Patterns: NYC Parking Analytics

An analysis of 6.75 million New York City parking violations issued during
fiscal year 2025. The project uses Pandas for data cleaning, SQLite for a
relational analytical database, and Matplotlib/Seaborn for exploratory
visualization.

The parking records are enriched with daily weather, violation descriptions
and listed fine amounts, and 2020 Census population data for the five boroughs.

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
- December 2024 through June 2025 contain very few records in the supplied
  source. Those months are documented but excluded from month-to-month
  interpretation.

These counts represent issued violations, not unique vehicles, drivers,
payments, or collected revenue. Fine totals are estimates based on the listed
schedule and should not be interpreted as actual collections.

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
  src/nycparking/
    sqlite/               SQLite database builder
  clean_csv.py            Chunked parking-data cleaning script
  requirements.txt
```

Large source, processed, and database files are excluded from Git because they
are approximately 1-1.5 GB each. See [data/README.md](data/README.md) for the
expected files and their roles.

## Data Sources

- [NYC Open Data: Parking Violations Issued - Fiscal Year 2025](https://data.cityofnewyork.us/City-Government/Parking-Violations-Issued-Fiscal-Year-2025/m5vz-tzqv),
  published by the New York City Department of Finance.
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api),
  used for daily New York City temperature, precipitation, wind, and weather
  conditions.
- [NYC Department of Finance Stipulated Fine and Fee Schedule](https://www.nyc.gov/assets/finance/downloads/pdf/tax_and_parking_program_operations/stipulated-fines-fee-schedule.pdf),
  used for violation descriptions and listed fine amounts.
- [2020 Decennial Census API](https://www.census.gov/data/developers/data-sets/decennial-census.html),
  published by the U.S. Census Bureau and used for county populations
  corresponding to the five NYC boroughs.

The joins are meaningful because parking issue dates match daily weather dates,
violation codes match the fine lookup, and normalized borough names match the
five Census county records.

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

1. Download the NYC parking CSV and place it at
   `data/raw/nycparking2025.csv`.
2. Add the weather and fine lookup files listed in
   [data/README.md](data/README.md).
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

The optional Census API key can be added to a local `.env` file:

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

## Tools and Acknowledgements

This project uses Python, Pandas, SQLite, Jupyter, Matplotlib, Seaborn, Plotly,
Dash, Requests, and python-dotenv. AI assistance from OpenAI ChatGPT and Codex
was used for code review, debugging, editing support, and documentation. The
analysis decisions, validation, and final project responsibility remain with
the author.
