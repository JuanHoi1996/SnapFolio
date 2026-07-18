"""Unit tests for anchor-first name extraction with licaitong blacklist fallback."""

from __future__ import annotations

from snapfolio.document import Document, Token
from snapfolio.extractors.base import (
    _extract_licaitong_name,
    _is_licaitong_name_blacklist,
    _is_licaitong_ui_chrome,
    _is_plausible_fund_name,
)
from snapfolio.extractors.configs import TENCENT_LICAITONG
from snapfolio.extractors.base import DetailExtractor


def _tok(text: str, y_px: int, height: int = 2720) -> Token:
    y0 = y_px / height
    return Token(text=text, x0=0.1, y0=y0, x1=0.9, y1=y0 + 0.02, confidence=0.9)


def test_licaitong_ui_chrome_not_in_generic_plausible_name() -> None:
    tok = _tok("近1年涨跌幅", 2027)
    assert _is_licaitong_ui_chrome(tok.text)
    assert _is_plausible_fund_name(tok.text, tok)


def test_licaitong_blacklist_fallback_sets_needs_review() -> None:
    doc = Document(
        tokens=[
            _tok("孤立的基金标题无重复", 400),
            _tok("应管理人要求，本产品单日单个投资者限额5000.00", 420),
        ],
        image_width=1260,
        image_height=2720,
    )
    name, needs_review = _extract_licaitong_name(doc)
    assert name == "孤立的基金标题无重复"
    assert needs_review is True

    records = DetailExtractor().extract(doc, TENCENT_LICAITONG, "test.png", page_id="holding")
    assert len(records) == 1
    assert records[0].name == "孤立的基金标题无重复"
    assert "needs_review" in records[0].flags


def test_licaitong_anchor_path_does_not_set_needs_review() -> None:
    title = "广发全球精选股票（QDI）人民币A"
    doc = Document(
        tokens=[
            _tok(title, 557),
            _tok("由广发基金管理有限公司提供", 639),
            _tok("持有资产（元）", 765),
        ],
        image_width=1260,
        image_height=2720,
    )
    name, needs_review = _extract_licaitong_name(doc)
    assert name == title
    assert needs_review is False
    assert not _is_licaitong_name_blacklist(title)
