from sqlalchemy import text

from nycparking.core.db import engine


def init_schema():
    print("Initializing warehouse schema")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS parking_violations (
                summons_number BIGINT NOT NULL PRIMARY KEY,
                plate_id VARCHAR(50),
                registration_state VARCHAR(10),
                plate_type VARCHAR(20),
                issue_date DATE,
                violation_code INT,
                vehicle_body_type VARCHAR(50),
                vehicle_make VARCHAR(100),
                issuing_agency VARCHAR(50),
                violation_precinct INT,
                issuer_precinct INT,
                violation_time VARCHAR(20),
                violation_county VARCHAR(50),
                street_name VARCHAR(255),
                vehicle_color VARCHAR(50),
                vehicle_year INT,
                violation_description TEXT,
                weather_id INT,
                INDEX idx_violation_precinct (violation_precinct),
                INDEX idx_issue_date (issue_date),
                INDEX idx_precinct_date (violation_precinct, issue_date),
                INDEX idx_violation_code (violation_code),
                INDEX idx_precinct (issuer_precinct),
                INDEX idx_parking_weather (weather_id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_weather (
                weather_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                weather_date DATE,
                avg_temp FLOAT,
                precipitation FLOAT,
                snow_depth FLOAT,
                weather_condition VARCHAR(50),
                INDEX idx_weather_date (weather_date)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_violation (
                violation_code INT NOT NULL PRIMARY KEY,
                violation_description TEXT,
                base_fine INT
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_precinct (
                precinct_id INT NOT NULL PRIMARY KEY
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_census_precinct (
                census_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                precinct INT,
                population INT,
                median_income INT,
                poverty_rate FLOAT,
                population_density FLOAT
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                issue_date DATE,
                ticket_count BIGINT NOT NULL DEFAULT 0,
                INDEX idx_daily_summary_date (issue_date)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS precinct_summary (
                violation_precinct INT,
                ticket_count BIGINT NOT NULL DEFAULT 0,
                INDEX idx_precinct_summary_precinct (violation_precinct)
            )
        """))

    print("Warehouse schema ready")
