from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from lxml import etree, html

from weekly_mezz.xml import parse_xml_with_recovery

import sys

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from logics.column_basic_terms import infer_security_type, populate_maturity_term  # noqa: E402
from logics.column_option_schedule import (  # noqa: E402
    populate_option_presence_status_fields,
    populate_option_schedule_fields,
    populate_text_only_option_fields,
)
from logics.column_option_sections import find_option_sections, populate_option_section_metadata  # noqa: E402
from logics.column_participants import populate_participant_fields  # noqa: E402
from logics.column_premium import populate_premium_fields  # noqa: E402
from logics.column_refixing import populate_refixing_from_text_if_missing  # noqa: E402
from logics.document_context import combine_document_text  # noqa: E402
from parsing_utils import parse_date, parse_number  # noqa: E402


FUNDING_PURPOSE_LABELS = [
    "시설자금",
    "영업양수자금",
    "운영자금",
    "채무상환자금",
    "타법인 증권 취득자금",
    "기타자금",
]


def parse_bond_issuance_html(html_text: str | bytes, *, file_path: str | Path, report: dict | None = None) -> dict[str, Any]:
    report = report or {}
    document = _parse_html_document(html_text)
    raw_tables = _extract_tables(document)
    rows = _main_bond_rows(raw_tables)
    record = _base_record(document, raw_tables, file_path, report)

    soup = BeautifulSoup(_decode(html_text), "html.parser")
    soups = [soup]
    bs_tables = soup.find_all(["table", "TABLE"])
    document_text = _clean_text(" ".join(document.itertext())) or combine_document_text(soups)
    option_sections = find_option_sections(document_text)
    is_bw = _is_bond_with_warrant(rows) or infer_security_type(report.get("report_nm", "")) == "BW"

    record["종류"] = "BW" if is_bw else infer_security_type(report.get("report_nm") or record.get("title") or "")
    record.update(
        {
            "회차": _value_after(_row_containing(rows, "사채의 종류"), "회차"),
            "발행금액": _amount_eok(_last_int(_row_containing(rows, "사채의 권면"))),
            "발행금액(억)": _amount_eok(_last_int(_row_containing(rows, "사채의 권면"))),
            "발행목적": _funding_purposes(rows),
            "표면이율": _format_rate(_interest_rate(rows, "표면이자율", "표면이율")),
            "만기이율": _format_rate(_interest_rate(rows, "만기이자율", "만기보장수익", "만기이율")),
            "만기일": _parse_date_or_raw(_last_value(_row_containing(rows, "사채만기일"))),
            "행사가액": _exercise_price(rows),
            "전환가액(원)": _exercise_price(rows),
            "대상주식": _exercise_target(rows),
            "전환시작일": _parse_date_or_raw(_exercise_period_value(rows, "시작일")),
            "전환종료일": _parse_date_or_raw(_exercise_period_value(rows, "종료일")),
            "청약일": _parse_date_or_raw(_last_value(_row_with_label(rows, "청약일"))),
            "납입일": _parse_date_or_raw(_last_value(_row_with_label(rows, "납입일"))),
            "납입방법": _payment_method(rows),
            "발행대상자": _issue_targets(raw_tables),
            "발행대상자세부엔티티": _issue_target_entities(raw_tables),
        }
    )

    _populate_refixing(record, rows, document_text)
    if not is_bw:
        populate_premium_fields(record, document_text)
    populate_maturity_term(record)
    populate_participant_fields(record, bs_tables)
    _merge_current_participant_targets(record)
    populate_option_section_metadata(record, option_sections, document_text)
    if rows:
        populate_option_schedule_fields(record, bs_tables, option_sections)
    else:
        populate_text_only_option_fields(record, option_sections)
    populate_option_presence_status_fields(record, bs_tables, option_sections, document_text)
    return record


def _decode(markup: str | bytes) -> str:
    if isinstance(markup, str):
        return markup
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return markup.decode(encoding)
        except UnicodeDecodeError:
            continue
    return markup.decode("utf-8", errors="replace")


def _parse_html_document(markup: str | bytes):
    return html.fromstring(_decode(markup), parser=html.HTMLParser(encoding="utf-8", recover=True, huge_tree=True))


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _element_text(element: etree._Element) -> str:
    return _clean_text(" ".join(element.itertext()))


def _base_record(document, raw_tables, file_path, report):
    title = _extract_title(document) or report.get("title") or report.get("report_nm", "")
    acpt_no = str(report.get("acpt_no") or report.get("rcept_no") or Path(file_path).stem).strip()
    rcept_no, correction_families = _correction_families(document, acpt_no)
    return {
        "title": title,
        "공시제목": title,
        "rcept_no": rcept_no or report.get("rcept_no") or acpt_no,
        "acpt_no": acpt_no,
        "source_file": str(Path(file_path).resolve()),
        "mode": "bond_issuance",
        "correction_families": correction_families,
        "raw_tables": raw_tables,
        "raw_rows": [row for table in raw_tables for row in table["logical_rows"]],
    }


def _extract_title(document) -> str:
    for xpath in ("//meta[translate(@property, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='og:title']/@content", "//title/text()", "//*[@title]/@title", "//h1/text()", "//h2/text()"):
        for value in document.xpath(xpath):
            title = _clean_text(str(value))
            if title:
                return title
    return ""


def _correction_families(document, acpt_no: str):
    options = []
    for option in document.xpath("//select[@id='mainDoc' or @name='mainDoc']/option"):
        raw_value = _clean_text(str(option.get("value") or ""))
        if not raw_value:
            continue
        doc_no, _, latest_flag = raw_value.partition("|")
        if doc_no:
            options.append({"rcept_no": doc_no, "latest_flag": latest_flag.upper(), "selected": option.get("selected") is not None})
    if not options:
        return None, {}
    current_sequence = next((i for i, item in enumerate(options) if item["selected"]), None)
    latest_item = next((item for item in options if item["latest_flag"] == "Y"), options[-1])
    members = [{"sequence": i, "acpt_no": acpt_no if i == current_sequence else None, "rcept_no": item["rcept_no"]} for i, item in enumerate(options)]
    return (options[current_sequence]["rcept_no"] if current_sequence is not None else None), {latest_item["rcept_no"]: {"current_sequence": current_sequence, "members": members}}


def _span_size(cell, name):
    try:
        return max(int(str(cell.get(name) or "1")), 1)
    except ValueError:
        return 1


def _expand_table(table):
    active = {}
    grid = []
    for row_index, row in enumerate(table.xpath(".//tr")):
        expanded = []
        col_index = 0
        source_col = 0
        consumed = set()

        def append_active():
            nonlocal col_index
            span = active.get(col_index)
            if span is None:
                return False
            consumed.add(col_index)
            remaining, cell, source_row, span_source_col, rowspan, colspan = span
            expanded.append({"text": _element_text(cell), "from_span": True, "rowspan": rowspan, "colspan": colspan})
            col_index += 1
            return True

        for cell in row.xpath("./th|./td"):
            while append_active():
                pass
            rowspan = _span_size(cell, "rowspan")
            colspan = _span_size(cell, "colspan")
            for offset in range(colspan):
                expanded.append({"text": _element_text(cell), "from_span": False, "rowspan": rowspan, "colspan": colspan})
                if rowspan > 1:
                    active[col_index + offset] = (rowspan - 1, cell, row_index, source_col, rowspan, colspan)
            col_index += colspan
            source_col += 1
        while active and col_index <= max(active):
            if not append_active():
                expanded.append({"text": "", "from_span": False, "rowspan": 1, "colspan": 1})
                col_index += 1
        if any(slot["text"] for slot in expanded):
            grid.append(expanded)
        active = {col: (remaining - 1 if col in consumed else remaining, cell, source_row, source_col, rowspan, colspan) for col, (remaining, cell, source_row, source_col, rowspan, colspan) in active.items() if (remaining - 1 if col in consumed else remaining) > 0}
    return grid


def _compress(row):
    values = []
    for value in row:
        cleaned = _clean_text(value)
        if cleaned and (not values or values[-1] != cleaned):
            values.append(cleaned)
    return values


def _extract_tables(document):
    tables = []
    for index, table in enumerate(document.xpath("//table")):
        grid = _expand_table(table)
        rows = [_compress([slot["text"] for slot in row]) for row in grid]
        rows = [row for row in rows if row]
        tables.append({"index": index, "chapter_title": _nearest_chapter_title(table), "cells": grid, "logical_rows": rows})
    return tables


def _nearest_chapter_title(table):
    nodes = table.xpath("preceding::*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6 or (self::p and contains(concat(' ', normalize-space(@class), ' '), ' CORRECTION ')) or (self::p and contains(concat(' ', normalize-space(@class), ' '), ' SECTION-'))][1]")
    return _element_text(nodes[0]) if nodes else ""


def _is_correction_chapter(table):
    return "정정신고" in _clean_text(str(table.get("chapter_title") or "")).replace(" ", "")


def _row_contains(row, *needles):
    text = " ".join(row)
    compact = text.replace(" ", "")
    return all(needle in text or needle.replace(" ", "") in compact for needle in needles)


def _row_containing(rows, *needles):
    return next((row for row in rows if _row_contains(row, *needles)), [])


def _main_bond_rows(raw_tables):
    for table in raw_tables:
        if _is_correction_chapter(table):
            continue
        rows = table.get("logical_rows") or []
        if any(_row_contains(row, "사채의 종류") for row in rows) and any(_row_contains(row, "사채의 권면") for row in rows) and any(_row_contains(row, "자금조달의 목적") for row in rows):
            return rows
    return []


def _normalize_label(value):
    return re.sub(r"^\d+(?:-\d+)?\.\s*", "", _clean_text(value))


def _row_with_label(rows, label):
    return next((row for row in rows if any(_normalize_label(value) == label for value in row)), [])


def _value_after(row, label):
    for index, value in enumerate(row):
        if value == label and index + 1 < len(row):
            return row[index + 1]
    return None


def _last_value(row):
    return row[-1] if row else None


def _last_int(row):
    for value in reversed(row):
        parsed = _parse_int(value)
        if parsed is not None:
            return parsed
    return None


def _parse_int(value):
    match = re.search(r"-?\d[\d,]*", _clean_text(value))
    return int(match.group(0).replace(",", "")) if match else None


def _parse_float(value):
    match = re.search(r"-?\d+(?:\.\d+)?", _clean_text(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _amount_eok(value):
    return None if value is None else value / 10**8


def _parse_date_or_raw(value):
    if not value:
        return None
    parsed = parse_date(value)
    return parsed if parsed != "-" else value


def _format_rate(value):
    return None if value is None else f"{round(value, 4):g}%"


def _interest_rate(rows, *labels):
    for label in labels:
        value = _parse_float(_last_value(_row_containing(rows, label)))
        if value is not None:
            return value
    return None


def _is_bond_with_warrant(rows):
    return _row_contains(_row_containing(rows, "사채의 종류"), "신주인수권")


def _exercise_period_value(rows, boundary_label):
    for label in ("전환청구기간", "권리행사기간"):
        value = _last_value(_row_containing(rows, label, boundary_label))
        if value is not None:
            return value
    if boundary_label == "종료일":
        value = _last_value(_row_with_label(rows, "종료일"))
        if value is not None:
            return value
    return None


def _exercise_price(rows):
    for label in ("전환가액", "교환가액", "행사가액"):
        value = _last_int(_row_containing(rows, label, "원"))
        if value is not None:
            return value
    return None


def _exercise_target(rows):
    for label in ("교환대상", "전환에 따라", "전환으로 발행할", "인수권행사에 따라"):
        value = _last_value(_row_containing(rows, label, "종류"))
        if value is not None:
            return value
    return None


def _payment_method(rows):
    for label in ("납입방법", "신주대금 납입방법"):
        value = _last_value(_row_with_label(rows, label))
        if value is not None:
            return value
    return None


def _funding_purposes(rows):
    purposes = []
    for label in FUNDING_PURPOSE_LABELS:
        value = _last_int(_row_containing(rows, "자금조달의 목적", label))
        purposes.append([label, 0 if value is None else value])
    return purposes


def _populate_refixing(record, rows, document_text):
    won = None
    row = _row_containing(rows, "시가하락")
    if row:
        won = _last_int(row)
    refix_text = " ".join(
        _row_containing(rows, "조정가액 근거")
        or _row_containing(rows, "전환가액 조정에 관한 사항")
        or _row_containing(rows, "교환가액 조정에 관한 사항")
        or _row_containing(rows, "행사가액 조정에 관한 사항")
        or _row_containing(rows, "전환가액 조정")
        or _row_containing(rows, "행사가액 조정")
    ) or document_text
    record["리픽싱(원)"] = won
    record["리픽싱사유"] = refix_text if refix_text else None
    temp = {"리픽싱가격": "-", "리픽싱주가": "-", "_리픽싱원문": refix_text}
    if won is not None and record.get("행사가액"):
        try:
            temp["리픽싱가격"] = f"{round(100 * won / record['행사가액'], 0)}%"
        except Exception:
            pass
    populate_refixing_from_text_if_missing(temp, document_text)
    record["리픽싱(%)"] = temp.get("리픽싱가격")
    record["리픽싱가격"] = temp.get("리픽싱가격")
    record["리픽싱주가"] = temp.get("리픽싱주가")
    record["리픽싱내용"] = refix_text if refix_text else "-"


def _issue_targets(raw_tables):
    for table in _non_correction_tables(raw_tables):
        rows = table.get("logical_rows") or []
        if not rows or not _row_contains(rows[0], "발행 대상자명", "발행권면"):
            continue
        targets = []
        for row in rows[1:]:
            if not row or row[0] in {"-", "합계", "총계", "계"}:
                continue
            amount = _last_int(row)
            if amount is not None:
                targets.append([row[0], amount])
        return targets
    return []


def _issue_target_entities(raw_tables):
    entities = []
    for table in _non_correction_tables(raw_tables):
        rows = table.get("logical_rows") or []
        if len(rows) < 3 or not _row_contains(rows[0], "명칭", "대표이사", "최대주주"):
            continue
        grouped = {}
        for row in rows[2:]:
            if len(row) < 3 or row[0] == "-":
                continue
            values = grouped.setdefault(row[0], {"representatives": [], "major_holders": []})
            if row[2] != "-" and row[2] not in values["representatives"]:
                values["representatives"].append(row[2])
            if len(row) >= 6 and row[-2] != "-" and row[-2] not in values["major_holders"]:
                values["major_holders"].append(row[-2])
        for name, values in grouped.items():
            entities.append([name, *values["representatives"], *values["major_holders"]])
    return entities


def _non_correction_tables(raw_tables):
    return [table for table in raw_tables if not _is_correction_chapter(table)]


def _merge_current_participant_targets(record):
    participant_text = record.get("발행대상")
    if not participant_text or participant_text == "-":
        return
    record["발행대상자_본건매칭"] = participant_text
    if not record.get("발행대상자"):
        targets = []
        for item in str(participant_text).split(","):
            text = item.strip()
            match = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)$", text)
            if match:
                targets.append([match.group(1).strip(), int(float(match.group(2)) * 10**8)])
        record["발행대상자"] = targets
