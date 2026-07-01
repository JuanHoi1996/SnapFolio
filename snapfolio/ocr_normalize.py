"""Fix common OCR confusions in fund/stock labels."""

from __future__ import annotations

import re

# (QDI) / （QDI） / QDI) before share class or fund-type suffix
_QDI_PAREN = re.compile(r"([（(])QDI([)）])")
_QDI_DASH_STOCK = re.compile(r"QDI(?=-|－|股票)", re.IGNORECASE)
# Metadata lines: 008706中高风险1QDI-股票
_QDI_METADATA = re.compile(r"(\d)QDI(?=-)", re.IGNORECASE)
# QDII misread as QDI + lowercase L (common on 理财通 / fund labels)
_QDI_L_CONFUSION = re.compile(r"QDIl", re.IGNORECASE)


def normalize_ocr_text(text: str) -> str:
    """Fix common OCR confusions in fund/stock labels."""
    if not text:
        return text

    s = _QDI_PAREN.sub(r"\1QDII\2", text)
    s = _QDI_DASH_STOCK.sub("QDII", s)
    s = _QDI_METADATA.sub(r"\1QDII", s)
    s = _QDI_L_CONFUSION.sub("QDII", s)
    return s
