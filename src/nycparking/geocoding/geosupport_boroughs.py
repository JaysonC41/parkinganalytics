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
import os
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
DEFAULT_GEOSUPPORT_PATH = Path(
    os.getenv(
        "GEOSUPPORT_PATH",
        Path.home() / "AppData/Local/Programs/Geosupport Desktop Edition",
    )
)

BOROUGH_CODES = {
    "Manhattan": "1",
    "Bronx": "2",
    "Brooklyn": "3",
    "Queens": "4",
    "Staten Island": "5",
}
CODE_TO_BOROUGH = {code: borough for borough, code in BOROUGH_CODES.items()}
ALL_BOROUGHS = tuple(BOROUGH_CODES)

PRECINCTS_BY_BOROUGH = {
    "Manhattan": {1, 5, 6, 7, 9, 10, 13, 14, 17, 18, 19, 20, 22, 23, 24, 25, 26, 28, 30, 32, 33, 34},
    "Bronx": {40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 52},
    "Brooklyn": {60, 61, 62, 63, 66, 67, 68, 69, 70, 71, 72, 73, 75, 76, 77, 78, 79, 81, 83, 84, 88, 90, 94},
    "Queens": {100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116},
    "Staten Island": {120, 121, 122, 123},
}
PRECINCT_TO_BOROUGH = {
    precinct: borough
    for borough, precincts in PRECINCTS_BY_BOROUGH.items()
    for precinct in precincts
}

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


def valid_street_name(value: object) -> bool:
    text = clean_text(value)
    return bool(text and set(text) != {"?"})


def precinct_borough(value: object) -> str | None:
    try:
        precinct = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    return PRECINCT_TO_BOROUGH.get(precinct)


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

    def address(
        self, borough: str, house_number: str, street_name: str, street_code: str = ""
    ) -> dict[str, Any]:
        return self.call(
            "Function_1E",
            Borough=BOROUGH_CODES[borough],
            AddressNo=house_number,
            StreetName=street_name,
        )

    def street_name(self, borough: str, street_name: str) -> dict[str, Any]:
        return self.call(
            "Function_1N",
            Borough=BOROUGH_CODES[borough],
            StreetName=street_name,
        )

    def intersection(
        self,
        borough: str,
        street1: str,
        street2: str,
        street_codes: Sequence[str] = (),
    ) -> dict[str, Any]:
        code = BOROUGH_CODES[borough]
        return self.call(
            "Function_2",
            Borough1=code,
            Street1=street1,
            Borough2=code,
            Street2=street2,
        )

    def segment(
        self,
        borough: str,
        names: Sequence[str],
        stretch: bool = False,
        street_codes: Sequence[str] = (),
    ) -> dict[str, Any]:
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


class LocalGeosupportClient:
    """Use the installed Geosupport Desktop engine through python-geosupport."""

    def __init__(self, geosupport_path: Path) -> None:
        from geosupport import Geosupport

        if not geosupport_path.exists():
            raise FileNotFoundError(
                f"Geosupport Desktop directory not found: {geosupport_path}"
            )
        self.geo = Geosupport(geosupport_path=str(geosupport_path))
        for logger_name in ("geosupport", "geosupport.geosupport"):
            package_logger = logging.getLogger(logger_name)
            package_logger.disabled = True
            package_logger.propagate = False
        self._display_cache: dict[
            tuple[str, tuple[str, ...]], tuple[bool, list[str], dict[str, Any]]
        ] = {}
        self._code_cache: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        self._location_cache: dict[tuple[object, ...], dict[str, Any]] = {}

    @staticmethod
    def _error_result(error: Exception) -> dict[str, Any]:
        result = getattr(error, "result", None)
        if isinstance(result, dict) and result:
            return result
        return {"_client_error": str(error)}

    def _call(self, function: str, **kwargs: object) -> dict[str, Any]:
        try:
            return self.geo[function](**kwargs)
        except Exception as error:  # GeosupportError retains parsed output.
            return self._error_result(error)

    def close(self) -> None:
        return None

    def display_codes(
        self, borough: str, codes: Sequence[str]
    ) -> tuple[bool, list[str], dict[str, Any]]:
        cache_key = (borough, tuple(codes))
        cached = self._display_cache.get(cache_key)
        if cached is not None:
            return cached
        borough_code = BOROUGH_CODES[borough]
        names: list[str] = []
        responses: list[dict[str, Any]] = []
        for code in codes:
            code_key = (borough, code)
            cached_code = self._code_cache.get(code_key)
            if cached_code is not None:
                name, response = cached_code
                names.append(name)
                responses.append(response)
                continue
            response = self._call("D", b5sc=borough_code + code)
            responses.append(response)
            extracted = extract_values(response, ("firststreetnamenormalized",))
            name = extracted[0] if extracted and valid_street_name(extracted[0]) else ""
            names.append(name)
            self._code_cache[code_key] = (name, response)
        # Street Code1 is the summons's on-street code. Cross-street fillers
        # may be invalid, so they do not invalidate an otherwise usable row.
        result = (
            bool(names and valid_street_name(names[0])),
            names,
            {
                "responses": responses,
                "Geosupport Return Code (GRC)": (
                    "00" if names and valid_street_name(names[0]) else "64"
                ),
            },
        )
        self._display_cache[cache_key] = result
        return result

    def address(
        self, borough: str, house_number: str, street_name: str, street_code: str = ""
    ) -> dict[str, Any]:
        b5sc = BOROUGH_CODES[borough] + street_code
        key = ("1E", b5sc, house_number)
        if key not in self._location_cache:
            self._location_cache[key] = self._call(
                "1E", b5sc=b5sc, house_number=house_number, mode="extended"
            )
        return self._location_cache[key]

    def street_name(self, borough: str, street_name: str) -> dict[str, Any]:
        borough_code = BOROUGH_CODES[borough]
        key = ("1N", borough_code, street_name.upper())
        if key not in self._location_cache:
            self._location_cache[key] = self._call(
                "1N",
                borough=borough_code,
                street_name=street_name,
            )
        return self._location_cache[key]

    def intersection(
        self,
        borough: str,
        street1: str,
        street2: str,
        street_codes: Sequence[str] = (),
    ) -> dict[str, Any]:
        borough_code = BOROUGH_CODES[borough]
        b5scs = tuple(borough_code + code for code in street_codes[:2])
        if len(b5scs) == 2:
            key = ("2",) + b5scs
            kwargs: dict[str, object] = {
                "b5sc": b5scs[0],
                "b5sc_2": b5scs[1],
                "cross_street_names": True,
            }
        else:
            key = ("2N", borough_code, street1.upper(), street2.upper())
            kwargs = {
                "borough": borough_code,
                "street_name": street1,
                "borough_2": borough_code,
                "street_name_2": street2,
                "cross_street_names": True,
            }
        if key not in self._location_cache:
            self._location_cache[key] = self._call("2", **kwargs)
        return self._location_cache[key]

    def segment(
        self,
        borough: str,
        names: Sequence[str],
        stretch: bool = False,
        street_codes: Sequence[str] = (),
    ) -> dict[str, Any]:
        borough_code = BOROUGH_CODES[borough]
        b5scs = tuple(borough_code + code for code in street_codes[:3])
        function = "3S" if stretch else "3"
        key = (function,) + b5scs
        if key not in self._location_cache:
            kwargs = {"b5sc": b5scs[0], "b5sc_2": b5scs[1], "b5sc_3": b5scs[2]}
            if not stretch:
                kwargs["mode"] = "extended"
                kwargs["cross_street_names"] = True
            self._location_cache[key] = self._call(function, **kwargs)
        return self._location_cache[key]


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
            precinct = precinct_borough(values["Violation Precinct"])
            location = precinct_borough(values["Violation Location"])
            if not codes and not (precinct or location):
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
    client: GeoserviceClient | LocalGeosupportClient,
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
    if target.house_number and names and valid_street_name(names[0]):
        attempts.append(
            (
                "address_1e",
                client.address(borough, target.house_number, names[0], target.codes[0]),
            )
        )
    if (
        not any(response_succeeded(response) for _, response in attempts)
        and len(names) >= 3
        and all(valid_street_name(name) for name in names[:3])
    ):
        attempts.append(
            ("segment_3", client.segment(borough, names[:3], street_codes=target.codes[:3]))
        )
        if not response_succeeded(attempts[-1][1]):
            attempts.append(
                (
                    "stretch_3s",
                    client.segment(
                        borough,
                        names[:3],
                        stretch=True,
                        street_codes=target.codes[:3],
                    ),
                )
            )
    if not any(response_succeeded(response) for _, response in attempts):
        # For three codes, validate the on-street against each cross street.
        # Trying all pairs also protects the pilot against undocumented source
        # ordering; the benchmark should reveal whether this is too permissive.
        unique_locations = list(
            dict.fromkeys(
                (name, code)
                for name, code in zip(names[:3], target.codes[:3])
                if valid_street_name(name)
            )
        )
        for (first, code1), (second, code2) in combinations(unique_locations, 2):
            response = client.intersection(
                borough, first, second, street_codes=(code1, code2)
            )
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
    client: GeoserviceClient | LocalGeosupportClient | None,
) -> dict[str, Any]:
    precinct = precinct_borough(target.violation_precinct)
    location_borough = precinct_borough(target.violation_location)
    precinct_conflict = bool(
        precinct and location_borough and precinct != location_borough
    )
    precinct_signal = None if precinct_conflict else (precinct or location_borough)
    ordered = sorted(plan.boroughs, key=lambda borough: borough != precinct_signal)
    if client is None or not target.codes:
        details: list[dict[str, Any]] = []
    else:
        details = [validate_candidate(client, target, borough) for borough in ordered]

    valid = [detail for detail in details if detail["display_ok"]]
    located = [detail for detail in valid if detail["location_ok"]]
    winners = located or valid
    if not located and len(valid) > 1:
        scored = []
        for detail in valid:
            similarity_score = street_name_similarity(
                target.street_name, detail["street_names"]
            )
            evidence_score = int(detail["borough"] == precinct) + int(
                similarity_score >= 0.82
            )
            scored.append((evidence_score, similarity_score, detail))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if scored[0][0] > 0 and (
            len(scored) == 1 or scored[0][:2] > scored[1][:2]
        ):
            winners = [scored[0][2]]
    geosupport_suggested = winners[0]["borough"] if len(winners) == 1 else ""
    winning_detail = winners[0] if len(winners) == 1 else None
    suggested = geosupport_suggested
    similarity = (
        street_name_similarity(target.street_name, winning_detail["street_names"])
        if winning_detail
        else 0.0
    )
    corroborated = bool(
        suggested
        and (
            precinct_signal == suggested
            or similarity >= 0.82
            or len(plan.boroughs) == 1
        )
    )
    validation_method = winning_detail["validation_method"] if winning_detail else ""

    if client is None:
        status, confidence = "prepared", ""
    elif precinct_conflict:
        suggested = ""
        winning_detail = None
        status, confidence = "review", "low"
        validation_method = "precinct_fields_conflict"
    elif precinct_signal:
        matching_detail = next(
            (detail for detail in valid if detail["borough"] == precinct_signal),
            None,
        )
        strong_geosupport_conflict = bool(
            geosupport_suggested
            and geosupport_suggested != precinct_signal
            and len(winners) == 1
        )
        suggested = precinct_signal
        winning_detail = matching_detail
        if strong_geosupport_conflict:
            status, confidence = "review", "low"
            validation_method = "precinct_geosupport_conflict"
        else:
            status = "accepted"
            confidence = (
                "high" if precinct and location_borough == precinct else "medium"
            )
            if matching_detail and matching_detail["location_ok"]:
                validation_method = f"precinct+{matching_detail['validation_method']}"
            else:
                validation_method = "precinct"
        similarity = (
            street_name_similarity(target.street_name, matching_detail["street_names"])
            if matching_detail
            else 0.0
        )
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
        "violation_location_borough": location_borough or "",
        "candidate_method": plan.method,
        "candidate_boroughs": "|".join(ordered),
        "display_valid_boroughs": "|".join(detail["borough"] for detail in valid),
        "validated_boroughs": (
            suggested
            if precinct_signal and suggested
            else "|".join(detail["borough"] for detail in winners)
        ),
        "suggested_borough": suggested,
        "status": status,
        "confidence": confidence,
        "validation_method": validation_method,
        "geosupport_street_names": (
            "|".join(name for name in winning_detail["street_names"] if name)
            if winning_detail
            else ""
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

    LOGGER.info("Collecting missing-borough rows with street-code or precinct evidence")
    targets = read_target_rows(raw_file, args.limit, args.chunksize)
    LOGGER.info("Collected %s target rows", f"{len(targets):,}")
    if not targets:
        return pd.DataFrame()

    LOGGER.info("Building a targeted borough/code index from known rows")
    index = build_targeted_index(raw_file, targets, args.chunksize)

    client: GeoserviceClient | LocalGeosupportClient | None = None
    if not args.prepare_only:
        if args.backend == "local":
            client = LocalGeosupportClient(Path(args.geosupport_path))
            LOGGER.info("Using local Geosupport Desktop at %s", args.geosupport_path)
        else:
            load_dotenv()
            api_key = os.getenv("GEOSERVICE_API_KEY", "").strip()
            client = GeoserviceClient(
                api_key=api_key,
                cache_path=Path(args.cache_file),
                delay_seconds=args.delay,
                timeout_seconds=args.timeout,
            )
            LOGGER.info("Using remote NYC Geoservice API")

    rows = []
    try:
        for number, target in enumerate(targets, 1):
            precinct_signal = precinct_borough(target.violation_precinct) or precinct_borough(
                target.violation_location
            )
            if not target.codes and precinct_signal:
                plan = CandidatePlan((precinct_signal,), "precinct_only")
            else:
                plan = index.candidates(target.codes)
            rows.append(resolve_target(target, plan, client))
            if number % 500 == 0:
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
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Validate missing parking-summons boroughs through NYC Geosupport."
    )
    parser.add_argument("--raw-file", default=DEFAULT_RAW_FILE)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--cache-file", default=DEFAULT_CACHE_FILE)
    parser.add_argument(
        "--backend",
        choices=("local", "api"),
        default="local",
        help="Geosupport Desktop is the default; use api for the REST fallback.",
    )
    parser.add_argument(
        "--geosupport-path",
        default=os.getenv("GEOSUPPORT_PATH", str(DEFAULT_GEOSUPPORT_PATH)),
    )
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
