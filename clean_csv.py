from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from nycparking.core.date_window import issue_date_window


DEFAULT_RAW_FILE = Path(r"C:\Users\jayson.coker\Documents\nycparking\data\nycparking2025.csv")
OUT_FILE = Path("data/processed/parking_clean.csv")

SOURCE_COLUMNS = {
    "Summons Number": "summons_number",
    "Plate ID": "plate_id",
    "Registration State": "registration_state",
    "Plate Type": "plate_type",
    "Issue Date": "issue_date",
    "Violation Code": "violation_code",
    "Vehicle Body Type": "vehicle_body_type",
    "Vehicle Make": "vehicle_make",
    "Issuing Agency": "issuing_agency",
    "Violation Precinct": "violation_precinct",
    "Issuer Precinct": "issuer_precinct",
    "Violation Time": "violation_time",
    "Violation County": "violation_county",
    "Street Name": "street_name",
    "Vehicle Color": "vehicle_color",
    "Vehicle Year": "vehicle_year",
    "Violation Description": "violation_description",
}

OUTPUT_COLUMNS = list(SOURCE_COLUMNS.values())


def clean_csv(raw_file: Path = DEFAULT_RAW_FILE, out_file: Path = OUT_FILE) -> None:
    print(f"Cleaning parking CSV from {raw_file}")

    if not raw_file.exists():
        raise FileNotFoundError(f"Could not find {raw_file}")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    first_chunk = True
    total_rows = 0
    invalid_dates = 0
    outside_window = 0
    min_issue_date, max_issue_date = issue_date_window()
    print(f"Keeping Issue Date from {min_issue_date} through {max_issue_date}")

    for chunk in pd.read_csv(
        raw_file,
        usecols=list(SOURCE_COLUMNS),
        chunksize=100000,
        low_memory=False,
        dtype=str,
    ):
        chunk = chunk.rename(columns=SOURCE_COLUMNS)

        parsed_dates = pd.to_datetime(
            chunk["issue_date"],
            format="%m/%d/%Y",
            errors="coerce",
        )
        invalid_dates += int(parsed_dates.isna().sum())
        in_window = parsed_dates.between(min_issue_date, max_issue_date)
        outside_window += int((parsed_dates.notna() & ~in_window).sum())
        keep = parsed_dates.notna() & in_window
        chunk = chunk.loc[keep].copy()
        chunk["issue_date"] = parsed_dates.loc[keep].dt.strftime("%Y-%m-%d")

        chunk["summons_number"] = pd.to_numeric(chunk["summons_number"], errors="coerce")
        chunk["vehicle_year"] = pd.to_numeric(chunk["vehicle_year"], errors="coerce")
        chunk["violation_code"] = pd.to_numeric(chunk["violation_code"], errors="coerce")
        chunk["violation_precinct"] = pd.to_numeric(chunk["violation_precinct"], errors="coerce")
        chunk["issuer_precinct"] = pd.to_numeric(chunk["issuer_precinct"], errors="coerce")

        chunk = chunk.dropna(subset=["summons_number"])
        chunk = chunk[OUTPUT_COLUMNS]

        chunk.to_csv(
            out_file,
            mode="w" if first_chunk else "a",
            index=False,
            header=first_chunk,
        )

        total_rows += len(chunk)
        first_chunk = False
        print(f"Rows cleaned: {total_rows:,}")

    print(f"Finished: {out_file}")
    print(f"Rows written: {total_rows:,}")
    print(f"Rows skipped for invalid Issue Date: {invalid_dates:,}")
    print(f"Rows skipped outside Issue Date window: {outside_window:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean the original NYC parking CSV.")
    parser.add_argument(
        "raw_file",
        nargs="?",
        default=DEFAULT_RAW_FILE,
        type=Path,
        help="Path to the original NYC parking CSV.",
    )
    parser.add_argument(
        "--out",
        default=OUT_FILE,
        type=Path,
        help="Output path for the normalized CSV.",
    )
    args = parser.parse_args()
    clean_csv(args.raw_file, args.out)


if __name__ == "__main__":
    main()
