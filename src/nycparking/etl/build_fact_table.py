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
                violation_description
            )
            SELECT
                summons_number,
                plate_id,
                registration_state,
                plate_type,
                STR_TO_DATE(issue_date, '%Y-%m-%d'),
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
                CAST(vehicle_year AS UNSIGNED),
                violation_description
            FROM staging_parking
        """))

    print("Parking violations table built")