"""Unit tests for Gemini fallback JSON parsing (no live API)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from snapfolio.llm_fallback import _parse_gemini_json, _strip_json_fences, extract_with_gemini
from snapfolio.models import PartialRecord

_SAMPLE_JSON = """[
  {
    "name": "景顺长城中证科技传媒通信150ETF联接A",
    "code": "001361",
    "quantity": null,
    "unit_price": null,
    "amount": 13912.93,
    "asset_type": "fund"
  }
]"""


def test_strip_json_fences() -> None:
    raw = '```json\n[{"name": "测试"}]\n```'
    assert _strip_json_fences(raw) == '[{"name": "测试"}]'


def test_parse_gemini_json_array() -> None:
    items = _parse_gemini_json('[{"name": "A", "code": "001361", "amount": 100.5}]')
    assert len(items) == 1
    assert items[0]["name"] == "A"


def test_parse_gemini_json_single_object() -> None:
    items = _parse_gemini_json('{"name": "B", "code": null}')
    assert len(items) == 1
    assert items[0]["name"] == "B"


def test_parse_gemini_json_with_fences() -> None:
    raw = '```json\n[{"name": "景顺长城", "code": "001361", "amount": 13912.93}]\n```'
    items = _parse_gemini_json(raw)
    assert items[0]["code"] == "001361"


def _mock_gemini_response(text: str) -> MagicMock:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = text
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


@patch("google.genai.Client")
def test_extract_with_gemini_maps_to_partial_record(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = _mock_gemini_response(_SAMPLE_JSON)

    partials = extract_with_gemini(
        b"fake-image",
        api_key="test-key",
        source_image="test.png",
    )

    assert len(partials) == 1
    rec = partials[0]
    assert isinstance(rec, PartialRecord)
    assert rec.source == "gemini"
    assert rec.name == "景顺长城中证科技传媒通信150ETF联接A"
    assert rec.code == "001361"
    assert rec.amount is not None
    assert rec.amount.value == Decimal("13912.93")
    assert rec.amount.strategy == "llm"
    assert rec.confidence == 0.7
    assert "llm_extracted" in rec.flags


@patch("google.genai.Client")
def test_extract_with_gemini_empty_on_bad_json(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = _mock_gemini_response("not json at all")
    partials = extract_with_gemini(b"x", api_key="k", source_image="a.png")
    assert partials == []


def test_extract_with_gemini_empty_without_key() -> None:
    assert extract_with_gemini(b"x", api_key="", source_image="a.png") == []
