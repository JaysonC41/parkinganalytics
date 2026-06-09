import subprocess
import sys

import typer
from sqlalchemy import text

from nycparking.core.db import engine
from nycparking.etl.build_dim_tables import build_dim_tables
from nycparking.etl.build_dim_weather import build_dim_weather
from nycparking.etl.build_fact_table import (
    build_fact_table,
    clean_fact_issue_dates,
    refresh_fact_weather_ids,
)
from nycparking.etl.build_summary_tables import build_summary_tables
from nycparking.etl.init_schema import init_schema
from nycparking.etl.load_census import load_census
from nycparking.etl.load_csv import load_staging
from nycparking.etl.load_weather import load_weather

app = typer.Typer()


@app.command()
def init():
    print("Setting up NYC parking project")
    init_schema()


@app.command()
def etl_run(
    reload_staging: bool = typer.Option(
        False,
        "--reload-staging",
        help="Reload the parking CSV into staging even when staging already has rows.",
    ),
    rebuild_fact: bool = typer.Option(
        False,
        "--rebuild-fact",
        help="Rebuild parking_violations even when the fact table already has rows.",
    ),
    link_weather_ids: bool = typer.Option(
        False,
        "--link-weather",
        help="Backfill parking_violations.weather_id for existing fact rows.",
    ),
):
    print("Running ETL process")

    init_schema()
    load_staging(force_reload=reload_staging)
    load_weather()
    build_dim_weather()
    build_fact_table(force_rebuild=rebuild_fact)
    clean_fact_issue_dates()
    if link_weather_ids:
        refresh_fact_weather_ids()
    build_dim_tables()
    load_census()
    build_summary_tables()

    print("Warehouse refresh complete")


@app.command()
def load_csv(
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace staging_parking even when it already has rows.",
    ),
):
    print("Loading parking CSV")
    init_schema()
    load_staging(force_reload=force)
    print("CSV load complete")


@app.command()
def build(
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace parking_violations even when it already has rows.",
    ),
):
    print("Building fact table")
    init_schema()
    build_fact_table(force_rebuild=force)
    clean_fact_issue_dates()
    print("Fact table complete")


@app.command()
def dimensions():
    print("Building dimension tables")
    init_schema()
    build_dim_weather()
    build_dim_tables()
    print("Dimension tables complete")


@app.command()
def link_weather():
    print("Linking facts to weather")
    refresh_fact_weather_ids()
    print("Weather links complete")


@app.command()
def clean_dates():
    print("Cleaning invalid fact dates")
    clean_fact_issue_dates()
    build_summary_tables()
    print("Invalid fact dates removed and summaries refreshed")


@app.command()
def summaries():
    print("Building summary tables")
    init_schema()
    build_summary_tables()
    print("Summary tables complete")


@app.command()
def db_test():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DATABASE()"))
        db_name = result.fetchone()

    print("Connected to:", db_name)


@app.command()
def dashboard():
    subprocess.run([sys.executable, "-m", "nycparking.dashboard.app"], check=True)


if __name__ == "__main__":
    app()
