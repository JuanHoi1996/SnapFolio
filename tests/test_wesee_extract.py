"""Regression tests for Tencent WeSee list extractor."""

from __future__ import annotations

from decimal import Decimal

from snapfolio.document import Document, Token
from snapfolio.extractors.base import ListExtractor, _STRATEGY_COLUMN, _STRATEGY_DERIVED
from snapfolio.extractors.configs import TENCENT_WESEE


def _tok(text: str, x0: float, y0: float, x1: float | None = None, y1: float | None = None) -> Token:
    return Token(
        text=text,
        x0=x0,
        y0=y0,
        x1=x1 if x1 is not None else x0 + 0.12,
        y1=y1 if y1 is not None else y0 + 0.02,
        confidence=0.95,
    )


def _wesee_base_headers() -> list[Token]:
    return [
        _tok("证券/代码", 0.05, 0.10),
        _tok("市值/股数", 0.40, 0.10),
        _tok("现价/成本", 0.65, 0.10),
        _tok("今日盈亏", 0.88, 0.10),
    ]


def test_wesee_rejects_signed_pnl_as_unit_price() -> None:
    """今日盈亏 value must not displace 现价 when they share the same y0."""
    tokens = _wesee_base_headers() + [
        _tok("中国船舶", 0.05, 0.20),
        _tok("600150", 0.05, 0.24),
        _tok("3,775.00", 0.38, 0.20),
        _tok("100", 0.38, 0.24),
        _tok("37.750", 0.62, 0.20),
        _tok("33.380", 0.62, 0.24),
        _tok("-10.00", 0.88, 0.20),  # PnL on same row as 现价
    ]
    doc = Document(tokens=tokens, image_width=1080, image_height=1920)
    records = ListExtractor().extract(doc, TENCENT_WESEE, "wesee.png", "holdings")
    assert len(records) == 1
    rec = records[0]
    assert rec.code == "600150"
    assert rec.unit_price is not None
    assert rec.unit_price.value == Decimal("37.750")
    assert rec.unit_price.strategy == _STRATEGY_COLUMN


def test_wesee_joins_wrapped_security_name() -> None:
    """Long names wrap onto a second line; both fragments must become one name."""
    tokens = _wesee_base_headers() + [
        _tok("半导体龙头ETF", 0.05, 0.74),
        _tok("工银", 0.05, 0.77),
        _tok("159665", 0.08, 0.81),
        _tok("1,261.50", 0.38, 0.74),
        _tok("500", 0.38, 0.81),
        _tok("2.523", 0.62, 0.74),
        _tok("2.400", 0.62, 0.81),
    ]
    doc = Document(tokens=tokens, image_width=1080, image_height=1920)
    records = ListExtractor().extract(doc, TENCENT_WESEE, "wesee.png", "holdings")
    assert len(records) == 1
    rec = records[0]
    assert rec.code == "159665"
    assert rec.name == "半导体龙头ETF工银"
    assert rec.quantity is not None and rec.quantity.value == Decimal("500")


def test_wesee_band_uses_selected_name_token_not_ocr_order() -> None:
    """Header '证券/代码(4)' must not become the band origin / quantity."""
    tokens = _wesee_base_headers() + [
        # OCR may emit header-like chrome before the real name.
        _tok("证券/代码(4)", 0.05, 0.185),
        _tok("三峡能源", 0.05, 0.20),
        _tok("600905", 0.05, 0.24),
        _tok("7,072.00", 0.38, 0.20),
        _tok("1700", 0.38, 0.24),
        _tok("4.160", 0.62, 0.20),
        _tok("5.823", 0.62, 0.24),
    ]
    doc = Document(tokens=tokens, image_width=1080, image_height=1920)
    records = ListExtractor().extract(doc, TENCENT_WESEE, "wesee.png", "holdings")
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "三峡能源"
    assert rec.quantity is not None
    assert rec.quantity.value == Decimal("1700")
    assert rec.quantity.value != Decimal("4")


def test_wesee_derives_large_quantity_and_marks_strategy() -> None:
    """When qty is dropped by the 100k gate, recover from amount / price as derived."""
    tokens = _wesee_base_headers() + [
        _tok("测试股份", 0.05, 0.20),
        _tok("600001", 0.05, 0.24),
        _tok("750,000.00", 0.38, 0.20),
        # Intentionally omit a readable quantity so derivation kicks in.
        _tok("5.000", 0.62, 0.20),
        _tok("4.800", 0.62, 0.24),
    ]
    doc = Document(tokens=tokens, image_width=1080, image_height=1920)
    records = ListExtractor().extract(doc, TENCENT_WESEE, "wesee.png", "holdings")
    assert len(records) == 1
    rec = records[0]
    assert rec.amount is not None and rec.amount.value == Decimal("750000.00")
    assert rec.unit_price is not None and rec.unit_price.value == Decimal("5.000")
    assert rec.quantity is not None
    assert rec.quantity.value == Decimal("150000")
    assert rec.quantity.strategy == _STRATEGY_DERIVED
    assert rec.amount.strategy == _STRATEGY_COLUMN
    assert rec.unit_price.strategy == _STRATEGY_COLUMN
