"""Unit tests for ML token featurization."""

from __future__ import annotations

import math

from snapfolio.document import Document, Token
from snapfolio.ml.features import FEATURE_NAMES, featurize_token


def _tok(text: str = "100.50", **kwargs) -> Token:
    defaults = dict(x0=0.1, y0=0.2, x1=0.3, y1=0.25, confidence=0.88)
    defaults.update(kwargs)
    return Token(text=text, **defaults)


def test_featurize_token_keys_and_finite_values() -> None:
    doc = Document(
        tokens=[
            _tok("100.50", x0=0.1, y0=0.2, x1=0.3, y1=0.25),
            _tok("600519", x0=0.5, y0=0.2, x1=0.7, y1=0.25),
        ],
        image_width=1080,
        image_height=1920,
    )
    tok = doc.tokens[0]
    feats = featurize_token(tok, all_tokens=doc.tokens, document=doc)

    assert set(feats.keys()) == set(FEATURE_NAMES)
    for name in FEATURE_NAMES:
        val = feats[name]
        assert isinstance(val, float)
        assert math.isfinite(val)

    assert feats["has_decimal_point"] == 1.0
    assert feats["text_len"] == len("100.50")
    assert 0.0 <= feats["row_index_norm"] <= 1.0
    assert 0.0 <= feats["pos_in_row"] <= 1.0


def test_featurize_cjk_and_six_digit_flags() -> None:
    doc = Document(
        tokens=[_tok("贵州茅台600519", x0=0.1, y0=0.5, x1=0.6, y1=0.55)],
        image_width=1080,
        image_height=1920,
    )
    feats = featurize_token(doc.tokens[0], document=doc)

    assert feats["has_6digit"] == 1.0
    assert feats["cjk_ratio"] > 0.0
    assert feats["digit_ratio"] > 0.0
