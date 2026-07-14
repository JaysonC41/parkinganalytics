# NYC Parking Analytics Entity Relationship Diagram

The SQLite database uses one main fact table and three dimension tables.
It also exposes a read-only `parking_enriched` view that joins the fact table
to all three dimensions for rubric-ready combined analysis.

```mermaid
erDiagram
    WEATHER_DAILY ||--o{ PARKING_VIOLATIONS : "weather_date = issue_date"
    VIOLATION_LOOKUP ||--o{ PARKING_VIOLATIONS : "violation_code"
    CENSUS_BOROUGH ||--o{ PARKING_VIOLATIONS : "borough"

    WEATHER_DAILY {
        TEXT weather_date PK
        INTEGER weather_code
        REAL temperature_max
        REAL temperature_min
        REAL precipitation
        REAL wind_speed_max
        TEXT weather_condition
    }

    VIOLATION_LOOKUP {
        INTEGER violation_code PK
        TEXT violation_description
        REAL fine_amount
        TEXT fine_note
    }

    CENSUS_BOROUGH {
        TEXT borough PK
        TEXT county_name
        INTEGER population
        TEXT state_fips
        TEXT county_fips UK
        INTEGER census_year
    }

    PARKING_VIOLATIONS {
        INTEGER summons_number PK
        TEXT plate_id
        TEXT issue_date FK
        INTEGER violation_code FK
        INTEGER violation_precinct
        INTEGER issuer_precinct
        TEXT borough FK
        TEXT street_name
        INTEGER vehicle_year
        INTEGER issue_year
        INTEGER issue_month
        INTEGER issue_day_of_week
    }
```

## Design Notes

- `parking_violations` is the fact table because each row represents one issued ticket.
- `weather_daily` contains one row per date. Parking records join to it through `issue_date`.
- `violation_lookup` contains one row per violation code. It prevents descriptions and fine amounts from being repeated millions of times.
- `census_borough` contains one row per NYC borough/county. It adds population context and allows ticket counts to be compared as rates.
- `summons_number` is the parking table primary key because it identifies an individual ticket.
- Foreign keys protect the relationships between parking records and the three dimensions.
- `parking_enriched` uses `LEFT JOIN` operations across all four analytical
  datasets and provides 35 columns without storing duplicate dimension values.
