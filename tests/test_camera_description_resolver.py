from __future__ import annotations

import unittest

from nycparking.geocoding.camera_description_resolver import (
    apply_browse_result,
    parse_camera_description,
    resolve_description,
)


class FakeClient:
    def __init__(
        self,
        intersection_boroughs: set[str] | None = None,
        street_boroughs: set[str] | None = None,
    ) -> None:
        self.intersection_boroughs = intersection_boroughs or set()
        self.street_boroughs = street_boroughs or set()

    @staticmethod
    def _response(success: bool) -> dict[str, str]:
        return {
            "Geosupport Return Code (GRC)": "00" if success else "42",
            "First Street Name Normalized": "MELROSE AVENUE",
        }

    def intersection(
        self,
        borough: str,
        street1: str,
        street2: str,
    ) -> dict[str, str]:
        return self._response(borough in self.intersection_boroughs)

    def street_name(self, borough: str, street_name: str) -> dict[str, str]:
        return self._response(borough in self.street_boroughs)


class CameraDescriptionParsingTests(unittest.TestCase):
    def test_parses_direction_and_intersection(self) -> None:
        parsed = parse_camera_description("SB Melrose Ave @ E 161 St")
        self.assertEqual(parsed.direction, "SB")
        self.assertEqual(parsed.on_street, "MELROSE AVE")
        self.assertEqual(parsed.cross_street, "E 161 ST")

    def test_removes_parenthesized_traffic_direction(self) -> None:
        parsed = parse_camera_description("NARROWS RD S (E/B) @")
        self.assertEqual(parsed.direction, "")
        self.assertEqual(parsed.on_street, "NARROWS RD S")
        self.assertEqual(parsed.cross_street, "")


class CameraDescriptionResolutionTests(unittest.TestCase):
    def test_exact_known_description_is_high_confidence(self) -> None:
        result = resolve_description(
            parse_camera_description("SB Melrose Ave @ E 161 St"),
            known_borough="Bronx",
            known_borough_count=1,
            known_total=20,
            known_boroughs="Bronx:20",
            client=FakeClient(),
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["suggested_borough"], "Bronx")
        self.assertEqual(result["resolution_method"], "known_exact_description")

    def test_unique_intersection_is_high_confidence(self) -> None:
        result = resolve_description(
            parse_camera_description("SB Melrose Ave @ E 161 St"),
            known_borough="",
            known_borough_count=0,
            known_total=0,
            known_boroughs="",
            client=FakeClient(intersection_boroughs={"Bronx"}),
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["suggested_borough"], "Bronx")
        self.assertEqual(
            result["resolution_method"],
            "parsed_intersection_function_2",
        )

    def test_unique_street_is_medium_confidence(self) -> None:
        result = resolve_description(
            parse_camera_description("SB Southern Blvd @"),
            known_borough="",
            known_borough_count=0,
            known_total=0,
            known_boroughs="",
            client=FakeClient(street_boroughs={"Bronx"}),
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["confidence"], "medium")
        self.assertEqual(result["suggested_borough"], "Bronx")
        self.assertEqual(result["resolution_method"], "unique_street_function_1n")

    def test_multiple_street_boroughs_remain_ambiguous(self) -> None:
        result = resolve_description(
            parse_camera_description("10TH AVE"),
            known_borough="",
            known_borough_count=0,
            known_total=0,
            known_boroughs="",
            client=FakeClient(street_boroughs={"Manhattan", "Brooklyn"}),
        )
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["suggested_borough"], "")

    def test_unique_browse_intersection_is_accepted(self) -> None:
        result = apply_browse_result(
            {
                "status": "ambiguous",
                "suggested_borough": "",
                "confidence": "",
                "resolution_method": "street_multiple_boroughs",
            },
            {"Manhattan": ["AMSTERDAM AVENUE"]},
            corridor_borough="Manhattan",
            corridor_summons=100,
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["suggested_borough"], "Manhattan")
        self.assertEqual(result["confidence"], "medium")

    def test_browse_and_corridor_conflict_requires_review(self) -> None:
        result = apply_browse_result(
            {
                "status": "ambiguous",
                "suggested_borough": "",
                "confidence": "",
                "resolution_method": "street_multiple_boroughs",
            },
            {"Manhattan": ["WILLIAM BURKE FDNY STREET"]},
            corridor_borough="Bronx",
            corridor_summons=21,
        )
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["suggested_borough"], "")
        self.assertEqual(
            result["resolution_method"],
            "browse_intersection_corridor_conflict",
        )


if __name__ == "__main__":
    unittest.main()
