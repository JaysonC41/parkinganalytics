"""Resolve missing boroughs from repeated camera-location descriptions.

This is the second recovery stage for summons rows whose three street codes
are zero and whose precinct fields do not identify an NYPD precinct. It
resolves each unique description once, then propagates the reviewed result
back to every summons carrying that exact normalized description.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from .geosupport_boroughs import (
    ALL_BOROUGHS,
    DEFAULT_CACHE_FILE,
    DEFAULT_GEOSUPPORT_PATH,
    DEFAULT_OUTPUT_FILE,
    GeoserviceClient,
    LocalGeosupportClient,
    extract_values,
    geosupport_return_codes,
    response_succeeded,
)


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_FILE = PROJECT_ROOT / "data" / "database" / "nyc_parking.sqlite"
DEFAULT_LOOKUP_FILE = (
    PROJECT_ROOT / "data" / "processed" / "geosupport_camera_description_lookup.csv"
)
DEFAULT_MATCHES_FILE = (
    PROJECT_ROOT / "data" / "processed" / "geosupport_camera_description_matches.csv"
)
DEFAULT_ACCEPTED_FILE = (
    PROJECT_ROOT / "data" / "processed" / "geosupport_camera_description_accepted.csv"
)

TRAFFIC_DIRECTION_RE = re.compile(
    r"^(?P<direction>N/?B|S/?B|E/?B|W/?B)\s+",
    flags=re.IGNORECASE,
)
TRAILING_TRAFFIC_DIRECTION_RE = re.compile(
    r"\s*\((?:N|S|E|W)/?B\)\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedDescription:
    raw: str
    normalized: str
    direction: str
    on_street: str
    cross_street: str


def normalize_description(value: object) -> str:
    """Normalize spacing and case without expanding truncated street text."""
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).upper()


def parse_camera_description(value: object) -> ParsedDescription:
    """Split descriptions such as ``SB MELROSE AVE @ E 161 ST``."""
    normalized = normalize_description(value)
    match = TRAFFIC_DIRECTION_RE.match(normalized)
    direction = ""
    location = normalized
    if match:
        direction = match.group("direction").replace("/", "").upper()
        location = normalized[match.end() :].strip()

    on_street, separator, cross_street = location.partition("@")
    on_street = TRAILING_TRAFFIC_DIRECTION_RE.sub("", on_street).strip()
    cross_street = cross_street.strip() if separator else ""
    return ParsedDescription(
        raw="" if value is None or pd.isna(value) else str(value),
        normalized=normalized,
        direction=direction,
        on_street=on_street,
        cross_street=cross_street,
    )


def read_skipped_targets(
    database_file: Path,
    audit_file: Path,
) -> pd.DataFrame:
    """Return missing-borough database rows absent from the first-stage audit."""
    audit = pd.read_csv(audit_file, usecols=["summons_number"], dtype="string")
    audit_ids = set(
        pd.to_numeric(audit["summons_number"], errors="coerce")
        .dropna()
        .astype("int64")
    )

    with sqlite3.connect(database_file) as connection:
        has_recovery = bool(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table' AND name = 'borough_recovery'
                """
            ).fetchone()[0]
        )
        recovery_join = (
            "LEFT JOIN borough_recovery AS r USING (summons_number)"
            if has_recovery
            else ""
        )
        recovery_filter = "AND r.summons_number IS NULL" if has_recovery else ""
        targets = pd.read_sql_query(
            f"""
            SELECT
                p.summons_number,
                p.street_name AS source_description
            FROM parking_violations AS p
            {recovery_join}
            WHERE (p.borough IS NULL OR TRIM(p.borough) = '')
              {recovery_filter}
            """,
            connection,
        )

    targets = targets[~targets["summons_number"].isin(audit_ids)].copy()
    targets["normalized_description"] = targets["source_description"].map(
        normalize_description
    )
    return targets


def known_description_evidence(
    database_file: Path,
    descriptions: list[str],
) -> pd.DataFrame:
    """Count known-borough rows carrying each exact normalized description."""
    if not descriptions:
        return pd.DataFrame(
            columns=[
                "normalized_description",
                "known_borough",
                "known_borough_count",
                "known_total",
                "known_boroughs",
            ]
        )

    with sqlite3.connect(database_file) as connection:
        connection.execute(
            """
            CREATE TEMP TABLE target_descriptions (
                normalized_description TEXT PRIMARY KEY
            )
            """
        )
        connection.executemany(
            "INSERT INTO target_descriptions VALUES (?)",
            ((description,) for description in descriptions),
        )
        evidence = pd.read_sql_query(
            """
            SELECT
                UPPER(TRIM(p.street_name)) AS normalized_description,
                p.borough,
                COUNT(*) AS known_count
            FROM parking_violations AS p
            INNER JOIN target_descriptions AS t
                ON t.normalized_description = UPPER(TRIM(p.street_name))
            WHERE p.borough IS NOT NULL
              AND TRIM(p.borough) <> ''
            GROUP BY UPPER(TRIM(p.street_name)), p.borough
            """,
            connection,
        )

    rows: list[dict[str, Any]] = []
    for description in descriptions:
        group = evidence[evidence["normalized_description"].eq(description)]
        borough_counts = {
            str(row.borough): int(row.known_count)
            for row in group.itertuples(index=False)
        }
        rows.append(
            {
                "normalized_description": description,
                "known_borough": (
                    next(iter(borough_counts)) if len(borough_counts) == 1 else ""
                ),
                "known_borough_count": len(borough_counts),
                "known_total": sum(borough_counts.values()),
                "known_boroughs": "|".join(
                    f"{borough}:{count}"
                    for borough, count in sorted(borough_counts.items())
                ),
            }
        )
    return pd.DataFrame(rows)


def response_coordinates(response: dict[str, Any]) -> tuple[str, str]:
    latitude = next(iter(extract_values(response, ("latitude",))), "")
    longitude = next(iter(extract_values(response, ("longitude",))), "")
    return latitude, longitude


def browse_cross_street_intersections(
    parsed: ParsedDescription,
    client: GeoserviceClient | LocalGeosupportClient,
    max_candidates: int = 10,
) -> dict[str, list[str]]:
    """Expand a truncated cross street with Function 1N, then try Function 2."""
    if len(parsed.cross_street.replace(" ", "")) < 3:
        return {}

    matches: dict[str, list[str]] = {}
    for borough in ALL_BOROUGHS:
        if not response_succeeded(client.street_name(borough, parsed.on_street)):
            continue
        browse_response = client.street_name(borough, parsed.cross_street)
        candidates: list[str] = []
        for candidate in extract_values(
            browse_response,
            ("firststreetnamenormalized", "listofstreetnames"),
        ):
            cleaned = str(candidate).strip()
            if (
                cleaned
                and cleaned.upper() != parsed.cross_street.upper()
                and cleaned not in candidates
            ):
                candidates.append(cleaned)
        for candidate in candidates[:max_candidates]:
            response = client.intersection(
                borough,
                parsed.on_street,
                candidate,
            )
            if response_succeeded(response):
                matches.setdefault(borough, []).append(candidate)
    return matches


def apply_browse_result(
    result: dict[str, Any],
    browse_matches: dict[str, list[str]],
    corridor_borough: str,
    corridor_summons: int,
) -> dict[str, Any]:
    """Apply a unique browsed intersection unless corridor evidence conflicts."""
    updated = dict(result)
    updated["corridor_borough"] = corridor_borough
    updated["corridor_summons"] = corridor_summons
    updated["browse_intersection_valid_boroughs"] = "|".join(browse_matches)
    updated["browse_intersection_matches"] = "|".join(
        f"{borough}:{candidate}"
        for borough, candidates in browse_matches.items()
        for candidate in candidates
    )
    if len(browse_matches) != 1:
        return updated

    browse_borough = next(iter(browse_matches))
    if corridor_borough and corridor_borough != browse_borough:
        updated.update(
            {
                "suggested_borough": "",
                "status": "review",
                "confidence": "low",
                "resolution_method": "browse_intersection_corridor_conflict",
            }
        )
    else:
        updated.update(
            {
                "suggested_borough": browse_borough,
                "status": "accepted",
                "confidence": "medium",
                "resolution_method": "browse_intersection_function_2",
            }
        )
    return updated


def resolve_description(
    parsed: ParsedDescription,
    known_borough: str,
    known_borough_count: int,
    known_total: int,
    known_boroughs: str,
    client: GeoserviceClient | LocalGeosupportClient,
) -> dict[str, Any]:
    """Resolve one unique description using progressively weaker evidence."""
    base: dict[str, Any] = {
        "normalized_description": parsed.normalized,
        "direction": parsed.direction,
        "parsed_on_street": parsed.on_street,
        "parsed_cross_street": parsed.cross_street,
        "known_boroughs": known_boroughs,
        "known_total": known_total,
        "intersection_valid_boroughs": "",
        "street_valid_boroughs": "",
        "browse_intersection_valid_boroughs": "",
        "browse_intersection_matches": "",
        "corridor_borough": "",
        "corridor_summons": 0,
        "suggested_borough": "",
        "status": "unmatched",
        "confidence": "",
        "resolution_method": "",
        "geosupport_street_names": "",
        "latitude": "",
        "longitude": "",
        "geosupport_return_codes": "",
    }

    if known_borough and known_borough_count == 1:
        base.update(
            {
                "suggested_borough": known_borough,
                "status": "accepted",
                "confidence": "high",
                "resolution_method": "known_exact_description",
            }
        )
        return base

    if not parsed.on_street:
        base["resolution_method"] = "blank_description"
        return base

    intersection_matches: list[tuple[str, dict[str, Any]]] = []
    if parsed.cross_street:
        for borough in ALL_BOROUGHS:
            response = client.intersection(
                borough,
                parsed.on_street,
                parsed.cross_street,
            )
            if response_succeeded(response):
                intersection_matches.append((borough, response))

    base["intersection_valid_boroughs"] = "|".join(
        borough for borough, _ in intersection_matches
    )
    if len(intersection_matches) == 1:
        borough, response = intersection_matches[0]
        latitude, longitude = response_coordinates(response)
        base.update(
            {
                "suggested_borough": borough,
                "status": "accepted",
                "confidence": "high",
                "resolution_method": "parsed_intersection_function_2",
                "geosupport_street_names": "|".join(
                    extract_values(
                        response,
                        (
                            "firststreetnamenormalized",
                            "secondstreetnamenormalized",
                            "listofstreetnames",
                        ),
                    )
                ),
                "latitude": latitude,
                "longitude": longitude,
                "geosupport_return_codes": "|".join(
                    geosupport_return_codes(response)
                ),
            }
        )
        return base
    if len(intersection_matches) > 1:
        base.update(
            {
                "status": "ambiguous",
                "resolution_method": "intersection_multiple_boroughs",
            }
        )
        return base

    street_matches: list[tuple[str, dict[str, Any]]] = []
    for borough in ALL_BOROUGHS:
        response = client.street_name(borough, parsed.on_street)
        if response_succeeded(response):
            street_matches.append((borough, response))

    base["street_valid_boroughs"] = "|".join(
        borough for borough, _ in street_matches
    )
    if len(street_matches) == 1:
        borough, response = street_matches[0]
        base.update(
            {
                "suggested_borough": borough,
                "status": "accepted",
                "confidence": "medium",
                "resolution_method": "unique_street_function_1n",
                "geosupport_street_names": "|".join(
                    extract_values(
                        response,
                        ("firststreetnamenormalized", "listofstreetnames"),
                    )
                ),
                "geosupport_return_codes": "|".join(
                    geosupport_return_codes(response)
                ),
            }
        )
    elif len(street_matches) > 1:
        base.update(
            {
                "status": "ambiguous",
                "resolution_method": "street_multiple_boroughs",
            }
        )
    else:
        base["resolution_method"] = (
            "intersection_and_street_unmatched"
            if parsed.cross_street
            else "street_unmatched"
        )
    return base


def build_client(
    backend: str,
    geosupport_path: Path,
    cache_file: Path,
    delay: float,
    timeout: float,
) -> GeoserviceClient | LocalGeosupportClient:
    if backend == "local":
        return LocalGeosupportClient(geosupport_path)
    api_key = os.getenv("GEOSERVICE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEOSERVICE_API_KEY is required for --backend api")
    return GeoserviceClient(
        api_key=api_key,
        cache_path=cache_file,
        delay_seconds=delay,
        timeout_seconds=timeout,
    )


def run(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    database_file = Path(args.database_file)
    audit_file = Path(args.audit_file)
    lookup_file = Path(args.lookup_file)
    matches_file = Path(args.matches_file)
    accepted_file = Path(args.accepted_file)

    targets = read_skipped_targets(database_file, audit_file)
    description_counts = (
        targets.groupby("normalized_description", dropna=False)
        .size()
        .rename("summons_count")
        .reset_index()
        .sort_values("summons_count", ascending=False)
    )
    if args.limit:
        description_counts = description_counts.head(args.limit)
        targets = targets[
            targets["normalized_description"].isin(
                description_counts["normalized_description"]
            )
        ].copy()

    evidence = known_description_evidence(
        database_file,
        description_counts["normalized_description"].tolist(),
    )
    descriptions = description_counts.merge(
        evidence,
        on="normalized_description",
        how="left",
        validate="one_to_one",
    )

    client = build_client(
        args.backend,
        Path(args.geosupport_path),
        Path(args.cache_file),
        args.delay,
        args.timeout,
    )
    rows: list[dict[str, Any]] = []
    try:
        for number, row in enumerate(descriptions.itertuples(index=False), 1):
            parsed = parse_camera_description(row.normalized_description)
            resolved = resolve_description(
                parsed,
                known_borough=str(row.known_borough or ""),
                known_borough_count=int(row.known_borough_count or 0),
                known_total=int(row.known_total or 0),
                known_boroughs=str(row.known_boroughs or ""),
                client=client,
            )
            resolved["summons_count"] = int(row.summons_count)
            rows.append(resolved)
            if number % 25 == 0:
                LOGGER.info(
                    "Resolved %s of %s unique descriptions",
                    number,
                    len(descriptions),
                )
        lookup = pd.DataFrame(rows)
        accepted_corridors = (
            lookup[lookup["status"].eq("accepted")]
            .groupby(["parsed_on_street", "suggested_borough"], dropna=False)[
                "summons_count"
            ]
            .sum()
            .reset_index()
        )
        corridor_summary = (
            accepted_corridors.groupby("parsed_on_street", dropna=False)
            .agg(
                borough_count=("suggested_borough", "nunique"),
                corridor_summons=("summons_count", "sum"),
            )
            .reset_index()
        )
        unique_corridor_summary = corridor_summary[
            corridor_summary["borough_count"].eq(1)
        ]
        unique_corridors = unique_corridor_summary.merge(
            accepted_corridors[
                accepted_corridors["parsed_on_street"].isin(
                    unique_corridor_summary["parsed_on_street"]
                )
            ][
                ["parsed_on_street", "suggested_borough"]
            ].drop_duplicates(),
            on="parsed_on_street",
            how="left",
            validate="one_to_one",
        )
        corridor_map = {
            str(row.parsed_on_street): (
                str(row.suggested_borough),
                int(row.corridor_summons),
            )
            for row in unique_corridors.itertuples(index=False)
        }

        for index in lookup.index[lookup["status"].eq("ambiguous")]:
            parsed = parse_camera_description(
                lookup.at[index, "normalized_description"]
            )
            browse_matches = browse_cross_street_intersections(parsed, client)
            corridor_borough, corridor_summons = corridor_map.get(
                parsed.on_street,
                ("", 0),
            )
            updated = apply_browse_result(
                lookup.loc[index].to_dict(),
                browse_matches,
                corridor_borough,
                corridor_summons,
            )
            for key, value in updated.items():
                lookup.at[index, key] = value
    finally:
        client.close()

    matches = targets.merge(
        lookup,
        on="normalized_description",
        how="left",
        validate="many_to_one",
    )
    accepted = matches[matches["status"].eq("accepted")].copy()

    for path in (lookup_file, matches_file, accepted_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    lookup.to_csv(lookup_file, index=False)
    matches.to_csv(matches_file, index=False)
    accepted.to_csv(accepted_file, index=False)

    LOGGER.info("Wrote %s unique-description rows to %s", len(lookup), lookup_file)
    LOGGER.info("Wrote %s summons rows to %s", len(matches), matches_file)
    LOGGER.info("Accepted %s summons rows into %s", len(accepted), accepted_file)
    if not matches.empty:
        LOGGER.info("Status counts:\n%s", matches["status"].value_counts().to_string())
    return lookup, matches


def build_parser() -> argparse.ArgumentParser:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Resolve missing boroughs from repeated camera descriptions."
    )
    parser.add_argument("--database-file", default=DEFAULT_DATABASE_FILE)
    parser.add_argument("--audit-file", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--lookup-file", default=DEFAULT_LOOKUP_FILE)
    parser.add_argument("--matches-file", default=DEFAULT_MATCHES_FILE)
    parser.add_argument("--accepted-file", default=DEFAULT_ACCEPTED_FILE)
    parser.add_argument(
        "--backend",
        choices=("local", "api"),
        default="local",
    )
    parser.add_argument(
        "--geosupport-path",
        default=os.getenv("GEOSUPPORT_PATH", str(DEFAULT_GEOSUPPORT_PATH)),
    )
    parser.add_argument("--cache-file", default=DEFAULT_CACHE_FILE)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum unique descriptions; 0 processes every description.",
    )
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run(args)


if __name__ == "__main__":
    main()
