from sqlalchemy import text

from nycparking.core.db import engine


def build_dim_tables():
    print("Building dimension tables")

    with engine.begin() as conn:
        # keep existing dimension rows and only add new values
        conn.execute(text("""
            INSERT IGNORE INTO dim_violation
            SELECT DISTINCT
                violation_code,
                violation_description,
                fine_amount
            FROM staging_parking
            WHERE violation_code IS NOT NULL
        """))

        conn.execute(text("""
            INSERT IGNORE INTO dim_precinct (precinct_id)
            SELECT DISTINCT issuer_precinct
            FROM staging_parking
            WHERE issuer_precinct IS NOT NULL
        """))

    print("Dimension tables built")
