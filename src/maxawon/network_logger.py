from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CDP_URL = "http://127.0.0.1:9222"
RETENTION_HOURS = 24
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-csrf-token",
    "x-xsrf-token",
}


def purge_old_logs(log_dir: Path, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=RETENTION_HOURS)
    removed = 0
    if not log_dir.exists():
        return removed

    for path in log_dir.rglob("*"):
        if not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            path.unlink()
            removed += 1

    for directory in sorted((item for item in log_dir.rglob("*") if item.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass

    return removed


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in SENSITIVE_HEADERS
    }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def daily_log_path(log_dir: Path, now: datetime | None = None) -> Path:
    current = now or datetime.now(timezone.utc)
    return log_dir / f"network-{current.strftime('%Y-%m-%d')}.jsonl"


def body_extension(content_type: str) -> str:
    lowered = content_type.lower()
    if "html" in lowered:
        return ".html"
    if "json" in lowered:
        return ".json"
    if "xml" in lowered:
        return ".xml"
    return ".txt"


def should_save_body(content_type: str, resource_type: str) -> bool:
    lowered = content_type.lower()
    if resource_type in {"image", "font", "stylesheet", "script"}:
        return False
    return (
        resource_type in {"document", "xhr", "fetch"}
        or "text/" in lowered
        or "json" in lowered
        or "xml" in lowered
    )


class NetworkLogger:
    def __init__(self, log_dir: Path, cdp_url: str = CDP_URL) -> None:
        self.log_dir = log_dir
        self.cdp_url = cdp_url
        self.requests: dict[str, dict[str, Any]] = {}
        self.log_file = daily_log_path(log_dir)
        self.body_dir = log_dir / "bodies"
        self.seen_pages: set[int] = set()

    def prepare(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        purge_old_logs(self.log_dir)
        self.body_dir.mkdir(parents=True, exist_ok=True)

    def write_event(self, event: dict[str, Any]) -> None:
        event.setdefault("timestamp", iso_now())
        self.log_file = daily_log_path(self.log_dir)
        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            file.write("\n")

    async def run(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "네트워크 로그 저장 기능을 사용하려면 Playwright가 필요합니다. "
                "`python3 -m pip install -e .`를 실행하세요."
            ) from exc

        self.prepare()
        async with async_playwright() as playwright:
            while True:
                browser = await self._connect_when_available(playwright)
                self.seen_pages.clear()
                disconnected = asyncio.get_running_loop().create_future()
                browser.on("disconnected", lambda: finish_future(disconnected))
                self.write_event({"type": "logger_connected", "cdpUrl": self.cdp_url})
                for context in browser.contexts:
                    self.attach_context(context)
                browser.on("context", self.attach_context)
                await disconnected
                self.write_event({"type": "logger_disconnected", "cdpUrl": self.cdp_url})

    async def _connect_when_available(self, playwright: Any) -> Any:
        attempt = 0
        while True:
            attempt += 1
            try:
                return await playwright.chromium.connect_over_cdp(self.cdp_url)
            except Exception as exc:
                if attempt == 1 or attempt % 30 == 0:
                    self.write_event(
                        {
                            "type": "logger_waiting_for_cdp",
                            "cdpUrl": self.cdp_url,
                            "message": str(exc),
                        }
                    )
                await asyncio.sleep(0.5)

    def attach_context(self, context: Any) -> None:
        context.on("page", self.attach_page)
        for page in context.pages:
            self.attach_page(page)

    def attach_page(self, page: Any) -> None:
        page_id = id(page)
        if page_id in self.seen_pages:
            return
        self.seen_pages.add(page_id)
        page.on("request", lambda request: self.on_request(page, request))
        page.on("response", lambda response: asyncio.create_task(self.on_response(page, response)))
        page.on("requestfailed", lambda request: self.on_request_failed(page, request))
        page.on("requestfinished", lambda request: self.on_request_finished(page, request))

    def on_request(self, page: Any, request: Any) -> None:
        request_id = request_hash(request)
        self.requests[request_id] = {
            "method": request.method,
            "url": request.url,
            "resourceType": request.resource_type,
            "pageUrl": page.url,
        }
        self.write_event(
            {
                "type": "request",
                "requestId": request_id,
                "method": request.method,
                "url": request.url,
                "resourceType": request.resource_type,
                "pageUrl": page.url,
                "headers": sanitize_headers(request.headers),
            }
        )

    async def on_response(self, page: Any, response: Any) -> None:
        request = response.request
        request_id = request_hash(request)
        headers = sanitize_headers(response.headers)
        event: dict[str, Any] = {
            "type": "response",
            "requestId": request_id,
            "url": response.url,
            "pageUrl": page.url,
            "status": response.status,
            "statusText": response.status_text,
            "headers": headers,
        }

        content_type = headers.get("content-type", "")
        if should_save_body(content_type, request.resource_type):
            body_path = await self.save_response_body(request_id, response, content_type)
            if body_path is not None:
                event["bodyPath"] = str(body_path)

        self.write_event(event)

    def on_request_failed(self, page: Any, request: Any) -> None:
        self.write_event(
            {
                "type": "request_failed",
                "requestId": request_hash(request),
                "method": request.method,
                "url": request.url,
                "resourceType": request.resource_type,
                "pageUrl": page.url,
                "failure": request.failure,
            }
        )

    def on_request_finished(self, page: Any, request: Any) -> None:
        self.write_event(
            {
                "type": "request_finished",
                "requestId": request_hash(request),
                "method": request.method,
                "url": request.url,
                "resourceType": request.resource_type,
                "pageUrl": page.url,
            }
        )

    async def save_response_body(self, request_id: str, response: Any, content_type: str) -> Path | None:
        try:
            body = await response.text()
        except Exception:
            return None

        self.body_dir.mkdir(parents=True, exist_ok=True)
        body_path = self.body_dir / f"{request_id}{body_extension(content_type)}"
        try:
            body_path.write_text(body, encoding="utf-8", errors="replace")
            return body_path
        except OSError as exc:
            self.write_event(
                {
                    "type": "body_save_failed",
                    "requestId": request_id,
                    "path": str(body_path),
                    "message": str(exc),
                }
            )
            return None


def request_hash(request: Any) -> str:
    seed = "|".join(
        [
            request.method,
            request.url,
            request.resource_type,
            str(request.timing.get("startTime", "")),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def finish_future(future: asyncio.Future[None]) -> None:
    if not future.done():
        future.set_result(None)


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--cdp-url", default=CDP_URL)
    args = parser.parse_args()

    logger = NetworkLogger(Path(args.log_dir), args.cdp_url)
    await logger.run()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
