import subprocess
import sys

import typer
from sqlalchemy import text

from nycparking.core.db import engine
from nycparking.etl.build_dim_tables import build_dim_tables
from nycparking.etl.build_dim_weather import build_dim_weather
from nycparking.etl.build_fact_table import build_fact_table, refresh_fact_weather_ids
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
def etl_run():
    print("Running ETL process")

    init_schema()
    load_staging()
    load_weather()
    build_dim_weather()
    build_fact_table()
    refresh_fact_weather_ids()
    build_dim_tables()
    load_census()
    build_summary_tables()

    print("Warehouse refresh complete")


@app.command()
def load_csv():
    print("Loading parking CSV")
    init_schema()
    load_staging()
    print("CSV load complete")


@app.command()
def build():
    print("Building fact table")
    init_schema()
    build_fact_table()
    refresh_fact_weather_ids()
    print("Fact table complete")


@app.command()
def dimensions():
    print("Building dimension tables")
    init_schema()
    build_dim_weather()
    refresh_fact_weather_ids()
    build_dim_tables()
    print("Dimension tables complete")


@app.command()
def link_weather():
    print("Linking facts to weather")
    refresh_fact_weather_ids()
    print("Weather links complete")


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
