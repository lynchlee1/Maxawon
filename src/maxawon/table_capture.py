from __future__ import annotations

import asyncio
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maxawon.browser_recovery import is_maxawon_expired_page


CDP_URL = "http://127.0.0.1:9222"
MAXAWON_EXPIRED_MESSAGE = (
    "Maxawon 페이지가 만료되었습니다. Chrome에서 새로고침한 뒤 앱으로 돌아와 "
    "'로그인 완료'를 누르세요."
)


@dataclass(frozen=True)
class CapturedTable:
    headers: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class CaptureResult:
    headers: list[str]
    rows: list[list[str]]
    pages: int


SEARCH_RESULT_HEADERS = [
    "페이지",
    "순번",
    "회사명",
    "대표자명",
    "기업상태",
    "기업유형/형태",
    "사업자번호",
    "법인번호",
    "산업분류",
    "주소",
    "전화번호",
    "최근 재무년도",
    "원문",
]


def pick_largest_table(tables: list[dict[str, Any]]) -> CapturedTable | None:
    valid_tables = [
        table
        for table in tables
        if table.get("rows")
    ]
    if not valid_tables:
        return None

    table = max(valid_tables, key=lambda item: len(item.get("rows", [])))
    headers = [str(value or "").strip() for value in table.get("headers", [])]
    rows = [
        [str(value or "").strip() for value in row]
        for row in table.get("rows", [])
    ]

    if not headers and rows:
        headers = [f"Column {index + 1}" for index in range(max(len(row) for row in rows))]

    return CapturedTable(headers=headers, rows=rows)


def combine_tables(tables: list[CapturedTable]) -> CapturedTable:
    if not tables:
        return CapturedTable(headers=[], rows=[])

    headers = tables[0].headers
    rows: list[list[str]] = []
    width = len(headers)

    for table in tables:
        if len(table.headers) > width:
            width = len(table.headers)
            headers = table.headers
        for row in table.rows:
            rows.append(row)

    if width:
        rows = [row + [""] * (width - len(row)) for row in rows]
        rows = [row[:width] for row in rows]

    return CapturedTable(headers=headers, rows=rows)


def write_table_csv(path: Path, table: CapturedTable) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        if table.headers:
            writer.writerow(table.headers)
        writer.writerows(table.rows)


async def capture_current_maxawon_table(
    max_pages: int | None = None,
    cdp_url: str = CDP_URL,
) -> CaptureResult:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "화면 테이블 복사 기능을 사용하려면 Playwright가 필요합니다. "
            "`python3 -m pip install -e .`를 실행하세요."
        ) from exc

    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be at least 1")

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            raise RuntimeError(
                "Chrome에 연결하지 못했습니다. 앱의 'Chrome 열기' 버튼으로 연 창에서 "
                "Maxawon에 로그인한 뒤 다시 시도하세요."
            ) from exc
        try:
            page = await _find_maxawon_page(browser)
            captured: list[CapturedTable] = []
            seen_tables: set[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = set()

            if await _has_search_result_list(page):
                await _go_to_first_result_page(page)

            page_number = 1
            while max_pages is None or page_number <= max_pages:
                await page.wait_for_load_state("domcontentloaded")
                await _raise_if_expired(page)
                table = await _extract_search_result_table(page, page_number)
                if table is None:
                    table = pick_largest_table(await _extract_tables(page))
                if table is not None:
                    signature = table_signature(table)
                    if signature in seen_tables:
                        break
                    seen_tables.add(signature)
                    captured.append(table)

                if max_pages is not None and page_number == max_pages:
                    break
                if await _has_search_result_list(page):
                    clicked = await _click_result_page_number(page, page_number + 1)
                    if not clicked:
                        clicked = await _click_next_page(page)
                else:
                    clicked = await _click_next_page(page)
                if not clicked:
                    break
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(800)
                page_number += 1

            combined = combine_tables(captured)
            return CaptureResult(
                headers=combined.headers,
                rows=combined.rows,
                pages=len(captured),
            )
        finally:
            await browser.close()


def capture_current_maxawon_table_sync(max_pages: int | None = None, cdp_url: str = CDP_URL) -> CaptureResult:
    return asyncio.run(capture_current_maxawon_table(max_pages=max_pages, cdp_url=cdp_url))


def table_signature(table: CapturedTable) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    return (
        tuple(table.headers),
        tuple(tuple(row) for row in table.rows),
    )


async def _raise_if_expired(page: Any) -> None:
    if await is_maxawon_expired_page(page):
        raise RuntimeError(MAXAWON_EXPIRED_MESSAGE)


async def _find_maxawon_page(browser: Any) -> Any:
    pages = [
        page
        for context in browser.contexts
        for page in context.pages
    ]
    for page in reversed(pages):
        if "maxawon.com" in page.url:
            return page
    if pages:
        return pages[-1]
    raise RuntimeError("Chrome에서 열린 페이지를 찾지 못했습니다.")


async def _extract_tables(page: Any) -> list[dict[str, Any]]:
    return await page.evaluate(
        """
        () => Array.from(document.querySelectorAll('table')).map((table) => {
          const rows = Array.from(table.querySelectorAll('tr')).map((tr) =>
            Array.from(tr.querySelectorAll('th,td')).map((cell) => cell.innerText.trim())
          ).filter((row) => row.some((cell) => cell.length > 0));

          const firstRow = rows[0] || [];
          const hasHeaderCells = table.querySelector('tr th') !== null;
          const headers = hasHeaderCells ? firstRow : [];
          const bodyRows = hasHeaderCells ? rows.slice(1) : rows;
          return { headers, rows: bodyRows };
        })
        """
    )


async def _has_search_result_list(page: Any) -> bool:
    return await page.evaluate(
        """
        () => document.querySelectorAll('ul.search-result__list > li').length > 0
        """
    )


async def _extract_search_result_table(page: Any, page_number: int) -> CapturedTable | None:
    rows = await page.evaluate(
        """
        (pageNumber) => {
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const fieldValue = (item) => {
            const values = Array.from(item.querySelectorAll('.list-info'))
              .map((node) => clean(node.innerText || node.textContent))
              .filter(Boolean);
            return values.join('').replace(/\\s*·\\s*/g, '·');
          };

          return Array.from(document.querySelectorAll('ul.search-result__list > li')).map((item, index) => {
            const fields = {};
            item.querySelectorAll('ul.search-info-list > li').forEach((field) => {
              const title = clean(field.querySelector('.list-tit')?.innerText || field.querySelector('.list-tit')?.textContent);
              if (!title) return;
              fields[title] = fieldValue(field);
            });

            const companyName = clean(item.querySelector('button.result-layer-open > span')?.innerText ||
              item.querySelector('button.result-layer-open > span')?.textContent);

            return [
              String(pageNumber),
              String(index + 1),
              companyName,
              fields['대표자명'] || '',
              fields['기업상태'] || '',
              fields['기업유형/형태'] || '',
              fields['사업자번호'] || '',
              fields['법인번호'] || '',
              fields['산업분류'] || '',
              fields['주소'] || '',
              fields['전화번호'] || '',
              fields['최근 재무년도'] || '',
              clean(item.innerText || item.textContent),
            ];
          }).filter((row) => row[2]);
        }
        """,
        page_number,
    )
    if not rows:
        return None
    return CapturedTable(headers=SEARCH_RESULT_HEADERS, rows=rows)


async def _go_to_first_result_page(page: Any) -> None:
    current = await _current_result_page_number(page)
    if current == 1:
        return
    await _click_result_page_number(page, 1)


async def _current_result_page_number(page: Any) -> int | None:
    value = await page.evaluate(
        """
        () => {
          const active = document.querySelector('button.num.on');
          const text = (active?.innerText || active?.textContent || '').trim();
          const pageNumber = Number(text);
          return Number.isInteger(pageNumber) ? pageNumber : null;
        }
        """
    )
    return int(value) if value is not None else None


async def _click_result_page_number(page: Any, page_number: int) -> bool:
    before = await _current_result_page_number(page)
    previous_first = await _first_search_result_name(page)
    target = page.locator("button.num").filter(has_text=re.compile(f"^{page_number}$")).first
    if await target.count() == 0:
        return False
    await _click_like_user(page, target)
    await _raise_if_expired(page)
    await _wait_for_result_page(page, page_number, before, previous_first)
    return True


async def _click_like_user(page: Any, locator: Any) -> None:
    if hasattr(locator, "wait_for"):
        await locator.wait_for(state="visible", timeout=5000)
    elif hasattr(locator, "wait_for_element_state"):
        await locator.wait_for_element_state("visible", timeout=5000)
    await locator.scroll_into_view_if_needed()
    await page.wait_for_timeout(120)

    box = await locator.bounding_box()
    if box is None:
        await locator.click(delay=80, timeout=5000)
        return

    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    await page.mouse.move(x, y, steps=8)
    await page.wait_for_timeout(120)
    await page.mouse.down()
    await page.wait_for_timeout(80)
    await page.mouse.up()
    await page.wait_for_timeout(300)


async def _first_search_result_name(page: Any) -> str:
    return await page.evaluate(
        """
        () => (document.querySelector('ul.search-result__list > li button.result-layer-open span')?.innerText || '').trim()
        """
    )


async def _wait_for_result_page(
    page: Any,
    page_number: int,
    previous_page: int | None = None,
    previous_first: str | None = None,
) -> None:
    try:
        await page.wait_for_function(
            """
            ([pageNumber, previousPage, previousFirst]) => {
              const active = document.querySelector('button.num.on');
              const text = (active?.innerText || active?.textContent || '').trim();
              const current = Number(text);
              const first = (document.querySelector('ul.search-result__list > li button.result-layer-open span')?.innerText || '').trim();
              if (Number.isInteger(pageNumber) && current === pageNumber && first && first !== previousFirst) return true;
              return previousPage !== null && current !== previousPage && first && first !== previousFirst;
            }
            """,
            [page_number, previous_page, previous_first],
            timeout=5000,
        )
    except Exception:
        await _raise_if_expired(page)
        await page.wait_for_timeout(1000)
    try:
        await page.wait_for_selector("ul.search-result__list > li", state="attached", timeout=5000)
    except Exception:
        await _raise_if_expired(page)
        raise


async def _click_next_page(page: Any) -> bool:
    handle = await page.evaluate_handle(
        """
        () => {
          const labels = ['다음', 'Next', 'next', '>', '›', '»'];
          const candidates = Array.from(document.querySelectorAll('a,button,[role="button"]'));
          const visible = (element) => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
              rect.width > 0 && rect.height > 0;
          };
          const disabled = (element) =>
            element.disabled ||
            element.getAttribute('aria-disabled') === 'true' ||
            /disabled|off/i.test(element.className || '');

          for (const element of candidates) {
            if (!visible(element) || disabled(element)) continue;
            const text = (element.innerText || element.textContent || '').trim();
            const title = (element.getAttribute('title') || '').trim();
            const aria = (element.getAttribute('aria-label') || '').trim();
            const rel = (element.getAttribute('rel') || '').trim();
            const value = `${text} ${title} ${aria} ${rel}`.trim();
            if (labels.some((label) => value === label || value.includes(label)) || rel === 'next') {
              return element;
            }
          }
          return null;
        }
        """
    )
    element = handle.as_element()
    if element is None:
        await handle.dispose()
        return False
    try:
        await _click_like_user(page, element)
        await _raise_if_expired(page)
        return True
    finally:
        await handle.dispose()
