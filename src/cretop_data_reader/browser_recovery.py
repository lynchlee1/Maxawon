from __future__ import annotations

from collections.abc import Awaitable
from inspect import isawaitable
from typing import Any


CRETOP_HOME_URL = "https://www.cretop.com/"
CRETOP_EXPIRED_MARKERS = (
    "페이지가 만료되었습니다",
    "[8004]",
    "Result Code: -8002",
)


async def _resolve(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


def is_cretop_expired_text(text: str | None) -> bool:
    if not text:
        return False
    return any(marker in text for marker in CRETOP_EXPIRED_MARKERS)


async def read_page_text(page: Any) -> str:
    if hasattr(page, "inner_text"):
        return await _resolve(page.inner_text("body"))

    locator = page.locator("body")
    return await _resolve(locator.inner_text())


async def is_cretop_expired_page(page: Any) -> bool:
    return is_cretop_expired_text(await read_page_text(page))


async def recover_cretop_expired_page(
    page: Any,
    home_url: str = CRETOP_HOME_URL,
    wait_until: str = "domcontentloaded",
) -> bool:
    if not await is_cretop_expired_page(page):
        return False

    await _resolve(page.goto(home_url))

    wait_for_load_state = getattr(page, "wait_for_load_state", None)
    if wait_for_load_state is not None:
        await _resolve(wait_for_load_state(wait_until))

    return True


async def ensure_cretop_page_alive(page: Any) -> bool:
    return await recover_cretop_expired_page(page)
