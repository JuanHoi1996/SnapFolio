"""Tests for Document.has_all / has_any_of and unique platform classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from snapfolio.classify import _match_signature, classify
from snapfolio.document import Document, Token
from snapfolio.extractors.configs import PLATFORM_CONFIGS
from snapfolio.pipeline import ingest_fixture

_ML_FIXTURES = Path(__file__).resolve().parents[1] / "output" / "ml_fixtures"


def _doc(*texts: str) -> Document:
    tokens = [
        Token(text=t, x0=0.1, y0=0.1 + i * 0.05, x1=0.5, y1=0.12 + i * 0.05, confidence=0.9)
        for i, t in enumerate(texts)
    ]
    return Document(tokens=tokens, image_width=1000, image_height=2000)


def test_has_all_and_has_any_of() -> None:
    doc = _doc("资产详情", "持有份额", "基金净值")
    assert doc.has_all("资产详情", "持有份额") is True
    assert doc.has_all("资产详情", "不存在") is False
    assert doc.has_any_of("不存在", "持有份额") is True
    assert doc.has_any_of("不存在", "也没有") is False
    # Empty needles: all([]) is True — CMB_STOCK relies on this with signature=().
    assert doc.has_all() is True
    # Deprecated alias keeps AND semantics.
    assert doc.has_any("资产详情", "持有份额") is True
    assert doc.has_any("资产详情", "不存在") is False


def test_partial_signature_miss_is_false() -> None:
    doc = _doc("资产详情", "持有份额")  # missing 基金净值
    assert _match_signature(doc, ("资产详情", "持有份额", "基金净值")) is False


def _count_page_matches(doc: Document) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for config in PLATFORM_CONFIGS:
        for page in config.pages:
            if _match_signature(doc, page.signature, page.signature_any_of):
                hits.append((config.platform_id, page.page_id))
    return hits


@pytest.mark.skipif(not _ML_FIXTURES.is_dir(), reason="ml_fixtures not present")
def test_each_fixture_matches_exactly_one_page_config() -> None:
    fixtures = sorted(_ML_FIXTURES.glob("*.fixture.txt"))
    assert fixtures, "expected at least one fixture"
    for path in fixtures:
        doc = ingest_fixture(path)
        hits = _count_page_matches(doc)
        # Closed-world classify short-circuits on first hit; uniqueness must still hold.
        assert len(hits) == 1, f"{path.name}: expected 1 page match, got {hits}"
        result = classify(doc)
        assert result.rejected is False
        assert result.platform is not None
        assert (result.platform.platform_id, result.page_id) == hits[0]
