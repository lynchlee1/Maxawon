from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from maxawon.table_capture import (
    CapturedTable,
    combine_tables,
    pick_largest_table,
    table_signature,
    write_table_csv,
)


class TableCaptureTests(unittest.TestCase):
    def test_picks_largest_non_empty_table(self) -> None:
        table = pick_largest_table(
            [
                {"headers": ["A"], "rows": [["1"]]},
                {"headers": ["회사명", "대표자"], "rows": [["세종", "김"], ["한신", "이"]]},
            ]
        )

        self.assertIsNotNone(table)
        self.assertEqual(["회사명", "대표자"], table.headers)
        self.assertEqual([["세종", "김"], ["한신", "이"]], table.rows)

    def test_builds_default_headers_when_table_has_no_header_cells(self) -> None:
        table = pick_largest_table(
            [
                {"headers": [], "rows": [["세종", "서울"], ["한신", "부산"]]},
            ]
        )

        self.assertEqual(["Column 1", "Column 2"], table.headers)

    def test_combines_pages_and_pads_short_rows(self) -> None:
        table = combine_tables(
            [
                CapturedTable(["회사명", "대표자"], [["세종", "김"]]),
                CapturedTable(["회사명", "대표자", "지역"], [["한신", "이", "서울"], ["대림"]]),
            ]
        )

        self.assertEqual(["회사명", "대표자", "지역"], table.headers)
        self.assertEqual([["세종", "김", ""], ["한신", "이", "서울"], ["대림", "", ""]], table.rows)

    def test_writes_utf8_sig_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "capture.csv"

            write_table_csv(path, CapturedTable(["회사명"], [["세종텔레콤"]]))

            with path.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual([["회사명"], ["세종텔레콤"]], rows)

    def test_table_signature_distinguishes_page_content(self) -> None:
        first = CapturedTable(["회사명"], [["세종텔레콤"]])
        second = CapturedTable(["회사명"], [["한신공영"]])

        self.assertEqual(table_signature(first), table_signature(first))
        self.assertNotEqual(table_signature(first), table_signature(second))


if __name__ == "__main__":
    unittest.main()
