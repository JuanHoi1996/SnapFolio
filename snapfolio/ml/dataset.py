"""Weakly-supervised token dataset construction from OCR fixtures."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pandas as pd

from snapfolio.classify import classify
from snapfolio.document import Document, Token, parse_fixture, strip_chrome
from snapfolio.extractors.base import extract_document
from snapfolio.ml.features import FEATURE_NAMES, featurize_token
from snapfolio.numbers import (
    extract_code,
    extract_inline_value,
    extract_name_code_from_merged,
    parse_decimal,
    parse_nav_with_date,
)

LABELS = ("name", "code", "quantity", "unit_price", "amount", "noise")

_NUMERIC_INLINE_LABELS = (
    "现价",
    "持仓数",
    "可用数",
    "持仓市值",
    "持有份额",
    "最新净值",
    "单位净值",
    "持有资产",
    "成本价",
    "市值",
)

_WS_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return _WS_RE.sub("", text.strip())


def _token_matches_numeric(token: Token, expected: Decimal) -> bool:
    parsed = parse_decimal(token.text)
    if parsed is not None and parsed == expected:
        return True
    nav = parse_nav_with_date(token.text)
    if nav is not None and nav == expected:
        return True
    for label in _NUMERIC_INLINE_LABELS:
        inline = extract_inline_value(token.text, label)
        if inline is not None and inline == expected:
            return True
    return False


def _token_matches_code(token: Token, code: str) -> bool:
    extracted = extract_code(token.text)
    if extracted == code:
        return True
    compact = _normalize_text(token.text)
    return code in compact


def _token_matches_name(token: Token, name: str) -> bool:
    norm_name = _normalize_text(name)
    norm_tok = _normalize_text(token.text)
    if not norm_name or not norm_tok:
        return False
    if norm_tok == norm_name:
        return True
    merged_name, _ = extract_name_code_from_merged(token.text)
    if merged_name and _normalize_text(merged_name) == norm_name:
        return True
    if norm_name in norm_tok or norm_tok in norm_name:
        return True
    return False


def _find_matching_tokens(tokens: list[Token], field: str, value) -> list[Token]:
    if value is None:
        return []
    if field in ("quantity", "unit_price", "amount"):
        expected = value if isinstance(value, Decimal) else Decimal(str(value))
        return [t for t in tokens if _token_matches_numeric(t, expected)]
    if field == "code":
        return [t for t in tokens if _token_matches_code(t, str(value))]
    if field == "name":
        return [t for t in tokens if _token_matches_name(t, str(value))]
    return []


def align_tokens_to_records(
    doc: Document,
    records: list,
) -> dict[int, str]:
    """
    Map token id() -> label for uniquely aligned tokens.
    Ambiguous or contested tokens are omitted.
    """
    tokens = doc.tokens
    token_labels: dict[int, list[str]] = {id(t): [] for t in tokens}

    field_names = ("name", "code", "quantity", "unit_price", "amount")
    for record in records:
        for field in field_names:
            if field in ("name", "code"):
                value = getattr(record, field, None)
                if not value:
                    continue
            else:
                obs = getattr(record, field, None)
                if obs is None or obs.value is None:
                    continue
                value = obs.value

            matches = _find_matching_tokens(tokens, field, value)
            if len(matches) != 1:
                continue
            token_labels[id(matches[0])].append(field)

    result: dict[int, str] = {}
    for tok in tokens:
        claims = token_labels[id(tok)]
        if len(claims) == 1:
            result[id(tok)] = claims[0]
        elif len(claims) == 0:
            result[id(tok)] = "noise"
    return result


def build_weak_dataset(fixture_paths: list[str | Path]) -> pd.DataFrame:
    rows: list[dict] = []

    for raw_path in fixture_paths:
        path = Path(raw_path)
        doc = parse_fixture(path)
        result = classify(doc)
        if result.rejected or result.platform is None:
            continue

        platform_id = result.platform.platform_id
        stripped = strip_chrome(doc)
        records = extract_document(
            stripped,
            result.platform,
            str(path),
            page_id=result.page_id,
        )
        if not records:
            continue

        labels = align_tokens_to_records(stripped, records)
        for tok in stripped.tokens:
            label = labels.get(id(tok))
            if label is None:
                continue

            feats = featurize_token(tok, all_tokens=stripped.tokens, document=stripped)
            row = {
                "fixture_id": path.stem,
                "platform": platform_id,
                "origin": "real",
                "token_text": tok.text,
                "label": label,
            }
            row.update(feats)
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["fixture_id", "platform", "origin", "token_text", "label", *FEATURE_NAMES])

    return pd.DataFrame(rows)


def save_dataset(df: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8")
    return out
