from pathlib import Path

import pandas as pd

from nycparking.core.db import engine
from nycparking.core.db_utils import table_has_rows
from nycparking.core.date_window import issue_date_window


DATA_FILE_CANDIDATES = [
    Path("data/raw/parking_fast.csv"),
    Path("data/raw/parking_clean.csv"),
]


def load_staging(force_reload: bool = False):
    print("Loading parking CSV")

    if table_has_rows("staging_parking") and not force_reload:
        print(
            "staging_parking already has rows; "
            "skipping CSV load. Use force reload to replace it."
        )
        return

    data_file = next((path for path in DATA_FILE_CANDIDATES if path.exists()), None)
    if data_file is None:
        candidates = ", ".join(str(path) for path in DATA_FILE_CANDIDATES)
        raise FileNotFoundError(f"Could not find any parking CSV. Checked: {candidates}")

    total_rows = 0
    skipped_rows = 0
    first_chunk = True
    min_issue_date, max_issue_date = issue_date_window()
    print(f"Keeping issue dates from {min_issue_date} through {max_issue_date}")

    for chunk in pd.read_csv(data_file, low_memory=False, chunksize=100000):
        issue_dates = pd.to_datetime(chunk["issue_date"], errors="coerce")
        keep = issue_dates.between(min_issue_date, max_issue_date)
        skipped_rows += int((~keep).sum())
        chunk = chunk.loc[keep].copy()
        chunk["issue_date"] = issue_dates.loc[keep].dt.strftime("%Y-%m-%d")
        if chunk.empty:
            continue

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
    if skipped_rows:
        print(f"Skipped {skipped_rows:,} rows outside the issue-date window")
