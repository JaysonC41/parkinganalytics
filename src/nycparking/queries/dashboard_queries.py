import pandas as pd
from sqlalchemy import text

from nycparking.core.db import engine


FACT_TABLE = "parking_violations"


def tickets_by_month():
    sql = f"""
    SELECT
        DATE_FORMAT(issue_date, '%Y-%m') AS month,
        COUNT(*) AS tickets
    FROM {FACT_TABLE}
    GROUP BY month
    ORDER BY month
    """

    return pd.read_sql(text(sql), engine)


def top_violations():
    sql = f"""
    SELECT
        violation_code,
        COUNT(*) AS tickets
    FROM {FACT_TABLE}
    GROUP BY violation_code
    ORDER BY tickets DESC
    LIMIT 20
    """

    return pd.read_sql(text(sql), engine)


def tickets_by_precinct():
    sql = f"""
    SELECT
        issuer_precinct,
        COUNT(*) AS tickets
    FROM {FACT_TABLE}
    WHERE issuer_precinct IS NOT NULL
    GROUP BY issuer_precinct
    ORDER BY tickets DESC
    LIMIT 25
    """

    return pd.read_sql(text(sql), engine)


def tickets_by_weather():
    sql = f"""
    SELECT
        COALESCE(w.weather_condition, 'Unknown') AS weather_condition,
        COUNT(*) AS tickets
    FROM {FACT_TABLE} p
    LEFT JOIN dim_weather w
        ON w.weather_id = p.weather_id
    GROUP BY weather_condition
    ORDER BY tickets DESC
    LIMIT 15
    """

    return pd.read_sql(text(sql), engine)


def summary_metrics():
    sql = f"""
    SELECT
        COUNT(*) AS total_tickets,
        COUNT(DISTINCT issue_date) AS active_days,
        COUNT(DISTINCT violation_code) AS violation_types,
        COUNT(DISTINCT violation_precinct) AS precincts
    FROM {FACT_TABLE}
    """

    return pd.read_sql(text(sql), engine).iloc[0].to_dict()
