# NYC Parking Analytics Capstone Grading Checklist

This checklist translates the Code:You capstone requirements and rubric into concrete work for this project.

## Full Credit Targets

### 1. Version Control
- GitHub repository shows at least 10 separate commits.
- All commits are made through the command line.
- No file uploader commits.

Current status:
- The `main` branch contained 20 commits before this final update. Local commit
  metadata does not show GitHub's web-flow identity; the author should still
  be prepared to confirm that every commit was made from the command line.

Status:
- The minimum requirement of 10 command-line commits is met.

### 2. Data Sources
- Use at least 2 datasets.
- Datasets must be combined meaningfully.
- Combined dataset must have at least 1,000 rows and 10 columns.
- Sources must be credited with links.

Completed implementation:
- Main dataset: NYC parking violations, from `nycparking2025.csv`.
- Weather dataset: NYC daily weather, joined by ticket issue date.
- Fine lookup dataset: violation code lookup joined by `violation_code` to add violation meaning and fine amount.
- Census dataset: census population/demographic data, joined by NYC county/borough where possible.

Status:
- All four sources are credited in `README.md`, `data/README.md`, notebook 02,
  and the SQLite `source_metadata` table.
- Join keys and analytical purpose are documented.
- The `parking_enriched` SQL view combines all four sources in 7,056,788 rows
  and 35 columns; notebook 02 validates its shape and demonstrates a joined
  sample and four-source analytical query.

### 3. Data Cleaning & EDA
- Use Pandas.
- Handle missing values.
- Handle duplicates.
- Handle data types.
- Perform transformations.
- Include at least 3 EDA techniques with insights.

Completed implementation:
- Clean dates, numeric IDs, violation codes, precincts, vehicle year, and missing values.
- Remove invalid issue dates and duplicate summons numbers.
- Create useful derived fields such as year, month, day of week, borough/county mapping, and weather category.
- Use EDA techniques such as summary statistics, grouped counts, missing-value analysis, trend analysis, and correlation/comparison views.

### 4. Databases & SQL
- Design and justify a relational schema.
- Include an ERD.
- Build the database in SQLite3 using Python.
- Include at least 3 intermediate or advanced SQL queries.

Completed implementation:
- The final workflow builds SQLite3 with Python.
- `parking_violations`
- `weather_daily`
- `violation_lookup`
- `census_borough`
- `source_metadata`
- `parking_enriched` combined SQL view
- Notebook 02 includes four intermediate/advanced queries covering weather,
  fine exposure, population-adjusted rates, and a direct four-table join.
- The queries demonstrate aggregation, `HAVING`, a subquery, and multi-table
  joins.

### 5. Functions
- Include at least 3 unique custom Python functions.
- Each function must serve a clear purpose.
- Functions should be documented with useful comments.

Completed implementation:
- Load raw parking data in chunks.
- Clean and normalize parking columns.
- Build or connect to the SQLite database.
- Load DataFrames into SQLite tables.
- Run reusable SQL queries or generate chart-ready summaries.
- The SQLite builder contains 12 documented functions, and notebook 01 adds
  documented cleaning and profiling functions.

### 6. Visualizations
- Include at least 3 different chart types.
- Visuals must be clear, labeled, relevant, and help tell a story.

Completed implementation:
- Line chart: parking tickets over time.
- Bar chart: top violation types or precincts.
- Heatmaps: month/day-of-week patterns and vehicle make/color comparisons.
- Filled line distribution: plausible vehicle model years.

### 7. Storytelling & Notebook Quality
- Markdown explains reasoning and conclusions.
- Comments are useful.
- Notebook is organized.
- No typos or sloppy formatting.
- Unnecessary/repetitive code is removed.

Completed implementation:
- Three ordered notebooks walk through cleaning, SQLite design and SQL, then
  exploratory analysis, visualizations, and conclusions.

### 8. Repo & README
- Professional `README.md`.
- Include `requirements.txt`.
- Include data files or scripts to reproduce data.
- Use relative paths.
- README includes title, setup instructions, data source links, questions, findings, and tool acknowledgements.

Completed implementation:
- `README.md` uses the unique title "Curbside Patterns: NYC Parking Analytics."
- Setup and environment instructions cover Windows, macOS, and Linux.
- Libraries, publishers, source links, and AI assistance are acknowledged.

## Recommended Analysis Questions

1. How do NYC parking violations change over time by month and day of week?
2. Which violation types and precincts account for the most tickets?
3. Are certain weather conditions associated with higher or lower ticket volume?
4. Which violation types create the largest estimated fine exposure?
5. How do ticket counts compare across boroughs/counties when population context is added?
6. Which combinations of location, violation type, and weather create the highest ticket activity?

## Recommended Final Project Structure

```text
nyc-parking-analytics/
  data/
    raw/
    processed/
  notebooks/
    01_clean_nyc_parking_data.ipynb
    02_build_sqlite_database.ipynb
    03_analyze_and_visualize.ipynb
  reports/
    ERD.md
    RUBRIC_AUDIT.md
  src/
    nycparking/
      ...
  CAPSTONE_REQUIREMENTS.md
  CAPSTONE_GRADING_CHECKLIST.md
  README.md
  requirements.txt
```

## Final Submission Check

1. Run all three notebooks in order from a clean kernel.
2. Confirm notebook 02 reports 7,056,788 rows and 35 columns for
   `parking_enriched`.
3. Confirm the GitHub default branch is `main` and contains these final files.
4. Commit and push the final validated changes from the command line.
5. Open the repository URL in a private browser window to verify that the
   README, notebooks, ERD, and source links are visible.
