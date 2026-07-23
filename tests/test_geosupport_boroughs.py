from __future__ import annotations

import unittest

from nycparking.geocoding.geosupport_boroughs import (
    CandidatePlan,
    EmpiricalStreetCodeIndex,
    SummonsLocation,
    geosupport_return_codes,
    normalize_street_code,
    precinct_borough,
    resolve_target,
    response_succeeded,
    street_name_similarity,
)


class StreetCodeTests(unittest.TestCase):
    def test_normalizes_lost_leading_zeroes(self) -> None:
        self.assertEqual(normalize_street_code("1234"), "01234")
        self.assertEqual(normalize_street_code("1234.0"), "01234")
        self.assertEqual(normalize_street_code("0"), "")
        self.assertEqual(normalize_street_code("not a code"), "")

    def test_precinct_ranges(self) -> None:
        self.assertEqual(precinct_borough("7"), "Manhattan")
        self.assertEqual(precinct_borough("48"), "Bronx")
        self.assertEqual(precinct_borough("79"), "Brooklyn")
        self.assertEqual(precinct_borough("109"), "Queens")
        self.assertEqual(precinct_borough("120"), "Staten Island")
        self.assertEqual(precinct_borough("116"), "Queens")
        self.assertIsNone(precinct_borough("4"))
        self.assertIsNone(precinct_borough("51"))
        self.assertIsNone(precinct_borough("0"))

    def test_exact_tuple_precedes_individual_codes(self) -> None:
        index = EmpiricalStreetCodeIndex()
        index.add("Brooklyn", ("21230", "40404", "40404"))
        index.add("Queens", ("21230", "99999"))
        plan = index.candidates(("21230", "40404", "40404"))
        self.assertEqual(plan.boroughs[0], "Brooklyn")
        self.assertEqual(set(plan.boroughs), {"Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"})
        self.assertEqual(plan.method, "exact_code_tuple_ranked")

    def test_street_name_similarity_normalizes_suffixes(self) -> None:
        self.assertEqual(street_name_similarity("FULTON STREET", ["FULTON ST"]), 1.0)


class ResponseTests(unittest.TestCase):
    def test_nested_grc_success(self) -> None:
        response = {"display": {"Geosupport Return Code (GRC)": "00"}}
        self.assertEqual(geosupport_return_codes(response), ["00"])
        self.assertTrue(response_succeeded(response))

    def test_grc_error(self) -> None:
        self.assertFalse(response_succeeded({"GRC": "64", "Message": "INVALID"}))
        self.assertFalse(response_succeeded({"_client_error": "timeout"}))

    def test_prepare_only_never_accepts_a_borough(self) -> None:
        index = EmpiricalStreetCodeIndex()
        index.add("Brooklyn", ("21230",))
        target = SummonsLocation("1", ("21230",), "", "FULTON ST", "", "79")
        result = resolve_target(target, index.candidates(target.codes), None)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["suggested_borough"], "")

    def test_matching_precinct_fields_are_accepted_without_codes(self) -> None:
        target = SummonsLocation("2", (), "", "", "7", "7")
        result = resolve_target(
            target,
            CandidatePlan(("Manhattan",), "precinct_only"),
            object(),
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["suggested_borough"], "Manhattan")
        self.assertEqual(result["validation_method"], "precinct")

    def test_conflicting_precinct_fields_require_review(self) -> None:
        target = SummonsLocation("3", (), "", "", "40", "7")
        result = resolve_target(
            target,
            CandidatePlan(("Manhattan", "Bronx"), "precinct_only"),
            object(),
        )
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["suggested_borough"], "")


if __name__ == "__main__":
    unittest.main()
