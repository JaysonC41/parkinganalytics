from sqlalchemy import text

from nycparking.core.db import engine


def build_dim_weather():
    print("Building weather dimension")

    # reload this table because the weather file is small
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dim_weather"))

        conn.execute(text("""
            INSERT INTO dim_weather (
                weather_date,
                avg_temp,
                precipitation,
                snow_depth,
                weather_condition
            )
            SELECT
                DATE(weather_date),
                (temperature_2m_max + temperature_2m_min) / 2,
                precipitation_sum,
                0,
                weather_condition
            FROM staging_weather
            WHERE weather_date IS NOT NULL
        """))

    print("Weather dimension built")
