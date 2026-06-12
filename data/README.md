# Data Inventory

This project uses raw source files in `data/raw/` and writes cleaned or analysis-ready outputs to `data/processed/`.

Large raw data files are intentionally excluded from Git. The notebook and scripts should document how to reproduce cleaned outputs from these files.

## Raw Files

| File | Rows | Columns | Purpose |
| --- | ---: | ---: | --- |
| `nycparking2025.csv` | 7,057,514 | 43 | Original NYC parking violations source file. This is the starting point for the cleaning notebook. |
| `nyc_weather_daily.csv` | 9,486 | 7 | Daily NYC weather data used to add weather context to parking violations by issue date. |
| `fines_extracted_fixed.csv` | 91 | 3 | Cleaned violation fine lookup used to enrich each parking violation code with a readable violation description and the fine amount. |
| `fines_extracted.csv` | 98 | 9 | Earlier extracted fine lookup source. This is kept for reproducibility but `fines_extracted_fixed.csv` is the analysis-ready version. |
| `nyc_census_borough.csv` | 5 | 6 | Reproducible 2020 Census population extract for the five counties corresponding to NYC boroughs. |

## Capstone Source Strategy

The main notebook should begin with `nycparking2025.csv`, show the cleaning logic, and explain how the cleaned parking dataset is produced in `data/processed/`.

The final analytical dataset should combine parking violations with at least one additional source. Recommended joins:

- Parking violations joined to weather by `issue_date = weather_date`.
- Parking violations joined to fine lookup by `violation_code` so each ticket can be analyzed by violation meaning and fine amount.
- Census data joined by borough/county once the final census source and location mapping are selected.

## Fine Lookup Note

The fine lookup is an important enrichment source. The original parking data has a violation code and a violation description, while `fines_extracted_fixed.csv` provides a cleaned lookup table for each code and the expected fine amount. In the final notebook and SQLite database, this should be represented either as:

- a `violation_lookup` dimension table joined to parking tickets by `violation_code`, or
- an analysis-ready joined table that includes `violation_description` and `fine_amount`.

Keeping the lookup as a separate table is preferred for the relational database because it avoids repeating the same violation description and fine amount millions of times.

The fine calculation is an estimate based on the listed amount in the supplied schedule. It does not represent actual payments, penalties, reductions, or collected revenue.

## SQLite Output

The database builder creates `data/database/nyc_parking.sqlite`. The database is excluded from Git because it is approximately 1.5 GB and can be reproduced by running:

```powershell
python -m nycparking.sqlite.build_database
```

The database contains:

- `parking_violations`
- `weather_daily`
- `violation_lookup`
- `census_borough`
- `source_metadata`
