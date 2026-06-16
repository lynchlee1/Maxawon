from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScraplingStatus:
    installed: bool
    message: str


def check_scrapling() -> ScraplingStatus:
    try:
        import scrapling
    except ImportError:
        return ScraplingStatus(
            installed=False,
            message="Scrapling이 설치되어 있지 않습니다. `python -m pip install -e .`를 실행하세요.",
        )

    version = getattr(scrapling, "__version__", "unknown")
    return ScraplingStatus(installed=True, message=f"Scrapling 사용 가능: {version}")


def selector_from_html(html: str):
    from scrapling.parser import Selector

    return Selector(html)
