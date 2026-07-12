"""Token featurization shared by training and inference."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from snapfolio.document import Document, Token, cluster_rows

if TYPE_CHECKING:
    pass

FEATURE_NAMES: list[str] = [
    "x_center_norm",
    "y_center_norm",
    "width_norm",
    "height_norm",
    "text_len",
    "digit_ratio",
    "cjk_ratio",
    "has_6digit",
    "has_decimal_point",
    "has_comma",
    "has_percent",
    "ocr_confidence",
    "tokens_in_row",
    "row_index_norm",
    "pos_in_row",
]

_SIX_DIGIT = re.compile(r"(?<!\d)\d{6}(?!\d)")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _digit_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(c.isdigit() for c in text) / len(text)


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(_CJK.findall(text)) / len(text)


def _row_context(token: Token, all_tokens: list[Token]) -> tuple[int, int, int]:
    """Return (row_index, pos_in_row, tokens_in_row)."""
    rows = cluster_rows(all_tokens)
    for row_idx, row in enumerate(rows):
        for pos, tok in enumerate(row):
            if tok is token:
                return row_idx, pos, len(row)
    return 0, 0, 1


def featurize_token(
    token: Token,
    *,
    all_tokens: list[Token] | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    document: Document | None = None,
) -> dict[str, float]:
    """
    Extract numeric features for a single OCR token.
    Pass either (image_width, image_height) or document for normalization context.
    """
    if document is not None:
        image_width = document.image_width
        image_height = document.image_height
        if all_tokens is None:
            all_tokens = document.tokens

    if all_tokens is None:
        all_tokens = [token]

    row_idx, pos_in_row, tokens_in_row = _row_context(token, all_tokens)
    num_rows = max(len(cluster_rows(all_tokens)), 1)
    row_index_norm = row_idx / max(num_rows - 1, 1)
    pos_norm = pos_in_row / max(tokens_in_row - 1, 1)

    text = token.text
    return {
        "x_center_norm": token.cx,
        "y_center_norm": token.cy,
        "width_norm": token.width,
        "height_norm": token.height,
        "text_len": float(len(text)),
        "digit_ratio": _digit_ratio(text),
        "cjk_ratio": _cjk_ratio(text),
        "has_6digit": 1.0 if _SIX_DIGIT.search(text) else 0.0,
        "has_decimal_point": 1.0 if "." in text or "。" in text else 0.0,
        "has_comma": 1.0 if "," in text or "，" in text else 0.0,
        "has_percent": 1.0 if "%" in text else 0.0,
        "ocr_confidence": float(token.confidence),
        "tokens_in_row": float(tokens_in_row),
        "row_index_norm": row_index_norm,
        "pos_in_row": pos_norm,
    }


def feature_vector(token: Token, **kwargs) -> list[float]:
    """Return features in FEATURE_NAMES order."""
    feats = featurize_token(token, **kwargs)
    return [feats[name] for name in FEATURE_NAMES]
