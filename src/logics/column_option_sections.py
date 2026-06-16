"""Option-section and call-cap extraction.

Output columns:
- 옵션구역분리
- PUT옵션본문
- CALL옵션본문
- CALL행사한도(%)
- CALL행사한도판정

Stability:
- heuristic: heading-based section slicing and numeric extraction
"""

import re


PUT_SECTION_HEADING_PATTERNS = [
    re.compile(
        r"(?:^|\s)(?:\d+\.\s*)?(?:사채권자\s*)?조기상환청구권\s*\(\s*Put Option\s*\)\s*[:：]",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\s)\[\s*조기상환청구권\s*\(\s*Put Option\s*\)\s*\]",
        re.IGNORECASE,
    ),
]
CALL_SECTION_HEADING_PATTERNS = [
    re.compile(
        r"(?:^|\s)(?:\d+(?:-\d+)?\.?\s*)?(?:옵션에 관한 사항\s*)?매도청구권\s*\(\s*Call Option\s*\)\s*에?\s*관한\s*사항",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\s)(?:\d+\.\s*)?(?:발행회사\s*)?매도청구권\s*\(\s*Call Option\s*\)\s*[:：]",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\s)\[\s*콜옵션[^\]]*\]",
        re.IGNORECASE,
    ),
]
TOP_LEVEL_SECTION_BOUNDARY_PATTERN = re.compile(r"\b(?:10|11|12|13|14|15|16|17|18|19|20|21|22|23)\.\s")

CALL_CAP_PATTERNS = [
    re.compile(
        r"취득규모\s*[:：][^()\n]{0,80}\(\s*(?:Call\s*Option|콜옵션)\s*([0-9]{1,3}(?:\.\d+)?)\s*%\s*\)",
        re.IGNORECASE,
    ),
    re.compile(r"행사비율\s*[:：]\s*([0-9]{1,3}(?:\.\d+)?)\s*%"),
    re.compile(r"사채원금의\s*([0-9]{1,3}(?:\.\d+)?)\s*%"),
    re.compile(r"원금에\s*해당(?:되는|하는)?\s*금액의\s*([0-9]{1,3}(?:\.\d+)?)\s*%"),
    re.compile(r"최대\s*권면총액의\s*([0-9]{1,3}(?:\.\d+)?)\s*%\s*한도"),
    re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%\s*를\s*초과하여\s*매도청구권을\s*행사할\s*수\s*없"),
    re.compile(r"매도청구권[^\n]{0,120}?([0-9]{1,3}(?:\.\d+)?)\s*%\s*한도"),
    re.compile(r"권면(?:총)?액(?:의)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%\s*를\s*초과하지\s*않는\s*범위"),
    re.compile(r"발행(?:가액|금액)\s*총액(?:\s*\(전자등록총액\))?(?:의)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%"),
    re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%\s*\(?(?:이하)?\s*[\"“”']?매도청구권\s*행사가능수량"),
    re.compile(r"(?:본\s*사채(?:총액|의\s*원금|의\s*발행가액)?|전자등록총액|권면총액)\s*(?:중|의)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%"),
    re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%\s*(?:까지|에\s*대하여)\s*매도청구권(?:을)?\s*행사"),
    re.compile(r"총\s*한도(?:로)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%\s*(?:를|로)?\s*매도청구권(?:을)?\s*행사"),
    re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%\s*를?\s*총\s*한도(?:로)?\s*매도청구권(?:을)?\s*행사"),
]
CALL_CAP_CONTEXT_PATTERNS = [
    re.compile(
        r"(?:옵션\s*사항\s*\(\s*Call\s*Option\s*\)|매도청구권|중도상환청구권|Call\s*Option에\s*관한\s*사항)"
        r".{0,360}?취득규모\s*[:：][^()\n]{0,80}\(\s*(?:Call\s*Option|콜옵션)\s*([0-9]{1,3}(?:\.\d+)?)\s*%\s*\)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:옵션\s*사항\s*\(\s*Call\s*Option\s*\)|매도청구권|중도상환청구권|Call\s*Option에\s*관한\s*사항)"
        r".{0,220}?행사비율\s*[:：]\s*([0-9]{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:옵션\s*사항\s*\(\s*Call\s*Option\s*\)|매도청구권|중도상환청구권|Call\s*Option에\s*관한\s*사항)"
        r".{0,220}?사채원금의\s*([0-9]{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:매도청구권|콜옵션|Call\s*Option).{0,220}?"
        r"(?:발행(?:가액|금액)\s*총액|권면(?:총)?액)(?:의)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:발행(?:가액|금액)\s*총액|권면(?:총)?액)(?:의)?\s*([0-9]{1,3}(?:\.\d+)?)\s*%.{0,180}?"
        r"(?:매도청구권|콜옵션|Call\s*Option)",
        re.IGNORECASE | re.DOTALL,
    ),
]

CALL_CAP_RESOLUTION_EXPLICIT = "explicit_numeric"
CALL_CAP_RESOLUTION_EXPLICIT_CONTEXT = "explicit_numeric_context"
CALL_CAP_RESOLUTION_REGULATORY_DEFAULT_ZERO = "regulatory_default_zero"
CALL_CAP_RESOLUTION_UNRESOLVED = "unresolved_missing_numeric"

CALL_CAP_REGULATION_DEFAULT_ZERO_PATTERN = re.compile(
    r"제\s*5-21조\s*제\s*3항에서\s*정하는\s*한도",
)


def find_option_sections(document_text):
    text = document_text or ""
    put_match = _find_heading_match(text, PUT_SECTION_HEADING_PATTERNS)
    call_match = _find_heading_match(text, CALL_SECTION_HEADING_PATTERNS)

    return {
        "put_section_text": _slice_section_text(
            text,
            put_match,
            sibling_start_indexes=[call_match.start()] if call_match else [],
        ),
        "call_section_text": _slice_section_text(
            text,
            call_match,
            sibling_start_indexes=[put_match.start()] if put_match else [],
        ),
        "put_section_found": bool(put_match),
        "call_section_found": bool(call_match),
    }


def _find_heading_match(text, patterns):
    candidates = []
    for pattern in patterns:
        candidates.extend(pattern.finditer(text or ""))
    if not candidates:
        return None
    return min(candidates, key=lambda match: (match.start(), -(match.end() - match.start())))


def _slice_section_text(text, start_match, sibling_start_indexes):
    if not start_match:
        return ""

    start_index = start_match.start()
    boundary_indexes = [index for index in sibling_start_indexes if index > start_index]

    for match in TOP_LEVEL_SECTION_BOUNDARY_PATTERN.finditer(text or ""):
        if match.start() > start_index:
            boundary_indexes.append(match.start())

    end_index = min(boundary_indexes) if boundary_indexes else len(text)
    return text[start_index:end_index].strip()


def _extract_call_exercise_cap_pct(call_option_text):
    text = call_option_text or ""
    for pattern in CALL_CAP_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _extract_call_exercise_cap_pct_with_context(document_text):
    text = document_text or ""
    for pattern in CALL_CAP_CONTEXT_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _is_regulatory_default_zero_call_cap(text):
    return bool(CALL_CAP_REGULATION_DEFAULT_ZERO_PATTERN.search(text or ""))


def populate_option_section_metadata(result_dict, option_sections, document_text):
    result_dict["옵션구역분리"] = {
        "put_section_found": option_sections["put_section_found"],
        "call_section_found": option_sections["call_section_found"],
        "method": "heading_position_slice",
    }

    if option_sections["put_section_text"]:
        result_dict["PUT옵션본문"] = option_sections["put_section_text"][:2000]

    if option_sections["call_section_text"]:
        result_dict["CALL옵션본문"] = option_sections["call_section_text"][:2000]
        call_cap_pct = _extract_call_exercise_cap_pct(option_sections["call_section_text"])
        if call_cap_pct is not None:
            result_dict["CALL행사한도(%)"] = call_cap_pct
            result_dict["CALL행사한도판정"] = CALL_CAP_RESOLUTION_EXPLICIT

    if "CALL행사한도(%)" not in result_dict:
        fallback_call_cap_pct = _extract_call_exercise_cap_pct_with_context(document_text)
        if fallback_call_cap_pct is not None:
            result_dict["CALL행사한도(%)"] = fallback_call_cap_pct
            result_dict["CALL행사한도판정"] = CALL_CAP_RESOLUTION_EXPLICIT_CONTEXT

    if "CALL행사한도(%)" not in result_dict and option_sections["call_section_found"]:
        if _is_regulatory_default_zero_call_cap(option_sections["call_section_text"]):
            result_dict["CALL행사한도(%)"] = 0.0
            result_dict["CALL행사한도판정"] = CALL_CAP_RESOLUTION_REGULATORY_DEFAULT_ZERO
        else:
            result_dict["CALL행사한도판정"] = CALL_CAP_RESOLUTION_UNRESOLVED
