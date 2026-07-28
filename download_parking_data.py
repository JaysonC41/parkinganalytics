"""Download the verified FY2025 parking source from the project release."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nycparking.source_data import ensure_parking_source  # noqa: E402


if __name__ == "__main__":
    ensure_parking_source(PROJECT_ROOT)
