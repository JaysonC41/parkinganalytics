from sqlalchemy import text

from nycparking.core.db import engine
from nycparking.core.db_utils import table_has_rows
from nycparking.core.date_window import issue_date_window


def build_fact_table(force_rebuild: bool = False):
    print("Building parking violations table")

    if table_has_rows("parking_violations") and not force_rebuild:
        print(
            "parking_violations already has rows; "
            "skipping fact rebuild. Use force rebuild to replace it."
        )
        return

    min_issue_date, max_issue_date = issue_date_window()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE parking_violations"))

        result = conn.execute(
            text("""
                INSERT INTO parking_violations (
                    summons_number,
                    plate_id,
                    registration_state,
                    plate_type,
                    issue_date,
                    violation_code,
                    vehicle_body_type,
                    vehicle_make,
                    issuing_agency,
                    violation_precinct,
                    issuer_precinct,
                    violation_time,
                    violation_county,
                    street_name,
                    vehicle_color,
                    vehicle_year,
                    violation_description,
                    weather_id
                )
                SELECT
                    CAST(s.summons_number AS UNSIGNED),
                    s.plate_id,
                    s.registration_state,
                    s.plate_type,
                    s.issue_date,
                    s.violation_code,
                    s.vehicle_body_type,
                    s.vehicle_make,
                    s.issuing_agency,
                    s.violation_precinct,
                    s.issuer_precinct,
                    s.violation_time,
                    s.violation_county,
                    s.street_name,
                    s.vehicle_color,
                    CAST(NULLIF(s.vehicle_year, '') AS UNSIGNED),
                    s.violation_description,
                    w.weather_id
                FROM (
                    SELECT
                        summons_number,
                        plate_id,
                        registration_state,
                        plate_type,
                        STR_TO_DATE(issue_date, '%Y-%m-%d') AS issue_date,
                        violation_code,
                        vehicle_body_type,
                        vehicle_make,
                        issuing_agency,
                        violation_precinct,
                        issuer_precinct,
                        violation_time,
                        violation_county,
                        street_name,
                        vehicle_color,
                        vehicle_year,
                        violation_description
                    FROM staging_parking
                    WHERE issue_date REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                ) s
                LEFT JOIN dim_weather w
                    ON w.weather_date = s.issue_date
                WHERE s.issue_date BETWEEN :min_issue_date AND :max_issue_date
            """),
            {"min_issue_date": min_issue_date, "max_issue_date": max_issue_date},
        )

    print(
        f"Parking violations table built with {result.rowcount:,} rows "
        f"from {min_issue_date} through {max_issue_date}"
    )


def clean_fact_issue_dates():
    min_issue_date, max_issue_date = issue_date_window()
    print(f"Removing fact rows outside {min_issue_date} through {max_issue_date}")

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                DELETE FROM parking_violations
                WHERE issue_date IS NULL
                    OR issue_date < :min_issue_date
                    OR issue_date > :max_issue_date
            """),
            {"min_issue_date": min_issue_date, "max_issue_date": max_issue_date},
        )

    print(f"Removed {result.rowcount:,} invalid-date fact rows")


def refresh_fact_weather_ids():
    print("Linking parking violations to weather dimension")

    with engine.connect() as conn:
        date_rows = conn.execute(text("""
            SELECT d.issue_date, w.weather_id
            FROM daily_summary d
            JOIN dim_weather w
                ON w.weather_date = d.issue_date
            WHERE d.issue_date IS NOT NULL
            ORDER BY d.issue_date
        """)).fetchall()

    if not date_rows:
        print("No matching weather dates found")
        return

    total_updated = 0
    for index, row in enumerate(date_rows, start=1):
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE parking_violations
                    SET weather_id = :weather_id
                    WHERE issue_date = :issue_date
                        AND (weather_id IS NULL OR weather_id <> :weather_id)
                """),
                {"weather_id": row.weather_id, "issue_date": row.issue_date},
            )
            total_updated += result.rowcount
        if index % 50 == 0 or index == len(date_rows):
            print(f"Linked weather for {index:,}/{len(date_rows):,} dates")

    print(f"Parking weather links refreshed: {total_updated:,} rows updated")
