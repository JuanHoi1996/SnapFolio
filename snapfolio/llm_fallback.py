"""Gemini vision fallback when local platform classification fails."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

from snapfolio.llm_prompt import DEFAULT_GEMINI_MODEL, EXTRACTION_PROMPT
from snapfolio.models import FieldObservation, PartialRecord
from snapfolio.numbers import parse_decimal

logger = logging.getLogger(__name__)

_LLM_CONFIDENCE = 0.7
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    s = text.strip()
    s = _JSON_FENCE_RE.sub("", s).strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_gemini_json(raw: str) -> list[dict]:
    cleaned = _strip_json_fences(raw)
    data = json.loads(cleaned)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def _field_obs(value: Decimal | None) -> FieldObservation | None:
    if value is None:
        return None
    return FieldObservation(value=value, confidence=_LLM_CONFIDENCE, strategy="llm")


def _item_to_partial(item: dict, *, source_image: str) -> PartialRecord | None:
    name = item.get("name")
    if not name or not str(name).strip():
        return None

    asset_type = item.get("asset_type", "fund")
    if asset_type not in ("fund", "stock"):
        asset_type = "fund"

    code = item.get("code")
    if code is not None:
        code = str(code).strip() or None
        if code and not re.fullmatch(r"\d{6}", code):
            code = None

    return PartialRecord(
        asset_type=asset_type,
        source="gemini",
        source_image=source_image,
        name=str(name).strip(),
        code=code,
        quantity=_field_obs(parse_decimal(str(item["quantity"])) if item.get("quantity") is not None else None),
        unit_price=_field_obs(
            parse_decimal(str(item["unit_price"])) if item.get("unit_price") is not None else None
        ),
        amount=_field_obs(parse_decimal(str(item["amount"])) if item.get("amount") is not None else None),
        confidence=_LLM_CONFIDENCE,
        flags=["llm_extracted"],
    )


def extract_with_gemini(
    image_bytes: bytes,
    *,
    api_key: str,
    source_image: str = "",
    mime_type: str = "image/png",
) -> list[PartialRecord]:
    """
    Extract holdings from a screenshot via Gemini vision.
    Returns empty list on any failure (network, quota, parse).
    """
    if not api_key or not image_bytes:
        return []

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=EXTRACTION_PROMPT),
            ],
        )
        raw_text = response.text or ""
        items = _parse_gemini_json(raw_text)
    except Exception:
        logger.exception("Gemini extraction failed for %s", source_image)
        return []

    partials: list[PartialRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        partial = _item_to_partial(item, source_image=source_image)
        if partial is not None:
            partials.append(partial)
    return partials
