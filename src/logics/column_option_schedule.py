"""PUT/CALL schedule extraction and yield calculation.

Output columns:
- PUT연복리(%)
- PUT옵션일정표
- CALL옵션일정표
- PUT옵션추출상태
- CALL옵션추출상태
- PUT옵션LLM검토필요
- CALL옵션LLM검토필요
- YTP(%)
- YTP산출상태
- YTC(%)
- YTC산출상태
- CALL옵션

Stability:
- heuristic: table pattern matching first, narrative schedule synthesis second
"""

import calendar
import re
from datetime import date, datetime

from parsing_utils import parse_date, split
from logics.document_context import is_correction_comparison_table


TEXT_SCHEDULE_PATTERN = re.compile(
    r"발행일로부터\s*(\d+)\s*개월.*?(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일.*?매\s*(\d+)\s*개월",
    re.DOTALL,
)
TEXT_SCHEDULE_RANGE_PATTERN = re.compile(
    r"발행일\s*이후\s*\d+\s*개월[^\d]{0,80}\(?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\)?"
    r".*?발행일\s*이후\s*\d+\s*개월[^\d]{0,80}\(?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\)?"
    r".*?매\s*(\d+)\s*개월",
    re.DOTALL,
)
TEXT_SCHEDULE_END_DATE_PATTERN = re.compile(
    r"부터\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*까지",
    re.DOTALL,
)
TEXT_SCHEDULE_WINDOW_PATTERN = re.compile(
    r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*부터.*?(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*까지",
    re.DOTALL,
)
COMPOUND_RATE_PATTERN = re.compile(r"조기상환수익률\s*연복리\s*(\d+(?:\.\d+)?)\s*%")
MAX_TEXT_SCHEDULE_POINTS = 32

PUT_OPTION_KEYWORD_PATTERN = re.compile(r"(?:조기상환청구권|Put\s*Option|put\s*option|조기상환권)", re.IGNORECASE)
CALL_OPTION_KEYWORD_PATTERN = re.compile(r"(?:매도청구권|Call\s*Option|call\s*option|콜옵션)", re.IGNORECASE)
OPTION_EXPLICIT_NONE_PATTERN = re.compile(r"(?:존재하지\s*않|해당사항\s*없|없음|없다)")

OPTION_SCHEDULE_ROW_INDEX_PATTERN = re.compile(r"^\s*(?:\d+\s*차|[①②③④⑤⑥⑦⑧⑨⑩])")
OPTION_SCHEDULE_ROW_HINT_PATTERN = re.compile(
    r"(?:조기상환청구기간|조기상환지급일|조기상환일|매매대금\s*지급기일|중도상환지급일|청구기간|FROM|TO)",
    re.IGNORECASE,
)
OPTION_SCHEDULE_EXCLUDE_ROW_PATTERN = re.compile(
    r"(?:사채만기일|청약일|납입일|이자지급방법|전환권\s*청구기간|전환청구기간|전환가액|교환가액|행사가액)",
    re.IGNORECASE,
)
KNOWN_SCHEDULE_TABLE_PATTERN = re.compile(
    r"(?:조기상환일|조기상환청구기간|조기상환율|매매일|매매대금\s*지급기일|매도청구권|Call\s*Option|\[FROM\]|\[TO\])",
    re.IGNORECASE,
)
ROW_STARTS_WITH_DATE_PATTERN = re.compile(r"^\s*\d{4}[.-]\d{1,2}[.-]\d{1,2}")
MAX_OPTION_SCHEDULE_CELL_COUNT = 8

OPTION_STATUS_PRESENT_PARSED = "present_parsed"
OPTION_STATUS_EXPLICIT_NONE = "explicit_none"
OPTION_STATUS_SECTION_DETECTED_BUT_UNPARSED = "section_detected_but_unparsed"
OPTION_STATUS_TABLE_DETECTED_BUT_UNPARSED = "table_detected_but_unparsed"
OPTION_STATUS_KEYWORD_DETECTED_BUT_UNPARSED = "keyword_detected_but_unparsed"
OPTION_STATUS_NO_EVIDENCE = "no_evidence"


def _parse_rate_from_text(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*%?", text or "")
    if not match:
        return None
    value = float(match.group(1))
    if "%" in (text or ""):
        return value
    if 50 <= value <= 200:
        return value
    return None


def _safe_parse_date(text):
    converted = parse_date(text.strip())
    return converted if converted != "-" else None


def resolve_schedule_dates(raw_dates):
    normalized_dates = []
    for raw_date in raw_dates:
        normalized = _safe_parse_date(raw_date.replace(".", "-"))
        if normalized:
            normalized_dates.append(normalized)

    ordered_dates = sorted(set(normalized_dates))
    if not ordered_dates:
        return "-", "-", "-"
    if len(ordered_dates) == 1:
        return "-", "-", ordered_dates[0]
    if len(ordered_dates) == 2:
        return "-", ordered_dates[0], ordered_dates[1]
    if len(ordered_dates) == 3:
        return ordered_dates[0], ordered_dates[1], ordered_dates[2]
    return "-", "-", ordered_dates[-1]


def _build_schedule_item(
    option_type,
    claim_start_date="-",
    claim_end_date="-",
    payment_date="-",
    redemption_rate_pct=None,
    source=None,
    row_text=None,
    interval_months=None,
):
    item = {
        "option_type": option_type,
        "청구시작일": claim_start_date,
        "청구종료일": claim_end_date,
        "지급일": payment_date,
        "event_date": payment_date,
        "redemption_rate_pct": redemption_rate_pct,
        "source": source,
    }
    if row_text is not None:
        item["row_text"] = row_text
    if interval_months is not None:
        item["interval_months"] = interval_months
    return item


def _schedule_triplet(item):
    return [
        item.get("청구시작일") or "-",
        item.get("청구종료일") or "-",
        item.get("지급일") or "-",
    ]


def _store_option_schedules(result_dict, public_key, detail_key, schedules):
    result_dict[detail_key] = schedules
    result_dict[public_key] = [_schedule_triplet(item) for item in schedules]


def _get_option_keyword_pattern(option_type):
    return PUT_OPTION_KEYWORD_PATTERN if option_type == "PUT" else CALL_OPTION_KEYWORD_PATTERN


def _get_option_state_keys(option_type):
    return {
        "public_schedule_key": f"{option_type}옵션일정표",
        "detail_schedule_key": f"_{option_type}옵션일정표상세",
        "status_key": f"{option_type}옵션추출상태",
        "llm_review_key": f"{option_type}옵션LLM검토필요",
        "evidence_key": f"_{option_type}옵션추출근거",
    }


def _count_option_related_tables(tables, option_type):
    keyword_pattern = _get_option_keyword_pattern(option_type)
    count = 0
    for table in tables or []:
        table_text = table.get_text(" ", strip=True)
        if not table_text or is_correction_comparison_table(table_text):
            continue
        if "사채의 종류" in table_text:
            continue
        if keyword_pattern.search(table_text):
            count += 1
    return count


def _has_explicit_option_none(section_text):
    return bool(OPTION_EXPLICIT_NONE_PATTERN.search(section_text or ""))


def _resolve_option_presence_status(option_type, result_dict, tables, section_text, section_found, document_text):
    keys = _get_option_state_keys(option_type)
    schedules = result_dict.get(keys["detail_schedule_key"]) or result_dict.get(keys["public_schedule_key"]) or []
    explicit_none = _has_explicit_option_none(section_text)
    table_candidate_count = _count_option_related_tables(tables, option_type)
    keyword_found_in_document = bool(_get_option_keyword_pattern(option_type).search(document_text or ""))

    if schedules:
        status = OPTION_STATUS_PRESENT_PARSED
    elif explicit_none:
        status = OPTION_STATUS_EXPLICIT_NONE
    elif section_found:
        status = OPTION_STATUS_SECTION_DETECTED_BUT_UNPARSED
    elif table_candidate_count > 0:
        status = OPTION_STATUS_TABLE_DETECTED_BUT_UNPARSED
    elif keyword_found_in_document:
        status = OPTION_STATUS_KEYWORD_DETECTED_BUT_UNPARSED
    else:
        status = OPTION_STATUS_NO_EVIDENCE

    result_dict[keys["status_key"]] = status
    result_dict[keys["llm_review_key"]] = status in {
        OPTION_STATUS_SECTION_DETECTED_BUT_UNPARSED,
        OPTION_STATUS_TABLE_DETECTED_BUT_UNPARSED,
        OPTION_STATUS_KEYWORD_DETECTED_BUT_UNPARSED,
    }
    result_dict[keys["evidence_key"]] = {
        "section_found": section_found,
        "explicit_none": explicit_none,
        "schedule_count": len(schedules),
        "table_candidate_count": table_candidate_count,
        "keyword_found_in_document": keyword_found_in_document,
    }


def populate_option_presence_status_fields(result_dict, tables, option_sections, document_text):
    _resolve_option_presence_status(
        "PUT",
        result_dict,
        tables,
        option_sections.get("put_section_text", ""),
        option_sections.get("put_section_found", False),
        document_text,
    )
    _resolve_option_presence_status(
        "CALL",
        result_dict,
        tables,
        option_sections.get("call_section_text", ""),
        option_sections.get("call_section_found", False),
        document_text,
    )


def _is_schedule_row_candidate(tr, row_text, raw_dates):
    if OPTION_SCHEDULE_EXCLUDE_ROW_PATTERN.search(row_text or ""):
        return False
    if not (2 <= len(raw_dates) <= 3):
        return False

    cells = tr.find_all(["th", "TH", "td", "TD", "te", "TE"])
    if cells and len(cells) > MAX_OPTION_SCHEDULE_CELL_COUNT:
        return False

    if OPTION_SCHEDULE_ROW_INDEX_PATTERN.search(row_text or ""):
        return True
    return bool(OPTION_SCHEDULE_ROW_HINT_PATTERN.search(row_text or ""))


def _looks_like_schedule_data_row(row_text, raw_dates):
    if not (2 <= len(raw_dates) <= 3):
        return False
    return bool(ROW_STARTS_WITH_DATE_PATTERN.search(row_text or ""))


def _extract_schedule_from_table(table, option_type):
    schedules = []
    table_text = table.get_text(" ", strip=True)
    table_is_known_schedule = bool(KNOWN_SCHEDULE_TABLE_PATTERN.search(table_text))

    for tr in table.find_all(["tr", "TR"]):
        row_text = tr.get_text(" ", strip=True)
        if not row_text:
            continue

        dates = re.findall(r"\d{4}[.-]\d{1,2}[.-]\d{1,2}|\d{4}년\s*\d{1,2}월\s*\d{1,2}일", row_text)
        if not dates:
            continue

        if not _is_schedule_row_candidate(tr, row_text, dates):
            if not (table_is_known_schedule and _looks_like_schedule_data_row(row_text, dates)):
                continue

        rate_value = None
        for token in split(row_text.replace(" ", " | ")):
            parsed = _parse_rate_from_text(token)
            if parsed is not None:
                rate_value = parsed
                break

        claim_start_date, claim_end_date, payment_date = resolve_schedule_dates(dates)
        if payment_date != "-":
            schedules.append(
                _build_schedule_item(
                    option_type=option_type,
                    claim_start_date=claim_start_date,
                    claim_end_date=claim_end_date,
                    payment_date=payment_date,
                    redemption_rate_pct=rate_value,
                    source="table",
                    row_text=row_text,
                )
            )

    return schedules


def _add_months(value, months):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _extract_schedule_from_text(option_text, option_type="PUT", maturity_date=None, put_compound_rate=None):
    schedules = []
    start_date = None
    end_date = None
    interval_months = None

    match = TEXT_SCHEDULE_PATTERN.search(option_text or "")
    if match:
        start_date = date(int(match.group(2)), int(match.group(3)), int(match.group(4)))
        interval_months = int(match.group(5))
        end_match = TEXT_SCHEDULE_END_DATE_PATTERN.search(option_text or "")
        if end_match:
            end_date = date(int(end_match.group(1)), int(end_match.group(2)), int(end_match.group(3)))
    else:
        range_match = TEXT_SCHEDULE_RANGE_PATTERN.search(option_text or "")
        if range_match:
            start_date = date(int(range_match.group(1)), int(range_match.group(2)), int(range_match.group(3)))
            end_date = date(int(range_match.group(4)), int(range_match.group(5)), int(range_match.group(6)))
            interval_months = int(range_match.group(7))
        else:
            window_match = TEXT_SCHEDULE_WINDOW_PATTERN.search(option_text or "")
            if window_match:
                claim_start_date = date(int(window_match.group(1)), int(window_match.group(2)), int(window_match.group(3)))
                claim_end_date = date(int(window_match.group(4)), int(window_match.group(5)), int(window_match.group(6)))
                if claim_end_date >= claim_start_date:
                    schedules.append(
                        _build_schedule_item(
                            option_type=option_type,
                            claim_start_date=claim_start_date.strftime("%Y-%m-%d"),
                            claim_end_date=claim_end_date.strftime("%Y-%m-%d"),
                            payment_date="-",
                            redemption_rate_pct=None,
                            source="text_window",
                        )
                    )
                return schedules

    if not start_date or not interval_months:
        return schedules

    current = start_date
    count = 0
    while count < MAX_TEXT_SCHEDULE_POINTS:
        if maturity_date and current > maturity_date:
            break
        if end_date and current > end_date:
            break

        schedules.append(
            _build_schedule_item(
                option_type=option_type,
                claim_start_date="-",
                claim_end_date="-",
                payment_date=current.strftime("%Y-%m-%d"),
                redemption_rate_pct=None,
                source="text_generated",
                interval_months=interval_months,
            )
        )
        current = _add_months(current, interval_months)
        count += 1

    if option_type == "PUT" and put_compound_rate is not None:
        for item in schedules:
            payment_date = datetime.strptime(item["지급일"], "%Y-%m-%d").date()
            months_gap = (payment_date.year - start_date.year) * 12 + (payment_date.month - start_date.month)
            years_gap = months_gap / 12.0
            item["redemption_rate_pct"] = round((1 + put_compound_rate / 100.0) ** years_gap * 100, 4)

    return schedules


def _calculate_yield_to_option(schedules, issue_date):
    if not schedules or not issue_date:
        return None
    base_date = datetime.strptime(issue_date, "%Y-%m-%d").date()
    for item in schedules:
        rate = item.get("redemption_rate_pct")
        event_date_str = item.get("지급일") or item.get("event_date")
        if rate is None or not event_date_str or event_date_str == "-":
            continue
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
        days = (event_date - base_date).days
        if days <= 0:
            continue
        annualized = ((rate / 100.0) ** (365.0 / days) - 1.0) * 100.0
        return round(annualized, 4)
    return None


def _yield_status(schedules, issue_date, yield_value):
    if not schedules:
        return "no_schedule"
    if yield_value is not None:
        return "computed"
    if not issue_date:
        return "missing_issue_date"
    if not any(item.get("redemption_rate_pct") is not None for item in schedules):
        return "missing_redemption_rate"
    return "calculation_not_available"


def populate_text_only_option_fields(result_dict, option_sections):
    if option_sections["call_section_found"] and "존재하지 않" in option_sections["call_section_text"]:
        result_dict["CALL옵션"] = "없음"

    if option_sections["put_section_found"]:
        put_compound_rate = None
        match = COMPOUND_RATE_PATTERN.search(option_sections["put_section_text"])
        if match:
            put_compound_rate = float(match.group(1))
            result_dict["PUT연복리(%)"] = put_compound_rate

        put_schedules = _extract_schedule_from_text(
            option_sections["put_section_text"],
            option_type="PUT",
            maturity_date=None,
            put_compound_rate=put_compound_rate,
        )
        if put_schedules:
            _store_option_schedules(result_dict, "PUT옵션일정표", "_PUT옵션일정표상세", put_schedules)
            ytp = _calculate_yield_to_option(put_schedules, result_dict.get("납입일"))
            if ytp is not None:
                result_dict["YTP(%)"] = ytp
            result_dict["YTP산출상태"] = _yield_status(put_schedules, result_dict.get("납입일"), ytp)

    if option_sections["call_section_found"]:
        call_schedules = _extract_schedule_from_text(
            option_sections["call_section_text"],
            option_type="CALL",
            maturity_date=None,
            put_compound_rate=None,
        )
        if call_schedules:
            _store_option_schedules(result_dict, "CALL옵션일정표", "_CALL옵션일정표상세", call_schedules)
            ytc = _calculate_yield_to_option(call_schedules, result_dict.get("납입일"))
            if ytc is not None:
                result_dict["YTC(%)"] = ytc
            result_dict["YTC산출상태"] = _yield_status(call_schedules, result_dict.get("납입일"), ytc)
        elif "존재하지 않" in option_sections["call_section_text"]:
            result_dict["CALL옵션"] = "없음"


def populate_option_schedule_fields(result_dict, tables, option_sections):
    put_schedules = []
    call_schedules = []
    for table in tables:
        text = table.get_text(" ", strip=True)
        if is_correction_comparison_table(text):
            continue
        if "조기상환" in text and ("기일" in text or "상환율" in text) and "사채의 종류" not in text:
            put_schedules.extend(_extract_schedule_from_table(table, "PUT"))
        if ("매도청구권" in text or "Call Option" in text or "콜옵션" in text) and "사채의 종류" not in text:
            call_schedules.extend(_extract_schedule_from_table(table, "CALL"))

    put_compound_rate = None
    if option_sections["put_section_text"]:
        match = COMPOUND_RATE_PATTERN.search(option_sections["put_section_text"])
        if match:
            put_compound_rate = float(match.group(1))
            result_dict["PUT연복리(%)"] = put_compound_rate

    maturity_date = None
    issue_date = result_dict.get("납입일")
    if result_dict.get("만기일") and result_dict["만기일"] != "-":
        maturity_date = datetime.strptime(result_dict["만기일"], "%Y-%m-%d").date()

    if option_sections["put_section_text"] and not put_schedules:
        put_schedules.extend(
            _extract_schedule_from_text(
                option_sections["put_section_text"],
                option_type="PUT",
                maturity_date=maturity_date,
                put_compound_rate=put_compound_rate,
            )
        )

    if option_sections["call_section_text"] and not call_schedules:
        call_schedules.extend(
            _extract_schedule_from_text(
                option_sections["call_section_text"],
                option_type="CALL",
                maturity_date=maturity_date,
                put_compound_rate=None,
            )
        )

    if put_schedules:
        _store_option_schedules(result_dict, "PUT옵션일정표", "_PUT옵션일정표상세", put_schedules)
        ytp = _calculate_yield_to_option(put_schedules, issue_date)
        if ytp is not None:
            result_dict["YTP(%)"] = ytp
        result_dict["YTP산출상태"] = _yield_status(put_schedules, issue_date, ytp)

    if call_schedules:
        _store_option_schedules(result_dict, "CALL옵션일정표", "_CALL옵션일정표상세", call_schedules)
        ytc = _calculate_yield_to_option(call_schedules, issue_date)
        if ytc is not None:
            result_dict["YTC(%)"] = ytc
        result_dict["YTC산출상태"] = _yield_status(call_schedules, issue_date, ytc)
    elif option_sections["call_section_found"] and "존재하지 않" in option_sections["call_section_text"]:
        result_dict["CALL옵션"] = "없음"
