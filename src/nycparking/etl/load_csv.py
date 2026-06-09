from pathlib import Path

import pandas as pd

from nycparking.core.db import engine


DATA_FILE_CANDIDATES = [
    Path("data/raw/parking_fast.csv"),
    Path("data/raw/parking_clean.csv"),
]


def load_staging():
    print("Loading parking CSV")

    data_file = next((path for path in DATA_FILE_CANDIDATES if path.exists()), None)
    if data_file is None:
        candidates = ", ".join(str(path) for path in DATA_FILE_CANDIDATES)
        raise FileNotFoundError(f"Could not find any parking CSV. Checked: {candidates}")

    total_rows = 0
    first_chunk = True

    for chunk in pd.read_csv(data_file, low_memory=False, chunksize=100000):
        chunk.to_sql(
            "staging_parking",
            engine,
            if_exists="replace" if first_chunk else "append",
            index=False,
            chunksize=10000,
            method="multi",
        )
        total_rows += len(chunk)
        first_chunk = False
        print(f"Loaded {total_rows:,} rows")

    print(f"Loaded {total_rows:,} rows from {data_file}")
