from sqlalchemy import text
from nycparking.core.db import engine


def build_fact_table():
    print("Building parking violations table")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE parking_violations"))

        conn.execute(text("""
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
                plate_id,
                registration_state,
                plate_type,
                STR_TO_DATE(s.issue_date, '%Y-%m-%d'),
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
                CAST(NULLIF(vehicle_year, '') AS UNSIGNED),
                violation_description,
                w.weather_id
            FROM staging_parking s
            LEFT JOIN dim_weather w
                ON w.weather_date = STR_TO_DATE(s.issue_date, '%Y-%m-%d')
        """))

    print("Parking violations table built")


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
