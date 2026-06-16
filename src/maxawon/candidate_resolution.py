from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


PERSONAL_BUSINESS_FORMS = ("개인기업",)
PERSONAL_BUSINESS_IPO_NAMES = ("개인사업자",)


class CandidateDecision(str, Enum):
    NO_MATCH = "no_match"
    UNIQUE = "unique"
    NEEDS_USER_CHOICE = "needs_user_choice"


@dataclass(frozen=True)
class CandidateResolution:
    decision: CandidateDecision
    candidates: list[dict[str, Any]]
    selected: dict[str, Any] | None = None


def normalize_company_name(value: Any) -> str:
    return (
        str(value or "")
        .replace("<!HS>", "")
        .replace("<!HE>", "")
        .replace(" ", "")
        .strip()
    )


def is_personal_business(candidate: dict[str, Any]) -> bool:
    form_name = str(candidate.get("enpFormNm") or "").strip()
    ipo_name = str(candidate.get("ipoNm") or "").strip()
    return form_name in PERSONAL_BUSINESS_FORMS or ipo_name in PERSONAL_BUSINESS_IPO_NAMES


def candidate_contains_search_key(candidate: dict[str, Any], search_key: str | None) -> bool:
    if not search_key:
        return True

    normalized_key = normalize_company_name(search_key)
    candidate_names = (
        normalize_company_name(candidate.get("enpRegNm")),
        normalize_company_name(candidate.get("enpNm")),
    )
    return any(normalized_key in name for name in candidate_names)


def resolve_company_candidates(
    candidates: list[dict[str, Any]],
    search_key: str | None = None,
) -> CandidateResolution:
    corporate_candidates = [
        candidate
        for candidate in candidates
        if not is_personal_business(candidate)
        and candidate_contains_search_key(candidate, search_key)
    ]

    if not corporate_candidates:
        return CandidateResolution(CandidateDecision.NO_MATCH, [])

    if len(corporate_candidates) == 1:
        return CandidateResolution(
            CandidateDecision.UNIQUE,
            corporate_candidates,
            selected=corporate_candidates[0],
        )

    return CandidateResolution(
        CandidateDecision.NEEDS_USER_CHOICE,
        corporate_candidates,
    )
