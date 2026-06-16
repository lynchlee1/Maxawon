from __future__ import annotations

import unittest

from maxawon.candidate_resolution import (
    CandidateDecision,
    candidate_contains_search_key,
    is_personal_business,
    normalize_company_name,
    resolve_company_candidates,
)


class CandidateResolutionTest(unittest.TestCase):
    def test_detects_personal_business(self) -> None:
        self.assertTrue(is_personal_business({"enpFormNm": "개인기업"}))
        self.assertTrue(is_personal_business({"ipoNm": "개인사업자"}))
        self.assertFalse(is_personal_business({"enpFormNm": "주식회사"}))

    def test_normalizes_maxawon_highlight_tags_and_spaces(self) -> None:
        self.assertEqual("세종텔레콤(주)", normalize_company_name("<!HS>세종텔레콤<!HE> (주)"))

    def test_candidate_must_contain_search_key(self) -> None:
        self.assertTrue(
            candidate_contains_search_key(
                {"enpRegNm": "<!HS>세종텔레콤<!HE>(주)", "enpNm": "<!HS>세종텔레콤<!HE>"},
                "세종텔레콤",
            )
        )
        self.assertFalse(
            candidate_contains_search_key(
                {"enpRegNm": "(주)세종", "enpNm": "<!HS>세종<!HE>"},
                "세종텔레콤",
            )
        )

    def test_unique_after_excluding_personal_businesses(self) -> None:
        resolution = resolve_company_candidates(
            [
                {"enpRegNm": "한신공영", "enpFormNm": "개인기업"},
                {"enpRegNm": "(주)한신공영", "enpFormNm": "주식회사"},
            ],
            search_key="한신공영",
        )

        self.assertEqual(CandidateDecision.UNIQUE, resolution.decision)
        self.assertEqual("(주)한신공영", resolution.selected["enpRegNm"])

    def test_needs_user_choice_when_multiple_corporate_candidates_remain(self) -> None:
        resolution = resolve_company_candidates(
            [
                {"enpRegNm": "세종텔레콤(주)", "enpFormNm": "주식회사"},
                {"enpRegNm": "(주)세종텔레콤", "enpFormNm": "주식회사"},
                {"enpRegNm": "세종텔레콤", "enpFormNm": "개인기업"},
            ],
            search_key="세종텔레콤",
        )

        self.assertEqual(CandidateDecision.NEEDS_USER_CHOICE, resolution.decision)
        self.assertIsNone(resolution.selected)
        self.assertEqual(2, len(resolution.candidates))

    def test_no_match_when_only_personal_businesses_remain(self) -> None:
        resolution = resolve_company_candidates(
            [{"enpRegNm": "세종텔레콤", "enpFormNm": "개인기업"}],
            search_key="세종텔레콤",
        )

        self.assertEqual(CandidateDecision.NO_MATCH, resolution.decision)
        self.assertEqual([], resolution.candidates)

    def test_search_key_excludes_broader_name(self) -> None:
        resolution = resolve_company_candidates(
            [
                {"enpRegNm": "세종텔레콤(주)", "enpFormNm": "주식회사"},
                {"enpRegNm": "(주)세종", "enpFormNm": "주식회사"},
            ],
            search_key="세종텔레콤",
        )

        self.assertEqual(CandidateDecision.UNIQUE, resolution.decision)
        self.assertEqual("세종텔레콤(주)", resolution.selected["enpRegNm"])


if __name__ == "__main__":
    unittest.main()
