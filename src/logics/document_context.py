"""Shared document-context helpers.

Output columns:
- support utilities only; no direct output columns

Stability:
- medium: depends on DART XML structure and correction-block layout
"""

import re


CORRECTION_COMPARISON_TABLE_PATTERN = re.compile(r"정\s*정\s*전.*정\s*정\s*후|정정사유")
NON_CONTENT_BODY_CHILD_TAGS = {"LIBRARY", "CORRECTION", "COVER", "HEAD", "FOOTNOTE"}


def is_within_correction_block(element) -> bool:
    current = element
    while current is not None:
        name = getattr(current, "name", None)
        if isinstance(name, str) and name.lower() == "correction":
            return True
        current = getattr(current, "parent", None)
    return False


def is_correction_comparison_table(table_text: str) -> bool:
    return bool(CORRECTION_COMPARISON_TABLE_PATTERN.search(table_text or ""))


def _is_section_like_tag(name: str | None) -> bool:
    if not isinstance(name, str):
        return False
    normalized = name.upper()
    return normalized == "PART" or normalized.startswith("SECTION-")


def _get_body_content_roots(soup):
    if soup is None:
        return []

    body = soup.find(["BODY", "body"])
    if body is None:
        return [soup]

    direct_children = [child for child in getattr(body, "children", []) if getattr(child, "name", None)]
    content_children = [
        child
        for child in direct_children
        if str(getattr(child, "name", "")).upper() not in NON_CONTENT_BODY_CHILD_TAGS
    ]
    return content_children or [body]


def combine_document_text(soups):
    if not soups:
        return ""
    text_chunks = []
    for soup in soups:
        for root in _get_body_content_roots(soup):
            for string in root.find_all(string=True):
                text = string.strip()
                if not text or is_within_correction_block(string):
                    continue
                text_chunks.append(text)
    return " ".join(text_chunks)


def filter_out_correction_tables(tables):
    return [table for table in tables or [] if not is_within_correction_block(table)]


def collect_body_tables(soups):
    tables = []
    for soup in soups or []:
        for root in _get_body_content_roots(soup):
            if str(getattr(root, "name", "")).upper() == "TABLE":
                tables.append(root)
            tables.extend(root.find_all(["table", "TABLE"]))
    return filter_out_correction_tables(tables)


def find_main_security_table(tables):
    for table in tables:
        table_text = table.get_text()
        if is_correction_comparison_table(table_text):
            continue
        if "사채의 종류" in table_text and "권면" in table_text:
            return table
    return None
