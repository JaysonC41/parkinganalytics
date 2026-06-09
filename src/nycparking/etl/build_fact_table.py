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

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE parking_violations p
            JOIN dim_weather w
                ON w.weather_date = p.issue_date
            SET p.weather_id = w.weather_id
            WHERE p.weather_id IS NULL
                OR p.weather_id <> w.weather_id
        """))

    print("Parking weather links refreshed")
