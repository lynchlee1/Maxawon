import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests
from lxml import etree, html


KIND_SEARCH_PAGE_URL = "https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain"
KIND_SEARCH_RESULTS_URL = "https://kind.krx.co.kr/disclosure/details.do"
KIND_DISCLOSURE_VIEWER_URL = "https://kind.krx.co.kr/common/disclsviewer.do"
VIEWER_HTML_FILENAME_TEMPLATE = "{acpt_no}.html"
MAX_REQUESTS_PER_MINUTE = 70
MIN_REQUEST_INTERVAL_SECONDS = 0.0
DEFAULT_HTML_WORKERS = 4
STOCK_RELATED_BOND_DISCLOSURE_CODE = "0119"
MEZZANINE_REPORT_SEARCH_TERMS = (
    "전환사채발행결정",
    "전환사채권발행결정",
    "교환사채발행결정",
    "교환사채권발행결정",
    "신주인수권부사채발행결정",
    "신주인수권부사채권발행결정",
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": KIND_SEARCH_PAGE_URL,
    "Origin": "https://kind.krx.co.kr",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

OPEN_VIEWER_RE = re.compile(
    r"openDisclsViewer\(\s*['\"](?P<acpt_no>[^'\"]*)['\"]\s*,\s*['\"](?P<doc_no>[^'\"]*)['\"]\s*\)"
)
TITLE_FLAG_RE = re.compile(r"\[([^\[\]]+)\]")
SET_PATH_RE = re.compile(
    r"parent\.setPath\(\s*'(?P<toc_loc_path>[^']*)'\s*,\s*'(?P<doc_loc_path>[^']*)'\s*,\s*"
    r"'(?P<doc_server_path>[^']*)'\s*,\s*'(?P<form_upclss_cd>[^']*)'\s*,\s*"
    r"'(?P<snd_loc_tp_cd>[^']*)'\s*\)"
)
VIEWER_STOCK_CODE_RE = re.compile(r"<h1[^>]*>\s*[^<]*\((?P<stock_code>[0-9A-Za-z]{6})\)\s*</h1>", re.IGNORECASE)


class RateLimiter:
    def __init__(
        self,
        max_requests_per_minute: int = MAX_REQUESTS_PER_MINUTE,
        min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    ):
        if max_requests_per_minute < 1 or max_requests_per_minute > MAX_REQUESTS_PER_MINUTE:
            raise ValueError("max_requests_per_minute must be between 1 and 70")
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be non-negative")
        self.max_requests_per_minute = max_requests_per_minute
        self.min_interval_seconds = min_interval_seconds
        self.request_timestamps: list[float] = []
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            while True:
                now = time.time()
                self.request_timestamps = [t for t in self.request_timestamps if now - t < 60]
                wait_for_min_interval = 0.0
                if self.request_timestamps:
                    wait_for_min_interval = self.min_interval_seconds - (now - self.request_timestamps[-1])
                wait_for_minute_window = 0.0
                if len(self.request_timestamps) >= self.max_requests_per_minute:
                    wait_for_minute_window = 60 - (now - self.request_timestamps[0])
                wait_seconds = max(wait_for_min_interval, wait_for_minute_window, 0.0)
                if wait_seconds <= 0:
                    self.request_timestamps.append(now)
                    return
                time.sleep(min(wait_seconds, 0.1))


def _clean_text(value) -> str:
    return " ".join(str(value or "").split())


def _date_text(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _compact_date_text(value: date) -> str:
    return value.strftime("%Y%m%d")


def _remove_whitespace(value: str) -> str:
    return "".join(str(value or "").split())


def _clean_search_text(value: str) -> str:
    text = str(value or "")
    cleaned = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            depth = 0
            last_close_index = -1
            scan_index = index
            while scan_index < len(text):
                current = text[scan_index]
                if current == "(":
                    depth += 1
                elif current == ")":
                    depth -= 1
                    last_close_index = scan_index
                    if depth <= 0:
                        scan_index += 1
                        while scan_index < len(text) and text[scan_index] == ")":
                            scan_index += 1
                        break
                scan_index += 1
            else:
                scan_index = last_close_index + 1 if last_close_index >= 0 else len(text)
            index = scan_index
            continue
        if char == ")":
            index += 1
            continue
        cleaned.append(char)
        index += 1
    return "".join(cleaned)


def _build_search_payload(
    *,
    start_date: date,
    end_date: date,
    page_no: int,
    page_count: int = 100,
    last_reprt_at: str = "ALL",
) -> dict[str, str]:
    payload = [
        ("method", "searchDetailsSub"),
        ("currentPageSize", str(page_count)),
        ("pageIndex", str(page_no)),
        ("searchCodeType", ""),
        ("repIsuSrtCd", ""),
        ("allRepIsuSrtCd", ""),
        ("oldSearchCorpName", ""),
        ("disclosureType", ""),
        ("disTypevalue", ""),
        ("reportNm", ""),
        ("reportCd", ""),
        ("searchCorpName", ""),
        ("business", ""),
        ("marketType", ""),
        ("settlementMonth", ""),
        ("securities", "1"),
        ("submitOblgNm", ""),
        ("enterprise", ""),
        ("fromDate", _date_text(start_date)),
        ("toDate", _date_text(end_date)),
        ("reportNmTemp", ""),
        ("reportNmPop", ""),
        ("orderMode", "1"),
        ("orderStat", "D"),
        ("forward", "details_sub"),
        ("disclosureType01", f"{STOCK_RELATED_BOND_DISCLOSURE_CODE}|"),
        ("pDisclosureType01", f"{STOCK_RELATED_BOND_DISCLOSURE_CODE}|"),
        ("disclosureTypeArr01", STOCK_RELATED_BOND_DISCLOSURE_CODE),
    ]
    for suffix in ("02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "13", "14", "20"):
        payload.extend(((f"disclosureType{suffix}", ""), (f"pDisclosureType{suffix}", "")))
    normalized_last_reprt_at = (last_reprt_at or "ALL").upper()
    if normalized_last_reprt_at == "Y":
        payload.append(("lastReport", "T"))
        payload.append(("bfrDsclsType", ""))
    elif normalized_last_reprt_at == "N":
        payload.append(("bfrDsclsType", "on"))
    return payload


def _parse_onclick(value: str | None) -> tuple[str, str]:
    match = OPEN_VIEWER_RE.search(value or "")
    if not match:
        return "", ""
    return match.group("acpt_no").strip(), match.group("doc_no").strip()


def _selected_main_doc_no(markup: bytes | str) -> str:
    if isinstance(markup, bytes):
        markup = markup.decode("utf-8", errors="replace")
    parser = html.HTMLParser(recover=True, huge_tree=True)
    root = html.fromstring(markup, parser=parser)
    selected = root.xpath("//select[@id='mainDoc' or @name='mainDoc']/option[@selected]")
    options = selected or root.xpath("//select[@id='mainDoc' or @name='mainDoc']/option[string-length(normalize-space(@value)) > 0]")
    for option in options:
        raw_value = _clean_text(option.get("value"))
        if raw_value:
            return raw_value.split("|", 1)[0].strip()
    return ""


def _search_content_doc_path(markup: bytes | str) -> str:
    if isinstance(markup, bytes):
        markup = markup.decode("utf-8", errors="replace")
    match = SET_PATH_RE.search(markup)
    if not match:
        return ""
    return match.group("doc_loc_path").strip()


def parse_viewer_stock_code(markup: bytes | str) -> str:
    if isinstance(markup, bytes):
        markup = markup.decode("utf-8", errors="replace")
    match = VIEWER_STOCK_CODE_RE.search(markup or "")
    return match.group("stock_code").upper() if match else ""


def _title_flags(title: str) -> list[str]:
    flags = []
    for match in TITLE_FLAG_RE.finditer(title or ""):
        flag = _clean_text(match.group(1))
        if flag and flag not in flags:
            flags.append(flag)
    return flags


def _node_text(node) -> str:
    if node is None:
        return ""
    return _clean_text(" ".join(node.itertext()))


def _find_results_table(root):
    for table in root.xpath("//table"):
        summary = _clean_text(table.get("summary"))
        if "회사명" in summary and "공시제목" in summary:
            return table
    tables = root.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' list ')]")
    return tables[0] if tables else None


def _parse_result_rows(markup: bytes | str) -> list[dict]:
    parser = html.HTMLParser(recover=True, huge_tree=True)
    if isinstance(markup, bytes):
        markup = markup.decode("utf-8", errors="replace")
    root = html.fromstring(markup, parser=parser)
    table = _find_results_table(root)
    if table is None:
        return []
    rows = []
    for tr in table.xpath(".//tr"):
        cells = tr.xpath("./td")
        if len(cells) < 5:
            continue
        company_cell = cells[2]
        title_cell = cells[3]
        submitter_cell = cells[4]
        company_link = (company_cell.xpath(".//a[@id='companysum']") or company_cell.xpath(".//a") or [None])[0]
        title_link = (title_cell.xpath(".//a") or [None])[0]
        title = _clean_text(title_link.get("title") if title_link is not None else "") or _node_text(title_cell)
        acpt_no, doc_no = _parse_onclick(title_link.get("onclick") if title_link is not None else "")
        if not acpt_no:
            continue
        company_name = _clean_text(company_link.get("title") if company_link is not None else "") or _node_text(company_cell)
        market_labels = [_clean_text(img.get("alt")) for img in company_cell.xpath(".//img") if _clean_text(img.get("alt"))]
        flags = _title_flags(_node_text(title_cell) or title)
        report_nm = title
        if flags and not report_nm.startswith("["):
            report_nm = "".join(f"[{flag}]" for flag in flags) + report_nm
        rows.append(
            {
                "corp_name": company_name,
                "corp_cls": _market_to_corp_cls(market_labels[0] if market_labels else ""),
                "stock_code": "",
                "report_nm": report_nm,
                "title": report_nm,
                "rcept_no": acpt_no,
                "acpt_no": acpt_no,
                "doc_no": doc_no,
                "rcept_dt": re.sub(r"\D", "", _node_text(cells[1]))[:8],
                "submitter": _node_text(submitter_cell),
                "market": market_labels[0] if market_labels else "",
                "is_correction_report": "정정" in flags,
            }
        )
    return rows


def _market_to_corp_cls(label: str) -> str:
    if "유가" in label or "코스피" in label:
        return "Y"
    if "코스닥" in label:
        return "K"
    if "코넥스" in label:
        return "N"
    return ""


def _matches_mezzanine_title(report: dict) -> bool:
    title = report.get("report_nm", "")
    title_candidates = {
        _remove_whitespace(title),
        _remove_whitespace(_clean_search_text(title)),
    }
    return (
        any(term in candidate for term in MEZZANINE_REPORT_SEARCH_TERMS for candidate in title_candidates)
        and "매수선택권행사자지정" not in title
    )


def _viewer_url(acpt_no: str, doc_no: str = "") -> str:
    return f"{KIND_DISCLOSURE_VIEWER_URL}?{urlencode({'method': 'search', 'acptno': acpt_no, 'docno': doc_no, 'viewerhost': '', 'viewerport': ''})}"


def _new_kind_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def _limited_get(session: requests.Session, limiter: RateLimiter, url: str, **kwargs) -> requests.Response:
    limiter.wait()
    return session.get(url, **kwargs)


def _limited_post(session: requests.Session, limiter: RateLimiter, url: str, **kwargs) -> requests.Response:
    limiter.wait()
    return session.post(url, **kwargs)


def _fetch_content_html(session: requests.Session, doc_no: str, *, timeout: int, limiter: RateLimiter) -> bytes:
    response = _limited_get(session, limiter, KIND_DISCLOSURE_VIEWER_URL, params={"method": "searchContents", "docNo": doc_no}, timeout=timeout)
    response.raise_for_status()
    doc_path = _search_content_doc_path(response.content)
    if not doc_path:
        raise ValueError(f"KIND content path not found for docNo={doc_no}")
    response = _limited_get(session, limiter, doc_path, timeout=timeout)
    response.raise_for_status()
    return response.content


def _download_report_html(report: dict, *, html_dir: Path, content_dir: Path, limiter: RateLimiter, timeout: int) -> dict:
    acpt_no = report["acpt_no"]
    viewer_path = html_dir / VIEWER_HTML_FILENAME_TEMPLATE.format(acpt_no=acpt_no)
    content_path = content_dir / VIEWER_HTML_FILENAME_TEMPLATE.format(acpt_no=acpt_no)
    with _new_kind_session() as session:
        if not viewer_path.exists():
            viewer = _limited_get(session, limiter, _viewer_url(acpt_no, report.get("doc_no") or ""), timeout=timeout)
            viewer.raise_for_status()
            viewer_path.write_bytes(viewer.content)
            viewer_content = viewer.content
        else:
            viewer_content = viewer_path.read_bytes()

        doc_no = report.get("doc_no") or _selected_main_doc_no(viewer_content)
        if doc_no and not content_path.exists():
            content_path.write_bytes(_fetch_content_html(session, doc_no, timeout=timeout, limiter=limiter))

    return {
        "viewer_html_path": str(viewer_path),
        "html_path": str(content_path if content_path.exists() else viewer_path),
        "doc_no": doc_no,
        "stock_code": parse_viewer_stock_code(viewer_content) or report.get("stock_code", ""),
    }


def fetch_mezzanine_reports(
    start_date: date,
    end_date: date,
    *,
    output_dir=None,
    last_reprt_at: str = "ALL",
    max_requests_per_minute: int = MAX_REQUESTS_PER_MINUTE,
    html_max_workers: int = DEFAULT_HTML_WORKERS,
    progress_callback=None,
    timeout: int = 30,
) -> dict:
    if (last_reprt_at or "ALL").upper() not in {"ALL", "Y", "N"}:
        raise ValueError("last_reprt_at는 'ALL', 'Y' 또는 'N'이어야 합니다.")
    limiter = RateLimiter(max_requests_per_minute)
    output_root = Path(output_dir or Path.home() / "Desktop" / "weekly_mezz_kind").expanduser().resolve()
    list_dir = output_root / "kind_result_pages"
    html_dir = output_root / "viewer_html"
    content_dir = output_root / "viewer_html_contents"
    list_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)

    html_max_workers = max(1, int(html_max_workers or 1))
    session = _new_kind_session()
    try:
        _limited_get(session, limiter, KIND_SEARCH_PAGE_URL, timeout=timeout).raise_for_status()
        reports = []
        seen_rcept_numbers = set()
        page_no = 1
        while True:
            payload = _build_search_payload(
                start_date=start_date,
                end_date=end_date,
                page_no=page_no,
                last_reprt_at=last_reprt_at,
            )
            response = _limited_post(session, limiter, KIND_SEARCH_RESULTS_URL, data=payload, timeout=timeout)
            response.raise_for_status()
            page_path = list_dir / f"{page_no:03d}_post_page_{page_no:05d}.body"
            page_path.write_bytes(response.content)
            page_reports = [row for row in _parse_result_rows(response.content) if _matches_mezzanine_title(row)]
            new_reports = []
            for row in page_reports:
                rcept_no = row.get("rcept_no")
                if rcept_no in seen_rcept_numbers:
                    continue
                seen_rcept_numbers.add(rcept_no)
                new_reports.append(row)
            if progress_callback:
                progress_callback(f"KIND results page {page_no}: found {len(new_reports)} new mezzanine disclosures")
            reports.extend(new_reports)
            if page_no >= _infer_total_pages(response.content, page_no):
                break
            page_no += 1

        if reports:
            completed = 0
            workers = min(html_max_workers, len(reports))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_report = {
                    executor.submit(
                        _download_report_html,
                        report,
                        html_dir=html_dir,
                        content_dir=content_dir,
                        limiter=limiter,
                        timeout=timeout,
                    ): report
                    for report in reports
                }
                for future in as_completed(future_to_report):
                    report = future_to_report[future]
                    report.update(future.result())
                    completed += 1
                    if progress_callback:
                        progress_callback(f"KIND HTML {completed}/{len(reports)}: {report.get('acpt_no', '')}")

        manifest = {
            "format": "weekly_mezz_kind_download_v1",
            "bgn_de": _compact_date_text(start_date),
            "end_de": _compact_date_text(end_date),
            "search_terms": list(MEZZANINE_REPORT_SEARCH_TERMS),
            "list": reports,
        }
        (output_root / "kind_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "status": "000",
            "message": "정상",
            "bgn_de": _compact_date_text(start_date),
            "end_de": _compact_date_text(end_date),
            "total_count": len(reports),
            "total_page": page_no,
            "search_terms": list(MEZZANINE_REPORT_SEARCH_TERMS),
            "list": reports,
        }
    finally:
        session.close()


def _infer_total_pages(markup: bytes, fallback: int) -> int:
    text = markup.decode("utf-8", errors="replace")
    numbers = [int(value.replace(",", "")) for value in re.findall(r"pageIndex['\"]?\s*[,=]\s*['\"]?(\d+)", text)]
    if numbers:
        return max(numbers)
    match = re.search(r"총\s*([0-9,]+)\s*건", text)
    if match:
        total = int(match.group(1).replace(",", ""))
        return max(1, (total + 99) // 100)
    return fallback
