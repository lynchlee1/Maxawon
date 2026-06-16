import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from weekly_mezz.dart import fetch_corp_code_entries, fetch_document_soups, fetch_previous_family_rcept_no
from weekly_mezz.parser import parse_report_document

INCLUSION_KEYWORDS = [["전환사채", "교환사채", "신주인수권부사채"], "발행"]
DART_MAIN_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
# Developer-only diagnostic output. Keep this False for release builds.
ENABLE_AUDIT_JSON = False

HEADER_FILL = PatternFill(fill_type="solid", fgColor="00D084")
HEADER_FONT = Font(bold=True, color="06110B")
LINK_FONT = Font(color="7DD3FC", underline="single")
BORDER_SIDE = Side(style="thin", color="263244")
HEADER_BORDER = Border(left=BORDER_SIDE, right=BORDER_SIDE, top=BORDER_SIDE, bottom=BORDER_SIDE)
BODY_BORDER = Border(left=BORDER_SIDE, right=BORDER_SIDE, top=BORDER_SIDE, bottom=BORDER_SIDE)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
BODY_ALIGNMENT = Alignment(horizontal="left", vertical="center", wrap_text=True)

SHARE_TYPE_SUFFIX_PATTERN = re.compile(
    r"\s*(?:(?:기명식|무기명식)\s*)?(?:보통주식?|우선주식?|전환우선주식?|상환우선주식?|상환전환우선주식?|종류주식)\s*$"
)
CORP_DESIGNATOR_PATTERN = re.compile(r"\(주\)|㈜|주식회사")
MATCH_NORMALIZE_PATTERN = re.compile(r"[^0-9A-Za-z가-힣]")

ISSUER_MARKET_LABELS = {
    "Y": "코스피",
    "K": "코스닥",
    "N": "코넥스",
    "E": "기타",
}

COLUMN_SPECS = [
    {"group": None, "header": "공시일", "key": "filing_date", "width": 12},
    {"group": None, "header": "헤더", "key": "report_header", "width": 12},
    {"group": "발행사", "header": "기업명", "key": "issuer_company_name", "width": 20},
    {"group": "발행사", "header": "상장구분", "key": "issuer_market", "width": 12},
    {"group": "발행사", "header": "종목코드", "key": "issuer_stock_code", "width": 12},
    {"group": "대상주식", "header": "기업명", "key": "target_company_name", "width": 20},
    {"group": "대상주식", "header": "종목코드", "key": "target_stock_code", "width": 12},
    {"group": None, "header": "회차", "key": "round", "width": 7},
    {"group": None, "header": "종류", "key": "security_type", "width": 7},
    {"group": None, "header": "발행금액", "key": "issue_amount_eok", "width": 11},
    {"group": None, "header": "행사가액", "key": "strike_price", "width": 11},
    {"group": None, "header": "할증률", "key": "premium_pct", "width": 9},
    {"group": None, "header": "납입일", "key": "issue_date", "width": 12},
    {"group": None, "header": "만기일", "key": "maturity_date", "width": 12},
    {"group": None, "header": "표면이자율", "key": "coupon_rate_pct", "width": 11},
    {"group": None, "header": "만기이자율", "key": "maturity_rate_pct", "width": 11},
    {"group": "Put", "header": "시작일", "key": "put_start_date", "width": 12},
    {"group": "Put", "header": "기한(년)", "key": "put_term_years", "width": 9},
    {"group": "Put", "header": "YTP", "key": "put_ytp_pct", "width": 8},
    {"group": "Put", "header": "세부일정", "key": "put_schedule_json", "width": 36},
    {"group": "Call", "header": "시작일", "key": "call_start_date", "width": 12},
    {"group": "Call", "header": "기한(년)", "key": "call_term_years", "width": 9},
    {"group": "Call", "header": "YTC", "key": "call_ytc_pct", "width": 8},
    {"group": "Call", "header": "한도", "key": "call_cap_pct", "width": 8},
    {"group": "Call", "header": "세부일정", "key": "call_schedule_json", "width": 36},
    {"group": "Refixing", "header": "주기", "key": "refixing_cycle_months", "width": 8},
    {"group": "Refixing", "header": "리픽싱(원)", "key": "refixing_price_won", "width": 11},
    {"group": "Refixing", "header": "리픽싱(%)", "key": "refixing_floor_pct", "width": 10},
    {"group": "Refixing", "header": "리픽싱사유", "key": "refixing_reason", "width": 28},
    {"group": None, "header": "투자자", "key": "investors_text", "width": 34},
    {"group": None, "header": "당사검토", "key": "internal_review", "width": 12},
    {"group": None, "header": "주간사", "key": "underwriter", "width": 12},
    {"group": None, "header": "링크", "key": "dart_link", "width": 32},
    {"group": None, "header": "정정이전", "key": "previous_rcept_no", "width": 16},
]

NUMERIC_KEYS = {
    "issue_amount_eok",
    "strike_price",
    "premium_pct",
    "coupon_rate_pct",
    "maturity_rate_pct",
    "put_term_years",
    "put_ytp_pct",
    "call_term_years",
    "call_ytc_pct",
    "call_cap_pct",
    "refixing_cycle_months",
    "refixing_price_won",
    "refixing_floor_pct",
}
INTEGER_FORMAT_KEYS = {"issue_amount_eok", "strike_price"}
DECIMAL_FORMAT_KEYS = NUMERIC_KEYS - INTEGER_FORMAT_KEYS


@dataclass
class ExportResult:
    output_path: Path
    audit_path: Path | None
    raw_path: Path | None
    summary: dict


def default_output_path(filename: str = "mezzanine_reports.xlsx") -> Path:
    desktop = Path.home() / "Desktop"
    base_dir = desktop if desktop.exists() else Path.home()
    return base_dir / filename


def ensure_parent_dir(path) -> Path:
    value = Path(path).expanduser()
    value.parent.mkdir(parents=True, exist_ok=True)
    return value


def should_include_report(report: dict) -> bool:
    if report.get("corp_cls", "") not in {"Y", "K"}:
        return False
    report_nm = report.get("report_nm", "")
    for keyword_group in INCLUSION_KEYWORDS:
        if isinstance(keyword_group, list):
            if not any(keyword in report_nm for keyword in keyword_group):
                return False
        elif keyword_group not in report_nm:
            return False
    return True


def filter_reports(reports: list[dict]) -> list[dict]:
    return [report for report in reports if should_include_report(report)]


def format_issuer_stock_code(stock_code) -> str:
    value = normalize_stock_code(stock_code)
    return f"A{value}" if value else ""


def normalize_stock_code(stock_code) -> str:
    value = (stock_code or "").strip().upper()
    return value[1:] if value.startswith("A") else value


def clean_target_stock_name(value) -> str:
    text = (value or "").strip()
    if not text or text == "-":
        return ""
    text = SHARE_TYPE_SUFFIX_PATTERN.sub("", text)
    text = CORP_DESIGNATOR_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    normalized = MATCH_NORMALIZE_PATTERN.sub("", text).upper()
    if normalized in {"발행회사", "발행회사의"}:
        return ""
    return text


def normalize_company_name_for_match(value) -> str:
    cleaned = clean_target_stock_name(value)
    return MATCH_NORMALIZE_PATTERN.sub("", cleaned).upper() if cleaned else ""


def build_company_stock_code_map(corp_code_entries: list[dict]) -> dict:
    mapping = {}
    for entry in corp_code_entries or []:
        stock_code = (entry.get("stock_code") or "").strip()
        corp_name = (entry.get("corp_name") or "").strip()
        if not stock_code or not corp_name:
            continue
        normalized = normalize_company_name_for_match(corp_name)
        if normalized and normalized not in mapping:
            mapping[normalized] = stock_code
    return mapping


def infer_security_type(report_nm, parsed_type) -> str:
    if parsed_type and parsed_type != "N/A":
        return parsed_type
    report_nm = report_nm or ""
    if "전환사채" in report_nm:
        return "CB"
    if "교환사채" in report_nm:
        return "EB"
    if "신주인수권부사채" in report_nm:
        return "BW"
    return ""


def build_dart_link(rcept_no) -> str:
    value = (rcept_no or "").strip()
    return DART_MAIN_URL.format(rcept_no=value) if value else ""


def extract_filing_date_from_rcept_no(rcept_no) -> str:
    value = (rcept_no or "").strip()
    if not re.fullmatch(r"\d{14}", value):
        return ""
    try:
        return datetime.strptime(value[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def extract_report_header(report_nm) -> str:
    match = re.match(r"\s*\[([^\]]+)\]", report_nm or "")
    return match.group(1).strip() if match else ""


def parse_numeric_value(value):
    if value in (None, "", "-"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", "").replace("%", "")
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def parse_iso_date(value):
    text = (value or "").strip()
    if not text or text == "-":
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_option_schedule_triplets(schedules) -> list[list[str]]:
    normalized_rows = []
    for item in schedules or []:
        if isinstance(item, dict):
            row = [item.get("청구시작일") or "-", item.get("청구종료일") or "-", item.get("지급일") or "-"]
        elif isinstance(item, (list, tuple)):
            row = list(item[:3])
        else:
            continue
        while len(row) < 3:
            row.append("-")
        normalized_rows.append([(value or "-") for value in row[:3]])
    return normalized_rows


def get_first_option_start_date(schedules) -> str:
    triplets = normalize_option_schedule_triplets(schedules)
    if not triplets:
        return ""
    claim_start_date, _, payment_date = triplets[0]
    if claim_start_date and claim_start_date != "-":
        return claim_start_date
    return "" if payment_date == "-" else payment_date


def calculate_option_term_years(issue_date, schedules):
    triplets = normalize_option_schedule_triplets(schedules)
    if not issue_date or not triplets:
        return None
    issue_date_value = parse_iso_date(issue_date)
    payment_date_value = parse_iso_date((triplets[0][2] or "").strip())
    if not issue_date_value or not payment_date_value or payment_date_value < issue_date_value:
        return None
    return round((payment_date_value - issue_date_value).days / 365.25, 1)


def serialize_option_schedule(schedules) -> str:
    triplets = normalize_option_schedule_triplets(schedules)
    return json.dumps(triplets, ensure_ascii=False) if triplets else ""


def format_investors_text(parsed: dict) -> str:
    issue_targets = parsed.get("발행대상자") or []
    if issue_targets:
        formatted_targets = []
        for row in issue_targets:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            name = str(row[0] or "").strip()
            amount = parse_numeric_value(row[1] if len(row) > 1 else None)
            if not name:
                continue
            if amount is None:
                formatted_targets.append(name)
            else:
                amount_in_eok = amount / 10**8
                amount_text = str(int(amount_in_eok)) if float(amount_in_eok).is_integer() else f"{amount_in_eok:.1f}"
                formatted_targets.append(f"{name} {amount_text}")
        if formatted_targets:
            return "\n".join(formatted_targets)
    investor_rows = parsed.get("투자자별투자액") or []
    if investor_rows:
        formatted = []
        for investor in investor_rows:
            name = (investor.get("name") or "").strip()
            amount = parse_numeric_value(investor.get("amount"))
            if not name:
                continue
            if amount is None:
                formatted.append(name)
            else:
                amount_in_eok = amount / 10**8
                amount_text = str(int(amount_in_eok)) if float(amount_in_eok).is_integer() else f"{amount_in_eok:.1f}"
                formatted.append(f"{name} {amount_text}")
        if formatted:
            return "\n".join(formatted)
    fallback = parsed.get("발행대상")
    return "" if fallback in (None, "-", "") else str(fallback)


def parse_report_documents(report: dict, api_key: str | None = None) -> dict:
    if report.get("html_path") or report.get("source_file"):
        return parse_report_document(report, [])
    return parse_report_document(report, fetch_document_soups(report.get("rcept_no"), api_key=api_key))


def previous_rcept_no_from_parsed(parsed: dict, current_rcept_no: str) -> str:
    families = parsed.get("correction_families") or {}
    current = str(current_rcept_no or parsed.get("rcept_no") or "").strip()
    for family in families.values():
        members = sorted(list(family.get("members") or []), key=lambda item: int(item.get("sequence") or 0))
        for index, member in enumerate(members):
            if str(member.get("rcept_no") or "").strip() == current or str(member.get("acpt_no") or "").strip() == current:
                if index == 0:
                    return ""
                return str(members[index - 1].get("rcept_no") or members[index - 1].get("acpt_no") or "")
    return ""


def build_export_row(
    report: dict,
    parsed: dict,
    company_stock_code_map: dict | None = None,
    previous_rcept_no: str = "",
) -> dict:
    company_stock_code_map = company_stock_code_map or {}
    issue_date = parsed.get("납입일") or ""
    security_type = infer_security_type(report.get("report_nm"), parsed.get("종류"))
    target_company_name = clean_target_stock_name(parsed.get("대상주식"))
    if not target_company_name and security_type in {"CB", "BW"}:
        target_company_name = clean_target_stock_name(report.get("corp_name"))
    target_stock_code = company_stock_code_map.get(normalize_company_name_for_match(target_company_name), "")
    put_schedules = parsed.get("PUT옵션일정표") or parsed.get("_PUT옵션일정표상세") or []
    call_schedules = parsed.get("CALL옵션일정표") or parsed.get("_CALL옵션일정표상세") or []

    return {
        "rcept_no": report.get("rcept_no", ""),
        "filing_date": extract_filing_date_from_rcept_no(report.get("rcept_no")),
        "report_header": extract_report_header(report.get("report_nm")),
        "issuer_company_name": report.get("corp_name", ""),
        "issuer_market": ISSUER_MARKET_LABELS.get(report.get("corp_cls"), report.get("corp_cls", "")),
        "issuer_stock_code": format_issuer_stock_code(report.get("stock_code")),
        "target_company_name": target_company_name,
        "target_stock_code": format_issuer_stock_code(target_stock_code),
        "round": parsed.get("회차", ""),
        "security_type": security_type,
        "issue_amount_eok": parse_numeric_value(parsed.get("발행금액") if parsed.get("발행금액") is not None else parsed.get("발행금액(억)")),
        "strike_price": parse_numeric_value(parsed.get("행사가액") if parsed.get("행사가액") is not None else parsed.get("전환가액(원)")),
        "premium_pct": parse_numeric_value(parsed.get("할증률(%)")),
        "issue_date": issue_date if issue_date != "-" else "",
        "maturity_date": (parsed.get("만기일") or "") if parsed.get("만기일") != "-" else "",
        "coupon_rate_pct": parse_numeric_value(parsed.get("표면이율")),
        "maturity_rate_pct": parse_numeric_value(parsed.get("만기이율")),
        "put_start_date": get_first_option_start_date(put_schedules),
        "put_term_years": calculate_option_term_years(issue_date, put_schedules),
        "put_ytp_pct": parse_numeric_value(parsed.get("YTP(%)")),
        "put_schedule_json": serialize_option_schedule(put_schedules),
        "call_start_date": get_first_option_start_date(call_schedules),
        "call_term_years": calculate_option_term_years(issue_date, call_schedules),
        "call_ytc_pct": parse_numeric_value(parsed.get("YTC(%)")),
        "call_cap_pct": parse_numeric_value(parsed.get("CALL행사한도(%)")),
        "call_schedule_json": serialize_option_schedule(call_schedules),
        "refixing_cycle_months": parse_numeric_value(parsed.get("리픽싱주가")),
        "refixing_price_won": parse_numeric_value(parsed.get("리픽싱(원)")),
        "refixing_floor_pct": parse_numeric_value(parsed.get("리픽싱(%)") if parsed.get("리픽싱(%)") is not None else parsed.get("리픽싱가격")),
        "refixing_reason": parsed.get("리픽싱사유") or parsed.get("리픽싱내용") or "",
        "investors_text": format_investors_text(parsed),
        "internal_review": "",
        "underwriter": "",
        "dart_link": build_dart_link(report.get("rcept_no")),
        "previous_rcept_no": previous_rcept_no,
    }


def build_export_rows_with_audit(data: dict, api_key: str | None = None, progress_callback=None) -> tuple:
    reports = filter_reports(data.get("list", []))
    company_stock_code_map = {}
    corp_code_error = ""
    try:
        company_stock_code_map = build_company_stock_code_map(fetch_corp_code_entries(api_key=api_key))
    except Exception as exc:
        corp_code_error = str(exc)
        if progress_callback:
            progress_callback(f"종목코드 매핑 다운로드 실패: {exc}")

    rows = []
    audit_rows = []
    parse_failures = []
    family_lookup_failures = []
    total_reports = len(reports)
    for index, report in enumerate(reports, start=1):
        if progress_callback:
            progress_callback(f"파싱 {index}/{total_reports}: {report.get('corp_name', '')} {report.get('rcept_no', '')}")
        parsed = {}
        parse_error = ""
        try:
            parsed = parse_report_documents(report, api_key=api_key)
        except Exception as exc:
            parse_error = str(exc)
            parse_failures.append({"rcept_no": report.get("rcept_no"), "error": parse_error})
            if progress_callback:
                progress_callback(f"문서 파싱 실패 {report.get('rcept_no', '')}: {exc}")

        previous_rcept_no = ""
        family_lookup_error = ""
        try:
            previous_rcept_no = previous_rcept_no_from_parsed(parsed, report.get("rcept_no", ""))
            if not previous_rcept_no and not (report.get("html_path") or report.get("source_file")):
                previous_rcept_no = fetch_previous_family_rcept_no(report.get("rcept_no", ""))
        except Exception as exc:
            family_lookup_error = str(exc)
            family_lookup_failures.append({"rcept_no": report.get("rcept_no"), "error": family_lookup_error})
            if progress_callback:
                progress_callback(f"정정이전 조회 실패 {report.get('rcept_no', '')}: {exc}")

        export_row = build_export_row(
            report,
            parsed,
            company_stock_code_map=company_stock_code_map,
            previous_rcept_no=previous_rcept_no,
        )
        rows.append(export_row)
        audit_rows.append(
            {
                "rcept_no": report.get("rcept_no", ""),
                "report": {
                    "corp_name": report.get("corp_name", ""),
                    "stock_code": report.get("stock_code", ""),
                    "corp_cls": report.get("corp_cls", ""),
                    "report_nm": report.get("report_nm", ""),
                    "rcept_no": report.get("rcept_no", ""),
                    "rcept_dt": report.get("rcept_dt", ""),
                },
                "parsed": parsed,
                "export_row": export_row,
                "error": parse_error,
                "family_lookup_error": family_lookup_error,
            }
        )

    summary = {
        "bgn_de": data.get("bgn_de"),
        "end_de": data.get("end_de"),
        "total_count": data.get("total_count", 0),
        "filtered_count": total_reports,
        "exported_count": len(rows),
        "parse_failure_count": len(parse_failures),
        "family_lookup_failure_count": len(family_lookup_failures),
        "corp_code_mapping_error": corp_code_error,
    }
    rows.sort(key=lambda row: (row.get("filing_date") or "9999-99-99", row.get("rcept_no") or ""))
    audit_rows.sort(
        key=lambda row: (
            row.get("export_row", {}).get("filing_date") or "9999-99-99",
            row.get("export_row", {}).get("rcept_no") or "",
        )
    )
    return rows, summary, audit_rows


def export_reports(data: dict, output_path, audit_json_path=None, api_key: str | None = None, progress_callback=None) -> ExportResult:
    output_path = ensure_parent_dir(output_path)
    rows, summary, audit_rows = build_export_rows_with_audit(data, api_key=api_key, progress_callback=progress_callback)
    workbook = Workbook()
    report_sheet = workbook.active
    report_sheet.title = "reports"
    _write_summary_sheet(workbook, summary)
    _write_report_sheet(report_sheet, rows)
    workbook.save(output_path)

    audit_path = None
    if ENABLE_AUDIT_JSON:
        audit_json_path = audit_json_path or output_path.with_name(f"{output_path.stem}_audit.json")
        audit_path = save_audit_rows_json(audit_rows, audit_json_path)
    raw_path = save_raw_reports_json(data, output_path)
    return ExportResult(output_path=output_path, audit_path=audit_path, raw_path=raw_path, summary=summary)


def save_audit_rows_json(audit_rows: list[dict], output_path) -> Path:
    output_path = ensure_parent_dir(output_path)
    output_path.write_text(json.dumps(audit_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def save_raw_reports_json(data: dict, excel_output_path) -> Path:
    excel_output_path = ensure_parent_dir(excel_output_path)
    raw_json_path = excel_output_path.with_name(f"{excel_output_path.stem}_raw.json")
    raw_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw_json_path


def _write_summary_sheet(workbook, summary: dict) -> None:
    summary_sheet = workbook.create_sheet("summary")
    summary_sheet.append(["key", "value"])
    for key, value in summary.items():
        summary_sheet.append([key, value])
    summary_sheet.freeze_panes = "A2"


def _write_report_sheet(sheet, rows: list[dict]) -> None:
    _write_header(sheet)
    _write_rows(sheet, rows)
    sheet.freeze_panes = "A3"
    sheet.sheet_view.showGridLines = False


def _write_header(sheet) -> None:
    current_column = 1
    while current_column <= len(COLUMN_SPECS):
        spec = COLUMN_SPECS[current_column - 1]
        group = spec["group"]
        if group is None:
            sheet.cell(row=1, column=current_column, value=spec["header"])
            sheet.merge_cells(start_row=1, start_column=current_column, end_row=2, end_column=current_column)
            _style_header_range(sheet, 1, current_column, 2, current_column)
            current_column += 1
            continue

        start_column = current_column
        while current_column <= len(COLUMN_SPECS) and COLUMN_SPECS[current_column - 1]["group"] == group:
            current_column += 1
        end_column = current_column - 1
        sheet.cell(row=1, column=start_column, value=group)
        sheet.merge_cells(start_row=1, start_column=start_column, end_row=1, end_column=end_column)
        _style_header_range(sheet, 1, start_column, 1, end_column)
        for column in range(start_column, end_column + 1):
            _style_header_cell(sheet.cell(row=2, column=column, value=COLUMN_SPECS[column - 1]["header"]))

    for index, spec in enumerate(COLUMN_SPECS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = spec["width"]
    sheet.row_dimensions[1].height = 22
    sheet.row_dimensions[2].height = 24


def _style_header_cell(cell) -> None:
    cell.fill = HEADER_FILL
    cell.font = HEADER_FONT
    cell.alignment = HEADER_ALIGNMENT
    cell.border = HEADER_BORDER


def _style_header_range(sheet, start_row: int, start_column: int, end_row: int, end_column: int) -> None:
    for row in range(start_row, end_row + 1):
        for column in range(start_column, end_column + 1):
            cell = sheet.cell(row=row, column=column)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = HEADER_ALIGNMENT
            cell.border = Border(
                left=BORDER_SIDE if column == start_column else None,
                right=BORDER_SIDE if column == end_column else None,
                top=BORDER_SIDE if row == start_row else None,
                bottom=BORDER_SIDE if row == end_row else None,
            )


def _write_rows(sheet, rows: list[dict]) -> None:
    for row_index, row in enumerate(rows, start=3):
        for column_index, spec in enumerate(COLUMN_SPECS, start=1):
            value = row.get(spec["key"], "")
            cell = sheet.cell(row=row_index, column=column_index, value=value)
            _style_body_cell(cell, spec["key"])
            if spec["key"] == "dart_link" and value:
                cell.hyperlink = value
                cell.font = LINK_FONT
        if row.get("previous_rcept_no") and sheet.cell(row=row_index, column=32).value in (None, ""):
            sheet.cell(row=row_index, column=32, value=row.get("previous_rcept_no"))
        sheet.row_dimensions[row_index].height = 42


def _style_body_cell(cell, key: str) -> None:
    cell.alignment = BODY_ALIGNMENT
    cell.border = BODY_BORDER
    if key in INTEGER_FORMAT_KEYS and isinstance(cell.value, (int, float)):
        cell.number_format = "#,##0"
    elif key in DECIMAL_FORMAT_KEYS and isinstance(cell.value, (int, float)):
        cell.number_format = "0.0"
