from nycparking.etl.build_dim_tables import build_dim_tables
from nycparking.etl.build_dim_weather import build_dim_weather
from nycparking.etl.build_fact_table import build_fact_table, refresh_fact_weather_ids
from nycparking.etl.build_summary_tables import build_summary_tables
from nycparking.etl.init_schema import init_schema
from nycparking.etl.load_census import load_census
from nycparking.etl.load_csv import load_staging
from nycparking.etl.load_weather import load_weather


def run_pipeline():
    print("Starting ETL pipeline")

    init_schema()
    load_staging()
    load_weather()
    build_dim_weather()
    build_fact_table()
    refresh_fact_weather_ids()
    build_dim_tables()
    load_census()
    build_summary_tables()

    print("Pipeline complete")


if __name__ == "__main__":
    run_pipeline()
