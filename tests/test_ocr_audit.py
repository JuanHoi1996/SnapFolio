"""Unit tests for OCR audit formatting (no RapidOCR required)."""

from __future__ import annotations

from snapfolio.document import Document, Token
from snapfolio.ocr_audit import audit_document, format_audit_text, write_batch_summary


def test_audit_document_flags_and_sort() -> None:
    doc = Document(
        tokens=[
            Token("现价1.1690", 0.5, 0.4, 0.7, 0.42, 0.95),
            Token("证券ETF", 0.04, 0.2, 0.2, 0.22, 0.9),
            Token("512880", 0.24, 0.2, 0.36, 0.22, 0.92),
            Token("杂讯", 0.1, 0.05, 0.2, 0.07, 0.4),
        ],
        image_width=1000,
        image_height=2000,
        source_path="sample.jpg",
    )
    audit = audit_document(doc)
    assert audit.token_count == 4
    assert audit.tokens[0].text == "杂讯"
    assert "low_conf" in audit.tokens[0].flags
    glue = next(t for t in audit.tokens if t.text == "现价1.1690")
    assert "label_value_glue" in glue.flags
    code = next(t for t in audit.tokens if t.text == "512880")
    assert "has_6digit" in code.flags
    text = format_audit_text(audit)
    assert "sample.jpg" in text
    assert "512880" in text


def test_write_batch_summary(tmp_path) -> None:
    doc = Document(
        tokens=[Token("持仓市值", 0.0, 0.0, 0.2, 0.05, 0.9)],
        image_width=100,
        image_height=100,
        source_path="a.jpg",
    )
    audit = audit_document(doc)
    path = write_batch_summary([audit], tmp_path)
    body = path.read_text(encoding="utf-8")
    assert "OCR Token Audit Summary" in body
    assert "a.jpg" in body
