from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cretop_data_reader.network_logger import (
    daily_log_path,
    purge_old_logs,
    sanitize_headers,
)


class NetworkLoggerTests(unittest.TestCase):
    def test_sanitize_headers_removes_credentials(self) -> None:
        sanitized = sanitize_headers(
            {
                "Authorization": "Bearer token",
                "Cookie": "session=secret",
                "Set-Cookie": "session=secret",
                "Content-Type": "text/html",
            }
        )

        self.assertEqual({"Content-Type": "text/html"}, sanitized)

    def test_purge_old_logs_keeps_only_one_day(self) -> None:
        now = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            old_file = log_dir / "old.jsonl"
            recent_file = log_dir / "recent.jsonl"
            old_file.write_text("old", encoding="utf-8")
            recent_file.write_text("recent", encoding="utf-8")

            old_time = (now - timedelta(hours=25)).timestamp()
            recent_time = (now - timedelta(hours=1)).timestamp()
            os.utime(old_file, (old_time, old_time))
            os.utime(recent_file, (recent_time, recent_time))

            removed = purge_old_logs(log_dir, now)

            self.assertEqual(1, removed)
            self.assertFalse(old_file.exists())
            self.assertTrue(recent_file.exists())

    def test_daily_log_path_uses_utc_date(self) -> None:
        now = datetime(2026, 6, 15, 23, 0, tzinfo=timezone.utc)

        self.assertEqual(Path("logs") / "network-2026-06-15.jsonl", daily_log_path(Path("logs"), now))


if __name__ == "__main__":
    unittest.main()
