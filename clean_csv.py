import pandas as pd
from pathlib import Path


RAW_FILE = Path("data/raw/parking_clean.csv")
OUT_FILE = Path("data/raw/parking_fast.csv")

columns_needed = [
    "summons_number",
    "plate_id",
    "registration_state",
    "plate_type",
    "issue_date",
    "violation_code",
    "vehicle_body_type",
    "vehicle_make",
    "issuing_agency",
    "violation_precinct",
    "issuer_precinct",
    "violation_time",
    "violation_county",
    "street_name",
    "vehicle_color",
    "vehicle_year",
    "violation_description",
]


def clean_csv():
    print("Cleaning parking CSV...")

    first_chunk = True
    total_rows = 0

    for chunk in pd.read_csv(
        RAW_FILE,
        usecols=columns_needed,
        chunksize=100000,
        low_memory=False,
    ):
        chunk["issue_date"] = pd.to_datetime(chunk["issue_date"], errors="coerce").dt.date
        chunk["vehicle_year"] = pd.to_numeric(chunk["vehicle_year"], errors="coerce")
        chunk["violation_code"] = pd.to_numeric(chunk["violation_code"], errors="coerce")
        chunk["violation_precinct"] = pd.to_numeric(chunk["violation_precinct"], errors="coerce")
        chunk["issuer_precinct"] = pd.to_numeric(chunk["issuer_precinct"], errors="coerce")

        chunk = chunk.dropna(subset=["summons_number"])

        chunk.to_csv(
            OUT_FILE,
            mode="w" if first_chunk else "a",
            index=False,
            header=first_chunk,
        )

        total_rows += len(chunk)
        first_chunk = False
        print("Rows cleaned:", total_rows)

    print("Finished:", OUT_FILE)


if __name__ == "__main__":
    clean_csv()