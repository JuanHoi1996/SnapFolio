"""Unit tests for global UI chrome stripping."""

from __future__ import annotations

from snapfolio.document import Document, Token, strip_chrome


def _tok(text: str, y0: float, y1: float | None = None) -> Token:
    y1 = y1 if y1 is not None else y0 + 0.02
    return Token(text=text, x0=0.1, y0=y0, x1=0.9, y1=y1, confidence=0.9)


def test_strip_chrome_removes_status_bar_and_footer_tabs() -> None:
    doc = Document(
        tokens=[
            _tok("6:13", 0.02),
            _tok("5G", 0.03),
            _tok("持有资产", 0.25),
            _tok("中欧医疗健康混合A", 0.30),
            _tok("讨论区", 0.94),
            _tok("定投", 0.95),
        ],
        image_width=1080,
        image_height=1920,
    )
    stripped = strip_chrome(doc)
    texts = {t.text for t in stripped.tokens}
    assert texts == {"持有资产", "中欧医疗健康混合A"}


def test_strip_chrome_preserves_chart_labels_in_body() -> None:
    doc = Document(
        tokens=[
            _tok("昨日 -62.69", 0.45),
            _tok("近1年涨跌幅", 0.75),
            _tok("009975中高风险QDII-股票", 0.28),
        ],
        image_width=1080,
        image_height=1920,
    )
    stripped = strip_chrome(doc)
    assert len(stripped.tokens) == 3
