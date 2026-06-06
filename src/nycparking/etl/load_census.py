import os

import pandas as pd
import requests
from dotenv import load_dotenv

from nycparking.core.db import engine

load_dotenv()

API_KEY = os.getenv("CENSUS_API_KEY")

if not API_KEY:
    raise ValueError("CENSUS_API_KEY is missing. Add it to your .env file.")


def fetch_census():
    print("Fetching census data")

    url = (
        "https://api.census.gov/data/2020/dec/pl"
        "?get=NAME,P1_001N"
        "&for=county:*"
        "&in=state:36"
        f"&key={API_KEY}"
    )

    response = requests.get(url, timeout=30)
    print("Status:", response.status_code)
    response.raise_for_status()

    data = response.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = ["name", "population", "state", "county"]

    df["population"] = pd.to_numeric(df["population"], errors="coerce")

    return df


def load_census():
    print("Loading census into database")

    df = fetch_census()
    df.to_sql("staging_census", engine, if_exists="replace", index=False)

    print(f"Census loaded: {len(df)} rows")
