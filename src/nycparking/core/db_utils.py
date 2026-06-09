from sqlalchemy import text

from nycparking.core.db import engine


def table_exists(table_name: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                        AND table_name = :table_name
                """),
                {"table_name": table_name},
            ).scalar()
        )


def table_row_count(table_name: str) -> int:
    if not table_exists(table_name):
        return 0
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar() or 0)


def table_has_rows(table_name: str) -> bool:
    if not table_exists(table_name):
        return False
    with engine.connect() as conn:
        return bool(conn.execute(text(f"SELECT 1 FROM `{table_name}` LIMIT 1")).first())
