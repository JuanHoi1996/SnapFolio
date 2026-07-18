"""理财通基金名抽取回归。"""

from __future__ import annotations

from snapfolio.document import Document, Token
from snapfolio.extractors.base import (
    _extract_licaitong_name,
    _is_licaitong_name_blacklist,
    _is_licaitong_ui_chrome,
    _is_plausible_fund_name,
)


def _tok(text: str, y_px: int, height: int = 2720) -> Token:
    y0 = y_px / height
    return Token(text=text, x0=0.1, y0=y0, x1=0.9, y1=y0 + 0.02, confidence=0.9)


def test_rejects_code_risk_metadata_as_name() -> None:
    tok = _tok("009975中高风险QDII-股票", 675)
    assert not _is_plausible_fund_name(tok.text, tok)
    assert not _is_plausible_fund_name("009975中", tok)


def test_rejects_ui_chrome_as_name() -> None:
    assert _is_licaitong_ui_chrome("昨日 -62.69")
    assert _is_licaitong_ui_chrome("近1年涨跌幅")
    assert _is_licaitong_name_blacklist("应管理人要求，本产品单日单个投资者限额5000.00")


def test_licaitong_name_from_duplicated_title() -> None:
    title = "华宝标普美国消费C(人民币)"
    doc = Document(
        tokens=[
            _tok(title, 325),
            _tok("应管理人要求，本产品单日单个投资者限额500.00", 328),
            _tok(title, 571),
            _tok("009975中高风险QDII-股票", 675),
            _tok("标普可选消费品精选版块.", 679),
        ],
        image_width=1260,
        image_height=2720,
    )
    name, _ = _extract_licaitong_name(doc)
    assert name == title


def test_licaitong_detail_name_above_provider_line() -> None:
    title = "广发全球精选股票（QDI）人民币A"
    doc = Document(
        tokens=[
            _tok("应管理人要求，本产品单日单个投资者限额5000.00", 325),
            _tok(title, 557),
            _tok("由广发基金管理有限公司提供", 639),
            _tok("持有资产（元）", 765),
            _tok("3.815.59", 853),
            _tok("昨日 -62.69", 992),
            _tok("近1年涨跌幅", 2027),
        ],
        image_width=1260,
        image_height=2720,
    )
    name, _ = _extract_licaitong_name(doc)
    assert name == title


def test_licaitong_holding_fuzzy_duplicate_title() -> None:
    doc = Document(
        tokens=[
            _tok("广发全球精选股票（QDII)人民..", 203),
            _tok("应管理人要求，本产品单日单个投资者限额5000.00", 328),
            _tok("广发全球精选股票（QDI)人民币", 568),
            _tok("持有中 >", 578),
            _tok("270023中高风险QDI-股票", 779),
            _tok("近1年涨跌幅", 1003),
            _tok("近1年涨跌幅", 1528),
        ],
        image_width=1260,
        image_height=2720,
    )
    name, _ = _extract_licaitong_name(doc)
    assert name is not None
    assert name.startswith("广发全球精选股票")
    assert "涨跌幅" not in name
    assert "昨日" not in name
