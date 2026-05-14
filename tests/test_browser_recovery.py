from __future__ import annotations

import unittest

from cretop_data_reader.browser_recovery import (
    CRETOP_HOME_URL,
    is_cretop_expired_text,
    recover_cretop_expired_page,
)


class FakeLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    async def inner_text(self) -> str:
        return self.text


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.goto_calls: list[str] = []
        self.wait_calls: list[str] = []

    def locator(self, selector: str) -> FakeLocator:
        if selector != "body":
            raise AssertionError(f"unexpected selector: {selector}")
        return FakeLocator(self.text)

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)
        self.text = "로그인 후(online23)"

    async def wait_for_load_state(self, state: str) -> None:
        self.wait_calls.append(state)


class CretopRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_detects_expired_page_text(self) -> None:
        self.assertTrue(is_cretop_expired_text("페이지가 만료되었습니다.\nResult Code: -8002"))
        self.assertTrue(is_cretop_expired_text("웹브라우저는 새로고침(Ctrl+Shift+R)을 해주시고 앱의 경우 종료 후 재접속하시길 바랍니다.[8004]"))

    def test_ignores_normal_page_text(self) -> None:
        self.assertFalse(is_cretop_expired_text("오늘은 어떤 일을 시작해 볼까요?"))
        self.assertFalse(is_cretop_expired_text(""))

    async def test_recovers_expired_page(self) -> None:
        page = FakePage("페이지가 만료되었습니다.\nResult Code: -8002")

        recovered = await recover_cretop_expired_page(page)

        self.assertTrue(recovered)
        self.assertEqual(page.goto_calls, [CRETOP_HOME_URL])
        self.assertEqual(page.wait_calls, ["domcontentloaded"])

    async def test_does_not_reload_live_page(self) -> None:
        page = FakePage("로그인 후(online23)")

        recovered = await recover_cretop_expired_page(page)

        self.assertFalse(recovered)
        self.assertEqual(page.goto_calls, [])
        self.assertEqual(page.wait_calls, [])


if __name__ == "__main__":
    unittest.main()
