"""Refixing-related extraction.

Output columns:
- 리픽싱가격
- 리픽싱주가
- 리픽싱내용

Stability:
- mixed: table-driven first, regex fallback for narrative text
"""

import re


REFIX_FLOOR_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*이상(?:이어야\s*(?:한다|된다)|으로\s*한다)"
)
REFIX_PERIOD_PATTERNS = [
    re.compile(
        r"매\s*(\d+)\s*(?:개)?\s*월(?!\s*가중산술평균주가)"
        r"(?:마다|이\s*경과한\s*날|에\s*해당(?:하는|되는)\s*날)?"
    ),
    re.compile(r"발행(?:일|후)?(?:로부터)?\s*(\d+)\s*(?:개)?\s*월이\s*경과한\s*날"),
]


def _extract_refixing_period_months(refix_text):
    text = refix_text or ""
    for pattern in REFIX_PERIOD_PATTERNS:
        for match in pattern.finditer(text):
            value = int(match.group(1))
            if 0 < value <= 60:
                return value
    return None


def populate_initial_refixing_fields(result_dict):
    if "리픽싱가격" not in result_dict:
        result_dict["리픽싱가격"] = "-"
    if "리픽싱주가" not in result_dict:
        result_dict["리픽싱주가"] = "-"
    if "리픽싱내용" not in result_dict:
        result_dict["리픽싱내용"] = "-"

    try:
        result_dict["리픽싱가격"] = f"{round(100 * result_dict['리픽싱가격'] / result_dict['전환가액(원)'], 0)}%"
    except Exception:
        result_dict["리픽싱가격"] = "-"


def populate_refixing_from_text_if_missing(result_dict, document_text):
    refix_text = result_dict.pop("_리픽싱원문", None) or document_text
    floor_missing = result_dict.get("리픽싱가격") in (None, "", "-")
    period_missing = result_dict.get("리픽싱주가") in (None, "", "-")

    if floor_missing:
        floor_match = REFIX_FLOOR_PATTERN.search(refix_text)
        if floor_match:
            result_dict["리픽싱가격"] = float(floor_match.group(1))

    if period_missing:
        period_months = _extract_refixing_period_months(refix_text)
        if period_months is not None:
            result_dict["리픽싱주가"] = period_months
