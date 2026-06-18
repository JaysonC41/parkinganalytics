# Data Inventory

This project keeps source files in `data/raw/` and writes cleaned outputs to
`data/processed/`.

The original parking source, cleaned output, and generated SQLite database are
excluded from Git because they are approximately 1-1.5 GB each. The smaller
weather, fine lookup, and Census extracts are stored in the repository so a
reviewer only needs to download the main NYC parking file.

## Raw Files

| File | Rows | Columns | Purpose |
| --- | ---: | ---: | --- |
| `nycparking2025.csv` | 7,057,514 | 43 | Original NYC parking violations source file. This is the starting point for the cleaning notebook. |
| `nyc_weather_daily.csv` | 9,486 | 7 | Daily NYC weather data used to add weather context to parking violations by issue date. |
| `fines_extracted_fixed.csv` | 91 | 3 | Cleaned violation fine lookup used to enrich each parking violation code with a readable violation description and the fine amount. |
| `nyc_census_borough.csv` | 5 | 6 | Reproducible Census Vintage 2025 county population estimate extract for the five counties corresponding to NYC boroughs. |

## Source Strategy

Notebook 01 begins with `nycparking2025.csv`, shows the cleaning logic, and
explains how `data/processed/parking_clean.csv` is produced.

The SQLite analytical database combines the sources using:

- Parking violations joined to weather by `issue_date = weather_date`.
- Parking violations joined to fine lookup by `violation_code` so each ticket can be analyzed by violation meaning and fine amount.
- Census data joined by normalized borough/county.

The resulting `parking_violations` fact table has 7,056,788 rows and 21
columns. Its dimension joins add weather, fine, and population context without
duplicating those descriptive values in every ticket row.

## Fine Lookup Note

The original parking data includes a violation code and description, while
`fines_extracted_fixed.csv` supplies the listed amount used in the analysis.
It is loaded into the `violation_lookup` dimension and joined by
`violation_code`, which keeps descriptions and amounts out of the millions of
fact rows.

Fine exposure is an estimate based on the listed amount in the supplied
schedule. It does not represent actual payments, penalties, reductions, or
collected revenue.

## SQLite Output

The database builder creates `data/database/nyc_parking.sqlite`. The database
is excluded from Git because it is approximately 1.5 GB and can be reproduced
by running:

```powershell
python -m nycparking.sqlite.build_database
```

The database contains:

- `parking_violations`
- `weather_daily`
- `violation_lookup`
- `census_borough`
- `source_metadata`
