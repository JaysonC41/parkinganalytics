from pathlib import Path

import pandas as pd

from nycparking.core.db import engine


WEATHER_FILE = Path("data/raw/nyc_weather_daily.csv")


def load_weather():
    print("Loading weather CSV")

    if not WEATHER_FILE.exists():
        raise FileNotFoundError(f"Could not find {WEATHER_FILE}")

    df = pd.read_csv(WEATHER_FILE, parse_dates=["weather_date"])

    df.to_sql(
        "staging_weather",
        engine,
        if_exists="replace",
        index=False,
        chunksize=5000,
        method="multi",
    )

    print(f"Loaded {len(df):,} weather records")
