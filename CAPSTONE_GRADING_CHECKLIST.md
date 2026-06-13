# NYC Parking Analytics Capstone Grading Checklist

This checklist translates the Code:You capstone requirements and rubric into concrete work for this project.

## Full Credit Targets

### 1. Version Control
- GitHub repository shows at least 10 separate commits.
- All commits are made through the command line.
- No file uploader commits.

Current status:
- 11 commits currently exist.

Status:
- The minimum requirement of 10 command-line commits is met.

### 2. Data Sources
- Use at least 2 datasets.
- Datasets must be combined meaningfully.
- Combined dataset must have at least 1,000 rows and 10 columns.
- Sources must be credited with links.

Project target:
- Main dataset: NYC parking violations, from `nycparking2025.csv`.
- Weather dataset: NYC daily weather, joined by ticket issue date.
- Fine lookup dataset: violation code lookup joined by `violation_code` to add violation meaning and fine amount.
- Census dataset: census population/demographic data, joined by NYC county/borough where possible.

Action needed:
- Document all sources in `README.md` and notebook markdown.
- Clearly explain why each join is meaningful.

### 3. Data Cleaning & EDA
- Use Pandas.
- Handle missing values.
- Handle duplicates.
- Handle data types.
- Perform transformations.
- Include at least 3 EDA techniques with insights.

Project target:
- Clean dates, numeric IDs, violation codes, precincts, vehicle year, and missing values.
- Remove invalid issue dates and duplicate summons numbers.
- Create useful derived fields such as year, month, day of week, borough/county mapping, and weather category.
- Use EDA techniques such as summary statistics, grouped counts, missing-value analysis, trend analysis, and correlation/comparison views.

### 4. Databases & SQL
- Design and justify a relational schema.
- Include an ERD.
- Build the database in SQLite3 using Python.
- Include at least 3 intermediate or advanced SQL queries.

Important project adjustment:
- Current project uses MySQL/PyMySQL. Final capstone should include a SQLite3 workflow because the rubric specifically requires SQLite3.

Project target tables:
- `parking_violations`
- `weather_daily`
- `violation_lookup`
- `census_county`
- `violation_summary` or other summary tables if useful

SQL query targets:
- Join parking violations to weather by issue date and group by weather condition.
- Join parking violations to violation lookup by violation code and estimate fine exposure by violation type.
- Join parking violations to census/borough data and calculate ticket rates or contextual counts.
- Use aggregation, HAVING, subqueries, and/or multi-table joins to answer analysis questions.

### 5. Functions
- Include at least 3 unique custom Python functions.
- Each function must serve a clear purpose.
- Functions should be documented with useful comments.

Project target functions:
- Load raw parking data in chunks.
- Clean and normalize parking columns.
- Build or connect to the SQLite database.
- Load DataFrames into SQLite tables.
- Run reusable SQL queries or generate chart-ready summaries.

### 6. Visualizations
- Include at least 3 different chart types.
- Visuals must be clear, labeled, relevant, and help tell a story.

Project target visuals:
- Line chart: parking tickets over time.
- Bar chart: top violation types or precincts.
- Heatmap or grouped bar chart: violations by weather condition, borough, month, or day of week.
- Optional map-style or scatter plot if useful.

### 7. Storytelling & Notebook Quality
- Markdown explains reasoning and conclusions.
- Comments are useful.
- Notebook is organized.
- No typos or sloppy formatting.
- Unnecessary/repetitive code is removed.

Project target:
- Create a main Jupyter notebook that walks from raw data to cleaned data, joins, SQLite load, SQL analysis, visualizations, and conclusions.

### 8. Repo & README
- Professional `README.md`.
- Include `requirements.txt`.
- Include data files or scripts to reproduce data.
- Use relative paths.
- README includes title, setup instructions, data source links, questions, findings, and tool acknowledgements.

Project target:
- Add a polished README with a unique title that does not include "capstone" or "Code:You".
- Add setup instructions for Windows, macOS, and Linux.
- Credit Python libraries, data sources, and AI assistance.

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
    nyc_parking_analysis.ipynb
  reports/
    erd.png
  src/
    nycparking/
      ...
  CAPSTONE_REQUIREMENTS.md
  CAPSTONE_GRADING_CHECKLIST.md
  README.md
  requirements.txt
```

## Priority Build Order

1. Create the main Jupyter notebook.
2. Import and clean `nycparking2025.csv` with clear markdown reasoning.
3. Add weather and census joins.
4. Build a SQLite3 database from Python.
5. Add 3 advanced SQL queries.
6. Add 3 or more visualizations with findings.
7. Create ERD.
8. Write README.
9. Make remaining command-line Git commits.
