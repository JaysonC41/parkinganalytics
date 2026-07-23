"""Recover missing boroughs from parking-summons street codes.

The source data stores five-digit street codes without the borough digit that
Geosupport requires.  This module learns plausible boroughs from rows whose
borough is known, then validates each plausible B5SC through NYC Geoservice.
It writes an audit file; it never silently changes the source data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOGGER = logging.getLogger(__name__)
DEFAULT_RAW_FILE = Path("data/raw/nycparking2025.csv")
DEFAULT_OUTPUT_FILE = Path("data/processed/geosupport_borough_matches.csv")
DEFAULT_CACHE_FILE = Path("data/processed/geosupport_cache.sqlite")
API_ROOT = "https://geoservice.planning.nyc.gov/geoservice/geoservice.svc"

BOROUGH_CODES = {
    "Manhattan": "1",
    "Bronx": "2",
    "Brooklyn": "3",
    "Queens": "4",
    "Staten Island": "5",
}
CODE_TO_BOROUGH = {code: borough for borough, code in BOROUGH_CODES.items()}
ALL_BOROUGHS = tuple(BOROUGH_CODES)

BOROUGH_MAP = {
    "BRONX": "Bronx",
    "BX": "Bronx",
    "P": "Bronx",
    "108": "Bronx",
    "BK": "Brooklyn",
    "K": "Brooklyn",
    "K F": "Brooklyn",
    "KINGS": "Brooklyn",
    "Q": "Queens",
    "QN": "Queens",
    "QNS": "Queens",
    "MN": "Manhattan",
    "NY": "Manhattan",
    "R": "Staten Island",
    "RICH": "Staten Island",
    "ST": "Staten Island",
}

SOURCE_COLUMNS = [
    "Summons Number",
    "Street Code1",
    "Street Code2",
    "Street Code3",
    "Violation County",
    "House Number",
    "Street Name",
    "Violation Location",
    "Violation Precinct",
]


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_county(value: object) -> str | None:
    text = re.sub(r"\s+", " ", clean_text(value).upper())
    return BOROUGH_MAP.get(text)


def normalize_street_code(value: object) -> str:
    """Return a five-character 5SC, preserving leading zeroes."""
    text = clean_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    if not text.isdigit():
        return ""
    number = int(text)
    if number == 0 or number > 99_999:
        return ""
    return f"{number:05d}"


def normalize_street_name(value: object) -> str:
    text = re.sub(r"[^A-Z0-9 ]+", " ", clean_text(value).upper())
    replacements = {
        "AVENUE": "AVE",
        "BOULEVARD": "BLVD",
        "STREET": "ST",
        "ROAD": "RD",
        "DRIVE": "DR",
        "PLACE": "PL",
        "PARKWAY": "PKWY",
    }
    words = [replacements.get(word, word) for word in text.split()]
    return " ".join(words)


def street_name_similarity(source_name: str, geosupport_names: Sequence[str]) -> float:
    source = normalize_street_name(source_name)
    if not source:
        return 0.0
    scores = []
    for name in geosupport_names:
        candidate = normalize_street_name(name)
        if not candidate:
            continue
        if candidate in source or source in candidate:
            scores.append(1.0)
        else:
            scores.append(SequenceMatcher(None, source, candidate).ratio())
    return max(scores, default=0.0)


def precinct_borough(value: object) -> str | None:
    try:
        precinct = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    if 1 <= precinct <= 34:
        return "Manhattan"
    if 40 <= precinct <= 52:
        return "Bronx"
    if 60 <= precinct <= 94:
        return "Brooklyn"
    if 100 <= precinct <= 115:
        return "Queens"
    if 120 <= precinct <= 123:
        return "Staten Island"
    return None


@dataclass(frozen=True)
class SummonsLocation:
    summons_number: str
    codes: tuple[str, ...]
    house_number: str
    street_name: str
    violation_location: str
    violation_precinct: str


@dataclass(frozen=True)
class CandidatePlan:
    boroughs: tuple[str, ...]
    method: str


class EmpiricalStreetCodeIndex:
    """Borough observations for codes and code tuples in known rows."""

    def __init__(self) -> None:
        self.code_boroughs: dict[str, set[str]] = defaultdict(set)
        self.tuple_boroughs: dict[tuple[str, ...], set[str]] = defaultdict(set)

    def add(self, borough: str, codes: Iterable[str]) -> None:
        code_tuple = tuple(code for code in codes if code)
        if not code_tuple:
            return
        for code in set(code_tuple):
            self.code_boroughs[code].add(borough)
        self.tuple_boroughs[code_tuple].add(borough)

    def candidates(self, codes: Sequence[str]) -> CandidatePlan:
        code_tuple = tuple(code for code in codes if code)
        exact = self.tuple_boroughs.get(code_tuple, set())
        if exact:
            preferred = sorted(exact)
            remaining = [borough for borough in ALL_BOROUGHS if borough not in exact]
            return CandidatePlan(tuple(preferred + remaining), "exact_code_tuple_ranked")

        observed = [self.code_boroughs[code] for code in code_tuple if self.code_boroughs.get(code)]
        if observed:
            intersection = set.intersection(*(set(item) for item in observed))
            if intersection:
                preferred = sorted(intersection)
                remaining = [borough for borough in ALL_BOROUGHS if borough not in intersection]
                return CandidatePlan(tuple(preferred + remaining), "code_intersection_ranked")
            union = set.union(*(set(item) for item in observed))
            if union:
                preferred = sorted(union)
                remaining = [borough for borough in ALL_BOROUGHS if borough not in union]
                return CandidatePlan(tuple(preferred + remaining), "code_union_ranked")
        return CandidatePlan(ALL_BOROUGHS, "all_boroughs_fallback")


class ResponseCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS geoservice_response (
                cache_key TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                request_params TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    @staticmethod
    def key(endpoint: str, params: Mapping[str, object]) -> str:
        payload = json.dumps([endpoint, sorted(params.items())], separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, endpoint: str, params: Mapping[str, object]) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT response_json FROM geoservice_response WHERE cache_key = ?",
            (self.key(endpoint, params),),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, endpoint: str, params: Mapping[str, object], response: dict[str, Any]) -> None:
        public_params = json.dumps(dict(params), sort_keys=True, separators=(",", ":"))
        self.connection.execute(
            """
            INSERT OR REPLACE INTO geoservice_response
                (cache_key, endpoint, request_params, response_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                self.key(endpoint, params),
                endpoint,
                public_params,
                json.dumps(response, separators=(",", ":")),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def flatten_json(value: object, prefix: str = "") -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            items.extend(flatten_json(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(flatten_json(child, f"{prefix}[{index}]"))
    else:
        items.append((prefix, value))
    return items


def normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower().split(".")[-1])


def geosupport_return_codes(response: Mapping[str, Any]) -> list[str]:
    values = []
    for key, value in flatten_json(response):
        name = normalized_key(key)
        if name in {"grc", "geosupportreturncode"} or name.endswith("grc"):
            values.append(str(value).strip())
    return values


def response_succeeded(response: Mapping[str, Any]) -> bool:
    if response.get("_client_error"):
        return False
    codes = geosupport_return_codes(response)
    if codes:
        return all(code.isdigit() and int(code) <= 1 for code in codes)
    error_fields = [
        str(value)
        for key, value in flatten_json(response)
        if "error" in normalized_key(key) and value
    ]
    return not error_fields and bool(response)


def extract_values(response: Mapping[str, Any], key_fragments: Sequence[str]) -> list[str]:
    fragments = tuple(re.sub(r"[^a-z0-9]", "", item.lower()) for item in key_fragments)
    values = []
    for key, value in flatten_json(response):
        name = normalized_key(key)
        if any(fragment in name for fragment in fragments) and value not in (None, ""):
            text = str(value).strip()
            if text and text not in values:
                values.append(text)
    return values


class GeoserviceClient:
    def __init__(
        self,
        api_key: str,
        cache_path: Path,
        delay_seconds: float = 0.1,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("GEOSERVICE_API_KEY is required unless --prepare-only is used")
        self.api_key = api_key
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.cache = ResponseCache(cache_path)
        self.session = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def close(self) -> None:
        self.cache.close()
        self.session.close()

    def call(self, endpoint: str, **params: object) -> dict[str, Any]:
        public_params = {key: value for key, value in params.items() if value not in (None, "")}
        public_params.setdefault("DisplayFormat", "true")
        cached = self.cache.get(endpoint, public_params)
        if cached is not None:
            return cached

        request_params = dict(public_params)
        request_params["Key"] = self.api_key
        url = f"{API_ROOT}/{endpoint}"
        cache_response = True
        try:
            response = self.session.get(url, params=request_params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                payload = {"value": payload}
        except (requests.RequestException, ValueError) as error:
            payload = {"_client_error": str(error)}
            cache_response = False
        if cache_response:
            self.cache.put(endpoint, public_params, payload)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return payload

    def display_codes(self, borough: str, codes: Sequence[str]) -> tuple[bool, list[str], dict[str, Any]]:
        borough_code = BOROUGH_CODES[borough]
        params = {f"B10sc{index}": borough_code + code for index, code in enumerate(codes, 1)}
        response = self.call("Function_D", **params)
        names = extract_values(response, ("streetname",))
        # extract_values removes duplicate text. Reconstruct repeated source
        # codes so the output remains aligned with Street Code1-3.
        unique_codes = list(dict.fromkeys(codes))
        if response_succeeded(response) and len(names) >= len(unique_codes):
            code_names = dict(zip(unique_codes, names[: len(unique_codes)]))
            return True, [code_names[code] for code in codes], response
        return False, names, response

    def address(self, borough: str, house_number: str, street_name: str) -> dict[str, Any]:
        return self.call(
            "Function_1E",
            Borough=BOROUGH_CODES[borough],
            AddressNo=house_number,
            StreetName=street_name,
        )

    def intersection(self, borough: str, street1: str, street2: str) -> dict[str, Any]:
        code = BOROUGH_CODES[borough]
        return self.call(
            "Function_2",
            Borough1=code,
            Street1=street1,
            Borough2=code,
            Street2=street2,
        )

    def segment(self, borough: str, names: Sequence[str], stretch: bool = False) -> dict[str, Any]:
        code = BOROUGH_CODES[borough]
        endpoint = "Function_3S" if stretch else "Function_3"
        return self.call(
            endpoint,
            Borough=code if stretch else None,
            Borough1=None if stretch else code,
            Borough2=None if stretch else code,
            Borough3=None if stretch else code,
            OnStreet=names[0],
            FirstCrossStreet=names[1],
            SecondCrossStreet=names[2],
        )


def read_target_rows(raw_file: Path, limit: int, chunksize: int) -> list[SummonsLocation]:
    targets: list[SummonsLocation] = []
    for chunk in pd.read_csv(
        raw_file,
        usecols=SOURCE_COLUMNS,
        dtype=str,
        chunksize=chunksize,
        low_memory=False,
    ):
        # pandas preserves source-file order for usecols, not necessarily the
        # order supplied above. Reorder before positional iteration.
        chunk = chunk[SOURCE_COLUMNS]
        mapped = chunk["Violation County"].map(normalize_county)
        for row in chunk.loc[mapped.isna()].itertuples(index=False, name=None):
            values = dict(zip(SOURCE_COLUMNS, row))
            codes = tuple(
                code
                for code in (
                    normalize_street_code(values["Street Code1"]),
                    normalize_street_code(values["Street Code2"]),
                    normalize_street_code(values["Street Code3"]),
                )
                if code
            )
            if not codes:
                continue
            targets.append(
                SummonsLocation(
                    summons_number=clean_text(values["Summons Number"]),
                    codes=codes,
                    house_number=clean_text(values["House Number"]),
                    street_name=clean_text(values["Street Name"]),
                    violation_location=clean_text(values["Violation Location"]),
                    violation_precinct=clean_text(values["Violation Precinct"]),
                )
            )
            if limit and len(targets) >= limit:
                return targets
    return targets


def build_targeted_index(
    raw_file: Path,
    targets: Sequence[SummonsLocation],
    chunksize: int,
) -> EmpiricalStreetCodeIndex:
    target_codes = {code for target in targets for code in target.codes}
    target_tuples = {target.codes for target in targets}
    index = EmpiricalStreetCodeIndex()
    usecols = ["Street Code1", "Street Code2", "Street Code3", "Violation County"]
    for chunk_number, chunk in enumerate(
        pd.read_csv(raw_file, usecols=usecols, dtype=str, chunksize=chunksize, low_memory=False),
        1,
    ):
        chunk = chunk[usecols]
        for row in chunk.itertuples(index=False, name=None):
            values = dict(zip(usecols, row))
            borough = normalize_county(values["Violation County"])
            if not borough:
                continue
            codes = tuple(
                code
                for code in (
                    normalize_street_code(values["Street Code1"]),
                    normalize_street_code(values["Street Code2"]),
                    normalize_street_code(values["Street Code3"]),
                )
                if code
            )
            if codes in target_tuples or any(code in target_codes for code in codes):
                index.add(borough, codes)
        if chunk_number % 10 == 0:
            LOGGER.info("Indexed %s source rows", f"{chunk_number * chunksize:,}")
    return index


def validate_candidate(
    client: GeoserviceClient,
    target: SummonsLocation,
    borough: str,
) -> dict[str, Any]:
    display_ok, names, display_response = client.display_codes(borough, target.codes)
    result: dict[str, Any] = {
        "borough": borough,
        "display_ok": display_ok,
        "street_names": names,
        "location_ok": False,
        "validation_method": "function_d" if display_ok else "none",
        "latitude": "",
        "longitude": "",
        "grc": ";".join(geosupport_return_codes(display_response)),
    }
    if not display_ok:
        return result

    attempts: list[tuple[str, dict[str, Any]]] = []
    if target.house_number and names:
        attempts.append(("address_1e", client.address(borough, target.house_number, names[0])))
    if not any(response_succeeded(response) for _, response in attempts) and len(names) >= 3:
        attempts.append(("segment_3", client.segment(borough, names[:3])))
        if not response_succeeded(attempts[-1][1]):
            attempts.append(("stretch_3s", client.segment(borough, names[:3], stretch=True)))
    if not any(response_succeeded(response) for _, response in attempts) and len(set(names)) >= 2:
        # For three codes, validate the on-street against each cross street.
        # Trying all pairs also protects the pilot against undocumented source
        # ordering; the benchmark should reveal whether this is too permissive.
        for first, second in combinations(dict.fromkeys(names[:3]), 2):
            response = client.intersection(borough, first, second)
            attempts.append(("intersection_2", response))
            if response_succeeded(response):
                break

    successful = [(method, response) for method, response in attempts if response_succeeded(response)]
    if successful:
        method, response = successful[0]
        result["location_ok"] = True
        result["validation_method"] = method
        result["latitude"] = next(iter(extract_values(response, ("latitude",))), "")
        result["longitude"] = next(iter(extract_values(response, ("longitude",))), "")
        result["grc"] = ";".join(geosupport_return_codes(response))
    return result


def resolve_target(
    target: SummonsLocation,
    plan: CandidatePlan,
    client: GeoserviceClient | None,
) -> dict[str, Any]:
    precinct = precinct_borough(target.violation_precinct)
    ordered = sorted(plan.boroughs, key=lambda borough: borough != precinct)
    if client is None:
        details: list[dict[str, Any]] = []
    else:
        details = [validate_candidate(client, target, borough) for borough in ordered]

    valid = [detail for detail in details if detail["display_ok"]]
    located = [detail for detail in valid if detail["location_ok"]]
    winners = located or valid
    suggested = winners[0]["borough"] if len(winners) == 1 else ""
    winning_detail = winners[0] if len(winners) == 1 else None
    similarity = (
        street_name_similarity(target.street_name, winning_detail["street_names"])
        if winning_detail
        else 0.0
    )
    corroborated = bool(
        suggested
        and (precinct == suggested or similarity >= 0.82 or len(plan.boroughs) == 1)
    )

    if client is None:
        status, confidence = "prepared", ""
    elif len(located) == 1 and len(winners) == 1:
        status, confidence = "accepted", "high"
    elif len(winners) == 1 and corroborated:
        status, confidence = "accepted", "medium"
    elif len(winners) == 1:
        status, confidence = "review", "low"
    elif len(winners) > 1:
        status, confidence = "ambiguous", ""
    else:
        status, confidence = "unmatched", ""

    return {
        "summons_number": target.summons_number,
        "street_codes": "|".join(target.codes),
        "house_number": target.house_number,
        "source_street_name": target.street_name,
        "violation_location": target.violation_location,
        "violation_precinct": target.violation_precinct,
        "precinct_borough": precinct or "",
        "candidate_method": plan.method,
        "candidate_boroughs": "|".join(ordered),
        "validated_boroughs": "|".join(detail["borough"] for detail in winners),
        "suggested_borough": suggested,
        "status": status,
        "confidence": confidence,
        "validation_method": winning_detail["validation_method"] if winning_detail else "",
        "geosupport_street_names": (
            "|".join(winning_detail["street_names"]) if winning_detail else ""
        ),
        "street_name_similarity": round(similarity, 3),
        "latitude": winning_detail["latitude"] if winning_detail else "",
        "longitude": winning_detail["longitude"] if winning_detail else "",
        "candidate_details": json.dumps(details, separators=(",", ":")),
    }


def run(args: argparse.Namespace) -> pd.DataFrame:
    raw_file = Path(args.raw_file)
    if not raw_file.exists():
        raise FileNotFoundError(raw_file)

    LOGGER.info("Collecting missing-borough rows with usable street codes")
    targets = read_target_rows(raw_file, args.limit, args.chunksize)
    LOGGER.info("Collected %s target rows", f"{len(targets):,}")
    if not targets:
        return pd.DataFrame()

    LOGGER.info("Building a targeted borough/code index from known rows")
    index = build_targeted_index(raw_file, targets, args.chunksize)

    client = None
    if not args.prepare_only:
        import os

        load_dotenv()
        api_key = os.getenv("GEOSERVICE_API_KEY", "").strip()
        client = GeoserviceClient(
            api_key=api_key,
            cache_path=Path(args.cache_file),
            delay_seconds=args.delay,
            timeout_seconds=args.timeout,
        )

    rows = []
    try:
        for number, target in enumerate(targets, 1):
            plan = index.candidates(target.codes)
            rows.append(resolve_target(target, plan, client))
            if number % 25 == 0:
                LOGGER.info("Resolved %s of %s targets", f"{number:,}", f"{len(targets):,}")
    finally:
        if client:
            client.close()

    output = pd.DataFrame(rows)
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    LOGGER.info("Wrote %s audit rows to %s", f"{len(output):,}", output_path)
    if not output.empty:
        LOGGER.info("Status counts:\n%s", output["status"].value_counts().to_string())
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate missing parking-summons boroughs through NYC Geosupport."
    )
    parser.add_argument("--raw-file", default=DEFAULT_RAW_FILE)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--cache-file", default=DEFAULT_CACHE_FILE)
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum targets for a safe pilot; use 0 for every eligible row.",
    )
    parser.add_argument("--chunksize", type=int, default=250_000)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Create candidate plans without making API calls or requiring a key.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run(args)


if __name__ == "__main__":
    main()
