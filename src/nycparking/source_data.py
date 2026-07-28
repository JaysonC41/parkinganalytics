"""Download and verify the packaged FY2025 parking source dataset."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile


ASSET_NAME = "nycparking2025.csv.zip"
SOURCE_NAME = "nycparking2025.csv"
RELEASE_TAG = "data-v1"
RELEASE_URL = (
    "https://github.com/JaysonC41/parkinganalytics/releases/download/"
    f"{RELEASE_TAG}/{ASSET_NAME}"
)
ASSET_SHA256 = "067f6de33121fee1a65704d315f0c7ec81c2e9a4e682b1a8f0535c4c6d7e16be"
SOURCE_SIZE = 1_310_711_350
COPY_CHUNK_SIZE = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_archive(
    url: str,
    destination: Path,
    expected_sha256: str,
) -> Path:
    """Stream a release asset to disk and reject an unexpected checksum."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = Request(
        url,
        headers={"User-Agent": "nyc-parking-analytics-source-downloader"},
    )

    try:
        with urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, COPY_CHUNK_SIZE)

        actual_sha256 = sha256_file(partial)
        if actual_sha256.lower() != expected_sha256.lower():
            raise ValueError(
                "Downloaded source archive failed SHA-256 verification. "
                f"Expected {expected_sha256}; received {actual_sha256}."
            )
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()

    return destination


def extract_source(
    archive_path: Path,
    destination: Path,
    expected_size: int = SOURCE_SIZE,
) -> Path:
    """Extract the one expected CSV and replace the destination atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")

    try:
        with ZipFile(archive_path) as archive:
            members = archive.namelist()
            if members != [SOURCE_NAME]:
                raise ValueError(
                    f"Unexpected archive contents: {members!r}; "
                    f"expected only {SOURCE_NAME!r}."
                )
            with archive.open(SOURCE_NAME) as source, partial.open("wb") as output:
                shutil.copyfileobj(source, output, COPY_CHUNK_SIZE)

        if expected_size and partial.stat().st_size != expected_size:
            raise ValueError(
                "Extracted source has an unexpected size. "
                f"Expected {expected_size:,} bytes; "
                f"received {partial.stat().st_size:,}."
            )
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()

    return destination


def ensure_parking_source(
    project_root: Path,
    *,
    force: bool = False,
    asset_url: str = RELEASE_URL,
    expected_sha256: str = ASSET_SHA256,
    expected_size: int = SOURCE_SIZE,
    keep_archive: bool = False,
) -> Path:
    """Return the raw CSV, downloading the verified release asset if needed."""
    project_root = Path(project_root).resolve()
    source_path = project_root / "data" / "raw" / SOURCE_NAME
    archive_path = project_root / "data" / "raw" / ASSET_NAME

    if source_path.exists() and not force:
        print(f"Source data already exists: {source_path}")
        return source_path

    if force and source_path.exists():
        source_path.unlink()

    print(f"Downloading {ASSET_NAME} from GitHub Releases...")
    download_archive(asset_url, archive_path, expected_sha256)
    print("Checksum passed. Extracting the source CSV...")
    extract_source(archive_path, source_path, expected_size)

    if not keep_archive:
        archive_path.unlink()

    print(f"Source data ready: {source_path}")
    return source_path
