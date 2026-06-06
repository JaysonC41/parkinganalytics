from pathlib import Path

import pandas as pd

from nycparking.core.db import engine


DATA_FILE = Path("data/raw/parking_clean.csv")


def load_staging():
    print("Loading parking CSV")

    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Could not find {DATA_FILE}")

    df = pd.read_csv(DATA_FILE, low_memory=False)

    df.to_sql(
        "staging_parking",
        engine,
        if_exists="replace",
        index=False,
        chunksize=10000,
    )

    print(f"Loaded {len(df):,} rows")
