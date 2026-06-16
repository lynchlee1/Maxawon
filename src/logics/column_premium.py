"""Premium-related column extraction.

Output columns:
- 기준주가대비발행비율(%)
- 할증률(%)

Stability:
- heuristic: regex-based text interpretation
"""

import re


PREMIUM_TEXT_GAP_LIMIT = 30
PREMIUM_SOURCE_WINDOW = 1600
PREMIUM_BASE_RATE_STRICT_PATTERN = re.compile(r"기준(?:주가|가액|가격)의\s*(\d+(?:\.\d+)?)\s*%")
PREMIUM_BASE_RATE_PATTERN = re.compile(
    rf"기준(?:주가|가액|가격)[^\d%\n]{{0,{PREMIUM_TEXT_GAP_LIMIT}}}(\d+(?:\.\d+)?)\s*%\s*에\s*해당"
)
PREMIUM_DIRECT_PATTERN = re.compile(r"할증률\s*(\d+(?:\.\d+)?)\s*%")
PREMIUM_MARKUP_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?할증")
STANDARD_PRICE_FORMULA_PATTERN = re.compile(r"가중산술평균주가")
STANDARD_PRICE_FORMULA_ZERO_PREMIUM_PATTERN = re.compile(
    r"가중산술평균주가.*?중\s*(?:가장\s*)?높은\s*가액(?:으)?로(?:써)?\s*(?:하(?:되|고)|산정|정하)",
    re.DOTALL,
)
STANDARD_PRICE_FORMULA_GENERIC_ZERO_PATTERN = re.compile(
    r"가중산술평균주가.*?중\s*(?:가장\s*)?높은\s*가액"
    r"|가중산술평균주가.*?중\s*큰\s*금액"
    r"|각\s*호의\s*가액\s*중\s*(?:가장\s*)?높은\s*가액"
    r"|산출된\s*금액.*?중\s*큰\s*금액",
    re.DOTALL,
)
STANDARD_FORMULA_BASE_RATIO_PATTERNS = [
    re.compile(
        r"중\s*높은\s*가액의\s*(\d+(?:\.\d+)?)\s*%\s*(?:로서|에\s*해당|를|로)",
        re.DOTALL,
    ),
    re.compile(
        r"중\s*높은\s*가액(?:을|으로)?\s*기준주가로\s*하여[^\d%\n]{0,30}"
        r"(?:기준주가의\s*)?(\d+(?:\.\d+)?)\s*%\s*(?:에\s*해당|를|로)",
        re.DOTALL,
    ),
    re.compile(
        r"중\s*가장\s*높은\s*가액을\s*기준(?:주가|가격)으로\s*하여[^\d%\n]{0,30}"
        r"(?:기준(?:주가|가격)의\s*)?(\d+(?:\.\d+)?)\s*%\s*(?:에\s*해당|를|로)",
        re.DOTALL,
    ),
]
EXCHANGE_PRICE_RATIO_PATTERN = re.compile(
    r"(?:교환프리미엄.*?|상장주식\s*종가의)\s*(\d+(?:\.\d+)?)\s*%",
    re.DOTALL,
)
PREMIUM_SOURCE_LABEL_PATTERN = re.compile(
    r"(전환가액 결정방법|교환가액 결정방법|행사가액 결정방법|전환가격 결정방법|교환가격 결정방법|행사가격 결정방법)"
)
PREMIUM_SOURCE_END_PATTERN = re.compile(
    r"(?:전환가액 조정에 관한 사항|교환가액 조정에 관한 사항|행사가액 조정에 관한 사항"
    r"|시가하락에 따른(?:\s*(?:전환|교환|행사)가액)?\s*조정"
    r"|전환에 따라 발행할 주식|교환대상|인수권행사에 따라 발행할 주식"
    r"|전환청구기간|행사기간|옵션에 관한 사항|합병 관련 사항|청약일|납입일"
    r"|대표주관회사|보증기관|담보제공에 관한 사항|이사회결의일(?:\(결정일\))?"
    r"|\b\d{1,2}(?:-\d+)?\.\s)"
)


def _premium_result_from_premium_pct(premium_pct):
    premium_pct = round(float(premium_pct), 4)
    return round(100.0 + premium_pct, 4), premium_pct


def _premium_result_from_base_ratio(base_ratio_pct):
    base_ratio_pct = round(float(base_ratio_pct), 4)
    return base_ratio_pct, round(base_ratio_pct - 100.0, 4)


def _extract_direct_premium_rate(text: str):
    direct_match = PREMIUM_DIRECT_PATTERN.search(text)
    if direct_match:
        return _premium_result_from_premium_pct(direct_match.group(1))

    markup_match = PREMIUM_MARKUP_PATTERN.search(text)
    if markup_match:
        return _premium_result_from_premium_pct(markup_match.group(1))

    return None, None


def _extract_reference_price_base_ratio(text: str):
    strict_match = PREMIUM_BASE_RATE_STRICT_PATTERN.search(text)
    if strict_match:
        return _premium_result_from_base_ratio(strict_match.group(1))

    relaxed_match = PREMIUM_BASE_RATE_PATTERN.search(text)
    if relaxed_match:
        return _premium_result_from_base_ratio(relaxed_match.group(1))

    return None, None


def _extract_standard_formula_base_ratio(text: str):
    if not STANDARD_PRICE_FORMULA_PATTERN.search(text):
        return None, None

    for pattern in STANDARD_FORMULA_BASE_RATIO_PATTERNS:
        match = pattern.search(text)
        if match:
            return _premium_result_from_base_ratio(match.group(1))

    return None, None


def _should_infer_zero_premium_from_standard_formula(text: str):
    if not text:
        return False
    if not STANDARD_PRICE_FORMULA_PATTERN.search(text):
        return False
    if not (
        STANDARD_PRICE_FORMULA_ZERO_PREMIUM_PATTERN.search(text)
        or STANDARD_PRICE_FORMULA_GENERIC_ZERO_PATTERN.search(text)
    ):
        return False

    explicit_base_ratio, explicit_premium_pct = _extract_standard_formula_base_ratio(text)
    if explicit_base_ratio is not None or explicit_premium_pct is not None:
        return False

    return True


def _extract_exchange_price_ratio(text: str):
    if not text:
        return None, None
    if "~" in text or "∼" in text:
        return None, None
    match = EXCHANGE_PRICE_RATIO_PATTERN.search(text)
    if not match:
        return None, None
    return _premium_result_from_base_ratio(match.group(1))


def _normalize_premium_text(text: str):
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_premium_source_segments(text: str):
    normalized = _normalize_premium_text(text)
    if not normalized:
        return []

    segments = []
    for match in PREMIUM_SOURCE_LABEL_PATTERN.finditer(normalized):
        tail = normalized[match.end(): match.end() + PREMIUM_SOURCE_WINDOW]
        end_match = PREMIUM_SOURCE_END_PATTERN.search(tail)
        segment = tail[: end_match.start()] if end_match else tail
        segment = segment.strip(" :-")
        if segment:
            segments.append(segment)
    return segments


def extract_premium_source_text(text: str):
    return " ".join(_extract_premium_source_segments(text))


def extract_premium_rate(text: str):
    if not text:
        return None, None

    premium_source_segments = _extract_premium_source_segments(text)
    candidate_texts = premium_source_segments or [_normalize_premium_text(text)]

    extractors = (
        _extract_direct_premium_rate,
        _extract_reference_price_base_ratio,
        _extract_standard_formula_base_ratio,
    )
    for candidate_text in candidate_texts:
        for extractor in extractors:
            base_ratio_pct, premium_pct = extractor(candidate_text)
            if base_ratio_pct is not None:
                return base_ratio_pct, premium_pct

        exchange_base_ratio, exchange_premium_pct = _extract_exchange_price_ratio(candidate_text)
        if exchange_base_ratio is not None:
            return exchange_base_ratio, exchange_premium_pct

        if _should_infer_zero_premium_from_standard_formula(candidate_text):
            return 100.0, 0.0

    return None, None


def populate_premium_fields(result_dict, premium_text):
    base_ratio_pct, premium_pct = extract_premium_rate(premium_text)
    if base_ratio_pct is not None:
        result_dict["기준주가대비발행비율(%)"] = base_ratio_pct
        result_dict["할증률(%)"] = premium_pct
