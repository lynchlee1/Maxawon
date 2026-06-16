import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PACKAGE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mezzanine_parser import extract_table_data  # noqa: E402
from weekly_mezz.html_bond_parser import parse_bond_issuance_html  # noqa: E402


def parse_report_document(report: dict, soups: list) -> dict:
    html_path = report.get("html_path") or report.get("source_file")
    if html_path:
        path = Path(html_path)
        return parse_bond_issuance_html(path.read_bytes(), file_path=path, report=report)

    tables = []
    for soup in soups or []:
        tables.extend(soup.find_all(["table", "TABLE"]))
    return extract_table_data(report, tables, soups=soups) if soups else {}

