from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from nycparking.source_data import ensure_parking_source


class SourceDataTests(unittest.TestCase):
    def test_downloads_verifies_and_extracts_release_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.zip"
            content = b"summons_number,borough\n1,Queens\n"
            with ZipFile(fixture, "w", ZIP_DEFLATED) as archive:
                archive.writestr("nycparking2025.csv", content)

            expected_sha256 = hashlib.sha256(fixture.read_bytes()).hexdigest()
            project = root / "project"
            result = ensure_parking_source(
                project,
                asset_url=fixture.as_uri(),
                expected_sha256=expected_sha256,
                expected_size=len(content),
            )

            self.assertEqual(result.read_bytes(), content)
            self.assertFalse(
                (project / "data/raw/nycparking2025.csv.zip").exists()
            )

    def test_existing_source_does_not_download_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "data/raw/nycparking2025.csv"
            source.parent.mkdir(parents=True)
            source.write_text("already present", encoding="utf-8")

            result = ensure_parking_source(
                project,
                asset_url="https://example.invalid/must-not-run.zip",
            )

            self.assertEqual(result, source.resolve())
            self.assertEqual(source.read_text(encoding="utf-8"), "already present")


if __name__ == "__main__":
    unittest.main()
