from sqlalchemy import text

from nycparking.core.db import engine


def build_dim_tables():
    print("Building dimension tables")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dim_violation"))

        conn.execute(text("""
            INSERT INTO dim_violation (
                violation_code,
                violation_description,
                base_fine
            )
            SELECT
                violation_code,
                MAX(violation_description),
                CAST(
                    NULLIF(
                        REGEXP_REPLACE(MAX(fine_amount), '[^0-9]', ''),
                        ''
                    ) AS UNSIGNED
                )
            FROM violation_lookup
            WHERE violation_code IS NOT NULL
            GROUP BY violation_code
        """))

        conn.execute(text("""
            INSERT IGNORE INTO dim_precinct (precinct_id)
            SELECT DISTINCT issuer_precinct
            FROM staging_parking
            WHERE issuer_precinct IS NOT NULL
        """))

    print("Dimension tables built")
