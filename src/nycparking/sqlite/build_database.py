from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import requests
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PARKING_FILE = PROJECT_ROOT / "data" / "processed" / "parking_clean.csv"
WEATHER_FILE = PROJECT_ROOT / "data" / "raw" / "nyc_weather_daily.csv"
FINE_FILE = PROJECT_ROOT / "data" / "raw" / "fines_extracted_fixed.csv"
CENSUS_FILE = PROJECT_ROOT / "data" / "raw" / "nyc_census_borough.csv"
DATABASE_FILE = PROJECT_ROOT / "data" / "database" / "nyc_parking.sqlite"
PARKING_READ_CHUNKSIZE = 100_000
SQL_INSERT_CHUNKSIZE = 1_000

CENSUS_URL = "https://api.census.gov/data/2020/dec/pl"
NYC_COUNTIES = {
    "005": "Bronx",
    "047": "Brooklyn",
    "061": "Manhattan",
    "081": "Queens",
    "085": "Staten Island",
}

PARKING_COLUMNS = [
    "summons_number",
    "plate_id",
    "registration_state",
    "plate_type",
    "issue_date",
    "violation_code",
    "vehicle_body_type",
    "vehicle_make",
    "issuing_agency",
    "violation_precinct",
    "issuer_precinct",
    "violation_time",
    "violation_county",
    "borough",
    "street_name",
    "vehicle_color",
    "vehicle_year",
    "issue_year",
    "issue_month",
    "issue_day_of_week",
    "issue_day_name",
]


def connect_database(database_path: Path = DATABASE_FILE) -> sqlite3.Connection:
    """Open the output database with pragmas that speed the bulk load."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA temp_store = MEMORY")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the fact table, dimensions, and source metadata table."""
    connection.executescript(
        """
        CREATE TABLE source_metadata (
            source_name TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE weather_daily (
            weather_date TEXT PRIMARY KEY,
            weather_code INTEGER,
            temperature_max REAL,
            temperature_min REAL,
            precipitation REAL,
            wind_speed_max REAL,
            weather_condition TEXT
        );

        CREATE TABLE violation_lookup (
            violation_code INTEGER PRIMARY KEY,
            violation_description TEXT,
            fine_amount REAL,
            fine_note TEXT
        );

        CREATE TABLE census_borough (
            borough TEXT PRIMARY KEY,
            county_name TEXT NOT NULL,
            population INTEGER NOT NULL,
            state_fips TEXT NOT NULL,
            county_fips TEXT NOT NULL UNIQUE,
            census_year INTEGER NOT NULL
        );

        CREATE TABLE parking_violations (
            summons_number INTEGER PRIMARY KEY,
            plate_id TEXT,
            registration_state TEXT,
            plate_type TEXT,
            issue_date TEXT NOT NULL,
            violation_code INTEGER,
            vehicle_body_type TEXT,
            vehicle_make TEXT,
            issuing_agency TEXT,
            violation_precinct INTEGER,
            issuer_precinct INTEGER,
            violation_time TEXT,
            violation_county TEXT,
            borough TEXT,
            street_name TEXT,
            vehicle_color TEXT,
            vehicle_year INTEGER,
            issue_year INTEGER,
            issue_month INTEGER,
            issue_day_of_week INTEGER,
            issue_day_name TEXT,
            FOREIGN KEY (issue_date) REFERENCES weather_daily(weather_date),
            FOREIGN KEY (violation_code) REFERENCES violation_lookup(violation_code),
            FOREIGN KEY (borough) REFERENCES census_borough(borough)
        );
        """
    )
    connection.commit()


def load_source_metadata(connection: sqlite3.Connection) -> None:
    """Record source links in the database itself."""
    rows = [
        (
            "NYC Parking Violations",
            "https://data.cityofnewyork.us/City-Government/Parking-Violations-Issued-Fiscal-Year-2025/m5vz-tzqv",
            "Individual parking violation records issued during New York City fiscal year 2025.",
        ),
        (
            "NYC Daily Weather",
            "https://open-meteo.com/en/docs/historical-weather-api",
            "Daily temperature, precipitation, wind, weather code, and condition data for New York City.",
        ),
        (
            "NYC Parking Fines",
            "https://www.nyc.gov/assets/finance/downloads/pdf/tax_and_parking_program_operations/stipulated-fines-fee-schedule.pdf",
            "Violation descriptions and listed fine amounts from the supplied NYC stipulated-fine schedule.",
        ),
        (
            "2020 Decennial Census",
            "https://www.census.gov/data/developers/data-sets/decennial-census.html",
            "2020 Census population totals for the five counties corresponding to New York City boroughs.",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO source_metadata (source_name, source_url, description)
        VALUES (?, ?, ?)
        """,
        rows,
    )
    connection.commit()


def load_weather(connection: sqlite3.Connection) -> int:
    """Load one weather row per calendar date."""
    weather = pd.read_csv(WEATHER_FILE)
    weather = weather.rename(
        columns={
            "weather_date": "weather_date",
            "temperature_2m_max": "temperature_max",
            "temperature_2m_min": "temperature_min",
            "precipitation_sum": "precipitation",
            "wind_speed_10m_max": "wind_speed_max",
        }
    )
    weather["weather_date"] = pd.to_datetime(
        weather["weather_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    weather = weather.dropna(subset=["weather_date"])
    weather = weather.drop_duplicates(subset=["weather_date"], keep="first")
    weather = weather[
        [
            "weather_date",
            "weather_code",
            "temperature_max",
            "temperature_min",
            "precipitation",
            "wind_speed_max",
            "weather_condition",
        ]
    ]
    weather.to_sql("weather_daily", connection, if_exists="append", index=False)
    connection.commit()
    return len(weather)


def collect_parking_violation_descriptions() -> dict[int, str]:
    """Read the cleaned parking file for descriptions missing from the fine table."""
    descriptions: dict[int, str] = {}
    for chunk in pd.read_csv(
        PARKING_FILE,
        usecols=["violation_code", "violation_description"],
        dtype="string",
        chunksize=500_000,
    ):
        chunk["violation_code"] = pd.to_numeric(
            chunk["violation_code"], errors="coerce"
        )
        valid = chunk.dropna(subset=["violation_code"])
        for code, description in valid.itertuples(index=False):
            numeric_code = int(code)
            cleaned_description = (
                str(description).strip() if pd.notna(description) else ""
            )
            if numeric_code not in descriptions:
                descriptions[numeric_code] = cleaned_description
            elif not descriptions[numeric_code] and cleaned_description:
                descriptions[numeric_code] = cleaned_description
    return descriptions


def load_violation_lookup(connection: sqlite3.Connection) -> int:
    """Load fine amounts and keep unfined parking codes available for joins."""
    fines = pd.read_csv(FINE_FILE, dtype="string")
    fines = fines.rename(
        columns={
            "Violation ": "violation_code",
            "Violation Description": "violation_description",
            "Fine Amount": "fine_text",
        }
    )
    fines["violation_code"] = pd.to_numeric(
        fines["violation_code"], errors="coerce"
    )
    fines = fines.dropna(subset=["violation_code"])
    fines["violation_code"] = fines["violation_code"].astype(int)
    fines["fine_text"] = fines["fine_text"].str.strip()
    fine_numbers = fines["fine_text"].str.replace("$", "", regex=False)
    fine_numbers = fine_numbers.str.replace(",", "", regex=False)
    fines["fine_amount"] = pd.to_numeric(fine_numbers, errors="coerce")
    fines["fine_note"] = fines["fine_text"].where(fines["fine_amount"].isna())
    fines = fines.drop_duplicates(subset=["violation_code"], keep="first")

    parking_descriptions = collect_parking_violation_descriptions()
    existing_codes = set(fines["violation_code"])
    missing_rows = [
        {
            "violation_code": code,
            "violation_description": description or "Description unavailable",
            "fine_amount": None,
            "fine_note": "Not listed in source fine schedule",
        }
        for code, description in sorted(parking_descriptions.items())
        if code not in existing_codes
    ]
    if missing_rows:
        fines = pd.concat([fines, pd.DataFrame(missing_rows)], ignore_index=True)

    fines["source_description"] = fines["violation_code"].map(parking_descriptions)
    fines["violation_description"] = fines["violation_description"].fillna(
        fines["source_description"]
    )
    fines = fines[
        ["violation_code", "violation_description", "fine_amount", "fine_note"]
    ].sort_values("violation_code")
    fines.to_sql("violation_lookup", connection, if_exists="append", index=False)
    connection.commit()
    return len(fines)


def fetch_census_data() -> pd.DataFrame:
    """Download 2020 population totals for NYC's five counties."""
    settings = dotenv_values(PROJECT_ROOT / ".env")
    api_key = os.environ.get("CENSUS_API_KEY") or settings.get("CENSUS_API_KEY")
    params = {
        "get": "NAME,P1_001N",
        "for": "county:*",
        "in": "state:36",
    }
    if api_key:
        params["key"] = api_key

    response = requests.get(CENSUS_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    census = pd.DataFrame(payload[1:], columns=payload[0])
    census = census[census["county"].isin(NYC_COUNTIES)].copy()
    census["borough"] = census["county"].map(NYC_COUNTIES)
    census["population"] = pd.to_numeric(census["P1_001N"], errors="raise")
    census["census_year"] = 2020
    census = census.rename(
        columns={
            "NAME": "county_name",
            "state": "state_fips",
            "county": "county_fips",
        }
    )
    return census[
        [
            "borough",
            "county_name",
            "population",
            "state_fips",
            "county_fips",
            "census_year",
        ]
    ].sort_values("borough")


def load_census(connection: sqlite3.Connection) -> int:
    """Refresh the borough Census extract and load it as a dimension."""
    census = fetch_census_data()
    census.to_csv(CENSUS_FILE, index=False)
    census.to_sql("census_borough", connection, if_exists="append", index=False)
    connection.commit()
    return len(census)


def load_parking(
    connection: sqlite3.Connection, chunksize: int = PARKING_READ_CHUNKSIZE
) -> int:
    """Stream the cleaned parking CSV into the fact table."""
    total_rows = 0
    for chunk_number, chunk in enumerate(
        pd.read_csv(
            PARKING_FILE,
            usecols=PARKING_COLUMNS,
            dtype="string",
            chunksize=chunksize,
        ),
        start=1,
    ):
        integer_columns = [
            "summons_number",
            "violation_code",
            "violation_precinct",
            "issuer_precinct",
            "vehicle_year",
            "issue_year",
            "issue_month",
            "issue_day_of_week",
        ]
        for column in integer_columns:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce").astype(
                "Int64"
            )

        chunk.to_sql(
            "parking_violations",
            connection,
            if_exists="append",
            index=False,
            chunksize=SQL_INSERT_CHUNKSIZE,
            method="multi",
        )
        connection.commit()
        total_rows += len(chunk)
        print(f"Loaded parking chunk {chunk_number}: {total_rows:,} rows")
    return total_rows


def create_indexes(connection: sqlite3.Connection) -> None:
    """Create the indexes used by notebook joins and grouped queries."""
    connection.executescript(
        """
        CREATE INDEX idx_parking_issue_date
            ON parking_violations(issue_date);
        CREATE INDEX idx_parking_violation_code
            ON parking_violations(violation_code);
        CREATE INDEX idx_parking_borough
            ON parking_violations(borough);
        CREATE INDEX idx_parking_precinct
            ON parking_violations(violation_precinct);
        CREATE INDEX idx_parking_borough_date
            ON parking_violations(borough, issue_date);
        """
    )
    connection.commit()


def validation_results(connection: sqlite3.Connection) -> dict[str, int]:
    """Run the row-count and relationship checks printed to the build log."""
    checks = {
        "parking_rows": "SELECT COUNT(*) FROM parking_violations",
        "weather_rows": "SELECT COUNT(*) FROM weather_daily",
        "violation_lookup_rows": "SELECT COUNT(*) FROM violation_lookup",
        "census_rows": "SELECT COUNT(*) FROM census_borough",
        "parking_without_weather": """
            SELECT COUNT(*)
            FROM parking_violations AS p
            LEFT JOIN weather_daily AS w
                ON w.weather_date = p.issue_date
            WHERE w.weather_date IS NULL
        """,
        "parking_without_violation_lookup": """
            SELECT COUNT(*)
            FROM parking_violations AS p
            LEFT JOIN violation_lookup AS v
                ON v.violation_code = p.violation_code
            WHERE p.violation_code IS NOT NULL
              AND v.violation_code IS NULL
        """,
        "parking_without_census": """
            SELECT COUNT(*)
            FROM parking_violations AS p
            LEFT JOIN census_borough AS c
                ON c.borough = p.borough
            WHERE p.borough IS NOT NULL
              AND c.borough IS NULL
        """,
        "foreign_key_errors": "SELECT COUNT(*) FROM pragma_foreign_key_check",
    }
    return {
        name: int(connection.execute(query).fetchone()[0])
        for name, query in checks.items()
    }


def build_database(database_path: Path = DATABASE_FILE) -> dict[str, int]:
    """Rebuild the SQLite file from the cleaned project inputs."""
    required_files = [PARKING_FILE, WEATHER_FILE, FINE_FILE]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required files: " + ", ".join(missing))

    for database_file in [
        database_path,
        database_path.with_name(database_path.name + "-shm"),
        database_path.with_name(database_path.name + "-wal"),
    ]:
        if database_file.exists():
            database_file.unlink()

    connection = connect_database(database_path)
    try:
        create_schema(connection)
        load_source_metadata(connection)
        print(f"Loaded weather rows: {load_weather(connection):,}")
        print(f"Loaded violation lookup rows: {load_violation_lookup(connection):,}")
        print(f"Loaded census rows: {load_census(connection):,}")
        print(f"Loaded parking rows: {load_parking(connection):,}")
        create_indexes(connection)
        results = validation_results(connection)
    finally:
        connection.close()

    print(f"SQLite database created at {database_path}")
    for name, value in results.items():
        print(f"{name}: {value:,}")
    return results


if __name__ == "__main__":
    build_database()
