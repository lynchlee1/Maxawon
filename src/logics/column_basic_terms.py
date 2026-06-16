"""Stable basic-term extraction from the main security table.

Output columns:
- 종류
- 납입일
- 회차
- 발행금액(억)
- 전환가액(원)
- 전환가액 결정방법
- 표면이율
- 만기이율
- 만기일
- 대상주식
- 옵션사항
- 전환시작일
- 전환종료일
- 만기

Stability:
- relatively stable: main-table, label-driven extraction
"""

import re
from datetime import datetime

from parsing_utils import parse_date, parse_number, split


ISSUE_DATE_TEXT_PATTERN = re.compile(
    r"납입일[^\d]{0,30}(\d{4}[.-]\d{1,2}[.-]\d{1,2}|\d{4}년\s*\d{1,2}월\s*\d{1,2}일)"
)


def infer_security_type(report_nm: str) -> str:
    if "전환사채" in report_nm:
        return "CB"
    if "교환사채" in report_nm:
        return "EB"
    if "신주인수권부사채" in report_nm:
        return "BW"
    return "N/A"


def _safe_parse_date(text):
    converted = parse_date(text.strip())
    return converted if converted != "-" else None


def extract_issue_date_from_text(document_text):
    text = document_text or ""
    match = ISSUE_DATE_TEXT_PATTERN.search(text)
    if not match:
        return None
    return _safe_parse_date(match.group(1).replace(".", "-"))


def populate_issue_date_from_document_text_if_missing(result_dict, document_text):
    if "납입일" in result_dict:
        return
    issue_date_from_text = extract_issue_date_from_text(document_text)
    if issue_date_from_text:
        result_dict["납입일"] = issue_date_from_text


def _extract_row_value_after_sub_label(row_parts, sub_label):
    if len(row_parts) <= 1:
        return None

    for index, part in enumerate(row_parts[1:], start=1):
        if part.strip() != sub_label:
            continue
        if index + 1 < len(row_parts):
            return row_parts[index + 1]
        return None

    return row_parts[-1]


def apply_target_table_row(result_dict, row_parts):
    if not row_parts:
        return

    keyword_text = row_parts[0]

    if "납입일" in keyword_text and len(row_parts) > 1:
        result_dict["납입일"] = parse_date(row_parts[1])

    if "사채의 종류" in keyword_text and len(row_parts) > 2:
        result_dict["회차"] = row_parts[2]

    if "사채의 권면" in keyword_text and len(row_parts) > 1:
        result_dict["발행금액(억)"] = parse_number(row_parts[1]) / 10**8

    price_keyword_matched = (
        ("전환가액" in keyword_text and "원" in keyword_text)
        or ("교환가액" in keyword_text and "원" in keyword_text)
        or ("행사가액" in keyword_text and "원" in keyword_text)
    )
    if price_keyword_matched and "전환가액(원)" not in result_dict and len(row_parts) > 1:
        result_dict["전환가액(원)"] = parse_number(row_parts[1])

    if "전환가액 결정방법" in keyword_text and len(row_parts) > 1:
        result_dict["전환가액 결정방법"] = row_parts[1:]
    elif "교환가액 결정방법" in keyword_text and len(row_parts) > 1:
        result_dict["전환가액 결정방법"] = row_parts[1:]
    elif "행사가액 결정방법" in keyword_text and len(row_parts) > 1:
        result_dict["전환가액 결정방법"] = row_parts[1:]

    if (
        "전환가액 조정에" in keyword_text
        or "교환가액 조정에" in keyword_text
        or "행사가액 조정에" in keyword_text
    ) and len(row_parts) > 1:
        result_dict["_리픽싱원문"] = " ".join(row_parts[1:])

    if "사채의 이율" in keyword_text and len(row_parts) > 2:
        result_dict["표면이율"] = row_parts[2]
        try:
            rate = float(row_parts[2].strip("%")) / 100
            result_dict["표면이율"] = f"{round(100 * rate, 1)}%"
        except Exception:
            pass

    if "만기이자율" in keyword_text and len(row_parts) > 1:
        result_dict["만기이율"] = row_parts[1]
        try:
            rate = float(row_parts[1].strip("%")) / 100
            result_dict["만기이율"] = f"{round(100 * rate, 1)}%"
        except Exception:
            pass

    if "사채만기일" in keyword_text and len(row_parts) > 1:
        result_dict["만기일"] = parse_date(row_parts[1])

    if "시가하락" in keyword_text and len(row_parts) > 2:
        result_dict["리픽싱가격"] = parse_number(row_parts[2])
        if result_dict["리픽싱가격"] == -1.0:
            result_dict["리픽싱가격"] = "-"

    if "조정가액 근거" in keyword_text and len(row_parts) > 1:
        result_dict["리픽싱내용"] = " ".join(row_parts[1:])
        if result_dict["리픽싱내용"] == ["-"]:
            result_dict["리픽싱내용"] = "-"

    if "교환대상" in keyword_text:
        target_stock = _extract_row_value_after_sub_label(row_parts, "종류")
        if target_stock:
            result_dict["대상주식"] = target_stock
    elif "전환에 따라" in keyword_text or "인수권행사에 따라" in keyword_text:
        target_stock = _extract_row_value_after_sub_label(row_parts, "종류")
        if target_stock:
            result_dict["대상주식"] = target_stock

    if "옵션에 관한" in keyword_text and len(row_parts) > 1:
        result_dict["옵션사항"] = " ".join(row_parts[1:])

    if ("청구기간" in keyword_text or "행사기간" in keyword_text) and len(row_parts) > 2 and "시작일" in row_parts[1]:
        result_dict["전환시작일"] = parse_date(row_parts[2])

    if keyword_text.strip() == "종료일" and len(row_parts) > 1:
        result_dict["전환종료일"] = parse_date(row_parts[1])


def extract_target_table_fields(target_table, result_dict):
    for tr in target_table.find_all(["tr", "TR"]):
        row_text = tr.get_text(" | ", strip=True)
        row_parts = split(row_text)
        apply_target_table_row(result_dict, row_parts)


def populate_maturity_term(result_dict):
    try:
        date1 = datetime.strptime(result_dict["만기일"], "%Y-%m-%d")
        date2 = datetime.strptime(result_dict["납입일"], "%Y-%m-%d")
        diff_days = (date1 - date2).days
        result_dict["만기"] = f"{round(diff_days / 365.0, 1)}년"
    except Exception:
        result_dict["만기"] = "-"
