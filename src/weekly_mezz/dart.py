import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from io import BytesIO

import requests
from bs4 import BeautifulSoup

from weekly_mezz.settings import get_api_key
from weekly_mezz.xml import parse_xml_with_recovery

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DOCUMENT_URL = "https://opendart.fss.or.kr/api/document.xml"
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_MAIN_URL = "https://dart.fss.or.kr/dsaf001/main.do"
DART_VIEWER_URL = "https://dart.fss.or.kr/report/viewer.do"
NON_CONTENT_BODY_CHILD_TAGS = {"LIBRARY", "CORRECTION", "COVER", "HEAD", "FOOTNOTE"}
VIEWER_NODE_PATTERN = re.compile(
    r"node1\['text'\]\s*=\s*\"(?P<text>.*?)\";.*?"
    r"node1\['rcpNo'\]\s*=\s*\"(?P<rcpNo>\d+)\";.*?"
    r"node1\['dcmNo'\]\s*=\s*\"(?P<dcmNo>\d+)\";.*?"
    r"node1\['eleId'\]\s*=\s*\"(?P<eleId>\d+)\";.*?"
    r"node1\['offset'\]\s*=\s*\"(?P<offset>\d+)\";.*?"
    r"node1\['length'\]\s*=\s*\"(?P<length>\d+)\";.*?"
    r"node1\['dtd'\]\s*=\s*\"(?P<dtd>[^\"]+)\";",
    re.DOTALL,
)


def require_api_key(api_key: str | None = None) -> str:
    value = (api_key or get_api_key()).strip()
    if not value:
        raise ValueError("OPENDART_API_KEY가 설정되어 있지 않습니다.")
    return value


def fetch_report_list(params: dict, timeout: int = 30) -> dict:
    response = requests.get(LIST_URL, params=params, timeout=timeout)
    data = response.json()
    if data.get("status") != "000":
        raise RuntimeError(data.get("message", "API error"))
    return data


def fetch_mezzanine_reports(
    start_date: date,
    end_date: date,
    api_key: str | None = None,
    progress_callback=None,
    report_type: str = "B001",
    last_reprt_at: str = "N",
) -> dict:
    api_key = require_api_key(api_key)
    last_reprt_at = (last_reprt_at or "N").upper()
    if last_reprt_at not in {"Y", "N"}:
        raise ValueError("last_reprt_at는 'Y' 또는 'N'이어야 합니다.")

    params = {
        "crtfc_key": api_key,
        "bgn_de": start_date.strftime("%Y%m%d"),
        "end_de": end_date.strftime("%Y%m%d"),
        "last_reprt_at": last_reprt_at,
        "pblntf_ty": "B",
        "pblntf_detail_ty": report_type,
        "page_count": 100,
    }
    first_page = fetch_report_list(params)
    total_page = int(first_page.get("total_page") or 1)
    reports = list(first_page.get("list", []))
    if progress_callback:
        progress_callback(f"Page 1/{total_page}: collected {len(reports)} reports")

    for page_no in range(2, total_page + 1):
        page_data = fetch_report_list({**params, "page_no": page_no})
        current_reports = page_data.get("list", [])
        reports.extend(current_reports)
        if progress_callback:
            progress_callback(f"Page {page_no}/{total_page}: collected {len(current_reports)} reports")

    return {
        "status": "000",
        "message": "정상",
        "bgn_de": params["bgn_de"],
        "end_de": params["end_de"],
        "total_count": len(reports),
        "total_page": total_page,
        "list": reports,
    }


def fetch_document_soups(rcept_no: str, api_key: str | None = None, timeout: int = 30) -> list:
    api_key = require_api_key(api_key)
    response = requests.get(
        DOCUMENT_URL,
        params={"crtfc_key": api_key, "rcept_no": rcept_no},
        timeout=timeout,
    )
    try:
        with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
            soups = []
            for name in zip_file.namelist():
                with zip_file.open(name) as file:
                    text = _decode_document_bytes(file.read())
                    if text:
                        soups.append(parse_xml_with_recovery(text))
            if _has_meaningful_document_content(soups):
                return soups
    except zipfile.BadZipFile:
        pass

    return _fetch_viewer_soups(rcept_no, timeout=timeout)


def fetch_corp_code_entries(api_key: str | None = None, timeout: int = 30) -> list[dict]:
    api_key = require_api_key(api_key)
    response = requests.get(CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=timeout)
    response.raise_for_status()
    try:
        with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
            for name in zip_file.namelist():
                with zip_file.open(name) as file:
                    return _parse_corp_code_entries(file.read())
    except zipfile.BadZipFile as exc:
        raise RuntimeError("corpCode.xml 응답을 ZIP으로 해석하지 못했습니다.") from exc
    return []


def _decode_document_bytes(data: bytes) -> str | None:
    for encoding in ("utf-8", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _response_text(response) -> str:
    encoding = getattr(response, "apparent_encoding", None) or response.encoding or "utf-8"
    return response.content.decode(encoding, errors="replace")


def _parse_corp_code_entries(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    entries = []
    for node in root.findall(".//list"):
        entry = {
            "corp_code": (node.findtext("corp_code") or "").strip(),
            "corp_name": (node.findtext("corp_name") or "").strip(),
            "stock_code": (node.findtext("stock_code") or "").strip(),
            "modify_date": (node.findtext("modify_date") or "").strip(),
        }
        if entry["corp_name"]:
            entries.append(entry)
    return entries


def _is_within_correction_block(element) -> bool:
    current = element
    while current is not None:
        name = getattr(current, "name", None)
        if isinstance(name, str) and name.upper() == "CORRECTION":
            return True
        current = getattr(current, "parent", None)
    return False


def _has_meaningful_body_content(soup) -> bool:
    body = soup.find(["BODY", "body"])
    if body is None:
        return bool(soup.find(["table", "TABLE", "p", "P"]))

    for child in [node for node in getattr(body, "children", []) if getattr(node, "name", None)]:
        if str(getattr(child, "name", "")).upper() in NON_CONTENT_BODY_CHILD_TAGS:
            continue
        if child.get_text(" ", strip=True):
            return True

    for node in body.find_all(True):
        if _is_within_correction_block(node):
            continue
        if str(getattr(node, "name", "")).upper() in NON_CONTENT_BODY_CHILD_TAGS:
            continue
        if node.get_text(" ", strip=True):
            return True
    return False


def _has_meaningful_document_content(soups: list) -> bool:
    return any(_has_meaningful_body_content(soup) for soup in soups or [])


def _parse_viewer_nodes(main_page_html: str) -> list[dict]:
    nodes = []
    seen = set()
    for match in VIEWER_NODE_PATTERN.finditer(main_page_html or ""):
        node = match.groupdict()
        key = (node["dcmNo"], node["eleId"], node["offset"], node["length"])
        if key in seen:
            continue
        seen.add(key)
        nodes.append(node)
    return nodes


def parse_family_rcept_numbers(main_page_html: str) -> list[str]:
    soup = BeautifulSoup(main_page_html or "", "html.parser")
    family_select = soup.find("select", id="family")
    if family_select is None:
        return []

    rcept_numbers = []
    seen = set()
    for option in family_select.find_all("option"):
        value = option.get("value") or ""
        match = re.search(r"(?:^|[?&])rcpNo=(\d{14})", value)
        if not match:
            continue
        rcept_no = match.group(1)
        if rcept_no in seen:
            continue
        seen.add(rcept_no)
        rcept_numbers.append(rcept_no)
    return rcept_numbers


_parse_family_rcept_numbers = parse_family_rcept_numbers


def find_previous_family_rcept_no(rcept_no: str, family_rcept_numbers: list[str]) -> str:
    current = (rcept_no or "").strip()
    ordered = sorted({value for value in family_rcept_numbers if re.fullmatch(r"\d{14}", value)})
    try:
        index = ordered.index(current)
    except ValueError:
        return ""
    if index == 0:
        return ""
    return ordered[index - 1]


def fetch_previous_family_rcept_no(rcept_no: str, timeout: int = 30) -> str:
    current = (rcept_no or "").strip()
    if not re.fullmatch(r"\d{14}", current):
        return ""
    response = requests.get(DART_MAIN_URL, params={"rcpNo": current}, timeout=timeout)
    response.raise_for_status()
    family_rcept_numbers = parse_family_rcept_numbers(_response_text(response))
    return find_previous_family_rcept_no(current, family_rcept_numbers)


def _fetch_viewer_soups(rcept_no: str, timeout: int = 30) -> list:
    main_response = requests.get(DART_MAIN_URL, params={"rcpNo": rcept_no}, timeout=timeout)
    main_response.raise_for_status()
    soups = []
    for node in _parse_viewer_nodes(_response_text(main_response)):
        if "정 정 신 고" in node.get("text", ""):
            continue
        viewer_response = requests.get(
            DART_VIEWER_URL,
            params={
                "rcpNo": node["rcpNo"],
                "dcmNo": node["dcmNo"],
                "eleId": node["eleId"],
                "offset": node["offset"],
                "length": node["length"],
                "dtd": node["dtd"],
            },
            timeout=timeout,
        )
        viewer_response.raise_for_status()
        soup = BeautifulSoup(_response_text(viewer_response), "html.parser")
        if soup.get_text(" ", strip=True):
            soups.append(soup)
    return soups
