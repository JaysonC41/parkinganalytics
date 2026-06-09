from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def issue_date_window() -> tuple[str, str]:
    min_date = os.getenv("PARKING_MIN_ISSUE_DATE", "2000-01-01")
    max_date = os.getenv("PARKING_MAX_ISSUE_DATE", "2025-12-31")
    return min_date, max_date
