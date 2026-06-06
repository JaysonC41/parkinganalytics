import os

import typer
from sqlalchemy import text

from nycparking.core.db import engine
from nycparking.etl.build_dim_weather import build_dim_weather
from nycparking.etl.build_fact_table import build_fact_table
from nycparking.etl.load_census import load_census
from nycparking.etl.load_csv import load_staging
from nycparking.etl.load_weather import load_weather

app = typer.Typer()


@app.command()
def init():
    print("Setting up NYC parking project")
    print("Project ready")


@app.command()
def etl_run():
    print("Running ETL process")

    load_census()
    load_weather()
    build_dim_weather()

    print("Warehouse refresh complete")


@app.command()
def load_csv():
    print("Loading parking CSV")
    load_staging()
    print("CSV load complete")


@app.command()
def build():
    print("Building fact table")
    build_fact_table()
    print("Fact table complete")


@app.command()
def db_test():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DATABASE()"))
        db_name = result.fetchone()

    print("Connected to:", db_name)


@app.command()
def dashboard():
    os.system("python -m nycparking.dashboard.app")


if __name__ == "__main__":
    app()
