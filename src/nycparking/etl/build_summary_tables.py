from sqlalchemy import text

from nycparking.core.db import engine


def build_summary_tables():
    print("Building summary tables")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE daily_summary"))
        conn.execute(text("""
            INSERT INTO daily_summary (issue_date, ticket_count)
            SELECT
                issue_date,
                COUNT(*) AS ticket_count
            FROM parking_violations
            WHERE issue_date IS NOT NULL
            GROUP BY issue_date
        """))

        conn.execute(text("TRUNCATE TABLE precinct_summary"))
        conn.execute(text("""
            INSERT INTO precinct_summary (violation_precinct, ticket_count)
            SELECT
                violation_precinct,
                COUNT(*) AS ticket_count
            FROM parking_violations
            WHERE violation_precinct IS NOT NULL
            GROUP BY violation_precinct
        """))

    print("Summary tables built")
