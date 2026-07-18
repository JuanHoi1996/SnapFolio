"""Unit tests for OCR text normalization (QDII/QDI fixes)."""

from __future__ import annotations

from decimal import Decimal

from snapfolio.document import build_document
from snapfolio.models import FieldObservation, PartialRecord
from snapfolio.ocr_normalize import normalize_ocr_text
from snapfolio.reconcile import merge_partials


def test_qdi_paren_fullwidth() -> None:
    assert normalize_ocr_text("广发全球精选股票（QDI）人民币A") == "广发全球精选股票（QDII）人民币A"


def test_qdi_paren_halfwidth() -> None:
    assert normalize_ocr_text("广发全球精选股票(QDI)人民币A") == "广发全球精选股票(QDII)人民币A"


def test_qdi_half_close_paren() -> None:
    assert normalize_ocr_text("广发全球精选股票（QDI)人民币") == "广发全球精选股票（QDII)人民币"


def test_qdi_stock_suffix() -> None:
    assert normalize_ocr_text("270023中高风险QDI-股票") == "270023中高风险QDII-股票"


def test_qdi_metadata_line() -> None:
    assert normalize_ocr_text("008706中高风险1QDI-股票") == "008706中高风险1QDII-股票"


def test_qdii_unchanged() -> None:
    text = "009975中高风险QDII-股票"
    assert normalize_ocr_text(text) == text


def test_qdil_confusion() -> None:
    assert normalize_ocr_text("广发全球精选股票（QDIl）人民币A") == "广发全球精选股票（QDII）人民币A"
    assert normalize_ocr_text("270023中高风险QDIl-股票") == "270023中高风险QDII-股票"


def test_no_blind_replace_inside_unrelated() -> None:
    text = "QDIAN基金测试"
    assert normalize_ocr_text(text) == text


def test_build_document_applies_normalize() -> None:
    bbox = [[0, 0], [10, 0], [10, 10], [0, 10]]
    doc = build_document([(bbox, "270023中高风险QDI-股票", 0.9)], 100, 100)
    assert doc.tokens[0].text == "270023中高风险QDII-股票"


def _obs(value: Decimal) -> FieldObservation:
    return FieldObservation(value=value, confidence=0.9, strategy="test")


def test_licaitong_qdi_qdii_names_merge() -> None:
    holding = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="holding.png",
        name="广发全球精选股票（QDI)人民币",
        code="270023",
        page_id="holding",
    )
    detail = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="detail.png",
        name="广发全球精选股票（QDII）人民币A",
        quantity=_obs(Decimal("736.80")),
        unit_price=_obs(Decimal("5.1786")),
        amount=_obs(Decimal("3815.59")),
        page_id="detail",
    )

    records = merge_partials([holding, detail])

    assert len(records) == 1
    assert records[0].code == "270023"
    assert "广发全球精选股票" in records[0].name


def test_licaitong_qdil_qdii_names_merge() -> None:
    holding = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="holding.png",
        name="广发全球精选股票（QDIl)人民币",
        code="270023",
        page_id="holding",
    )
    detail = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="detail.png",
        name="广发全球精选股票（QDII）人民币A",
        quantity=_obs(Decimal("736.80")),
        unit_price=_obs(Decimal("5.1786")),
        amount=_obs(Decimal("3815.59")),
        page_id="detail",
    )

    records = merge_partials([holding, detail])

    assert len(records) == 1
    assert records[0].code == "270023"
    assert "广发全球精选股票" in records[0].name
