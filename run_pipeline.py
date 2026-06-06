from nycparking.etl.build_dim_weather import build_dim_weather
from nycparking.etl.build_fact_table import build_fact_table
from nycparking.etl.load_census import load_census
from nycparking.etl.load_csv import load_staging
from nycparking.etl.load_weather import load_weather


def run_pipeline():
    print("Starting ETL pipeline")

    load_staging()
    build_fact_table()
    load_weather()
    load_census()
    build_dim_weather()

    print("Pipeline complete")


if __name__ == "__main__":
    run_pipeline()
