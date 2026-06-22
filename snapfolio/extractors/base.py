"""Generic ListExtractor and DetailExtractor engines."""

from __future__ import annotations

import re
from decimal import Decimal

from snapfolio.document import (
    Document,
    Token,
    assign_token_to_column,
    cluster_rows,
    detect_column_anchors,
    numeric_token_right_of,
    same_row,
    tokens_in_y_band,
    value_near_label,
)
from snapfolio.extractors.configs import FieldSpec, PlatformConfig
from snapfolio.models import FieldObservation, PartialRecord
from snapfolio.numbers import (
    extract_code,
    extract_inline_value,
    extract_name_code_from_merged,
    parse_decimal,
    parse_nav_with_date,
)

_STRATEGY_INLINE = "inline"
_STRATEGY_SPATIAL = "spatial"
_STRATEGY_REGEX = "regex"
_STRATEGY_COLUMN = "column"

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}")
_STATUS_BAR_RE = re.compile(r"^(G\.?l|4G|5G|N@?|38大促|腾讯腾安)$", re.I)


def _is_plausible_fund_name(text: str, token: Token) -> bool:
    if not text or len(text) < 3:
        return False
    if _TIME_RE.match(text.strip()):
        return False
    if _STATUS_BAR_RE.match(text.strip()):
        return False
    if re.match(r"^[\d\+\-\.,%]+$", text):
        return False
    if token.y0 < 0.08:
        return False
    if any(k in text for k in ("详情", "提供", "腾安", "大促", "交易明细")):
        return False
    if any(k in text for k in ("管理人", "限额", "要求", "费率", "定投", "买入")):
        return False
    if "净值" in text and "混合" not in text and "基金" not in text:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", text))


def _page_text(tokens: list[Token]) -> str:
    return "\n".join(t.text for t in sorted(tokens, key=lambda t: (t.y0, t.x0)))


def _obs(
    value: Decimal | str,
    confidence: float,
    strategy: str,
    token: Token | None = None,
) -> FieldObservation:
    conf = confidence
    if token is not None:
        conf = min(confidence, token.confidence)
    return FieldObservation(value=value, confidence=conf, strategy=strategy)


def resolve_field(
    doc: Document,
    spec_labels: tuple[str, ...],
    *,
    fallback_labels: tuple[str, ...] = (),
    inline_first: bool = True,
    direction: str = "right",
    max_distance: float = 0.4,
    parse_nav_date: bool = False,
    scope_tokens: list[Token] | None = None,
) -> FieldObservation | None:
    """
    Multi-strategy field resolution: inline -> spatial -> page regex -> None.
    """
    labels = spec_labels + fallback_labels
    tokens = scope_tokens if scope_tokens is not None else doc.tokens

    if inline_first:
        for label in labels:
            for tok in tokens:
                if label in tok.text and tok.text != label:
                    val = extract_inline_value(tok.text, label)
                    if val is not None:
                        return _obs(val, 0.9, _STRATEGY_INLINE, tok)
                    if parse_nav_date:
                        nav = parse_nav_with_date(tok.text[len(label) :])
                        if nav is not None:
                            return _obs(nav, 0.85, _STRATEGY_INLINE, tok)

    for label in labels:
        for tok in tokens:
            if tok.text.strip() == label or tok.text.startswith(label):
                neighbor = numeric_token_right_of(tok, tokens, max_dx=max_distance)
                if neighbor:
                    text = neighbor.text
                    parsed = parse_nav_with_date(text) if parse_nav_date else parse_decimal(text)
                    if parsed is not None:
                        return _obs(parsed, 0.8, _STRATEGY_SPATIAL, neighbor)

    spatial_direction = "either" if direction == "either" else direction
    for label in labels:
        spatial_doc = Document(tokens, doc.image_width, doc.image_height, doc.source_path)
        val_tok = value_near_label(
            spatial_doc, label, direction=spatial_direction, max_distance=max_distance
        )
        if val_tok and val_tok.text.strip() != label:
            text = val_tok.text
            if parse_nav_date:
                parsed = parse_nav_with_date(text)
            else:
                parsed = parse_decimal(text)
            if parsed is not None:
                return _obs(parsed, 0.75, _STRATEGY_SPATIAL, val_tok)

    for label in labels:
        pattern = re.compile(rf"{re.escape(label)}\s*[:：]?\s*([\+\-]?[\d,，\.。]+(?:\.\d+)?)")
        for tok in tokens:
            m = pattern.search(tok.text)
            if m:
                parsed = parse_decimal(m.group(1))
                if parsed is not None:
                    return _obs(parsed, 0.6, _STRATEGY_REGEX, tok)

    page = _page_text(tokens)
    for label in labels:
        cross_line = re.compile(
            rf"{re.escape(label)}[^\d]{{0,40}}?([\+\-]?[\d,，\.。]+(?:\.\d+)?)"
        )
        m = cross_line.search(page.replace("\n", " "))
        if m:
            parsed = parse_nav_with_date(m.group(1)) if parse_nav_date else parse_decimal(m.group(1))
            if parsed is not None:
                return _obs(parsed, 0.55, _STRATEGY_REGEX)

    return None


class DetailExtractor:
    """Extract fields from DETAIL archetype (key-value card layout)."""

    def extract(
        self,
        doc: Document,
        config: PlatformConfig,
        source_image: str,
        page_id: str | None = None,
    ) -> list[PartialRecord]:
        record = PartialRecord(
            asset_type=config.asset_type,
            source=config.platform_id,
            source_image=source_image,
            page_id=page_id,
        )

        for field_name, spec in config.fields.items():
            if spec.is_name:
                name = self._extract_name(doc, config, spec, page_id)
                if name:
                    record.name = name
                continue
            if spec.is_code:
                code = self._extract_code(doc)
                if code:
                    record.code = code
                continue

            obs = resolve_field(
                doc,
                spec.labels,
                fallback_labels=spec.fallback_labels,
                inline_first=spec.inline_first,
                direction=spec.direction,
                max_distance=spec.max_distance,
                parse_nav_date=spec.parse_nav_date,
            )
            if obs:
                setattr(record, field_name, obs)

        record.confidence = self._aggregate_confidence(record)
        return [record]

    def _extract_name(self, doc: Document, config: PlatformConfig, spec: FieldSpec, page_id: str | None = None) -> str | None:
        if page_id == "holding" and config.platform_id == "tencent_licaitong":
            title_candidates = [
                t
                for t in doc.tokens
                if 0.12 < t.y0 < 0.35
                and _is_plausible_fund_name(t.text, t)
                and ("混合" in t.text or "基金" in t.text or "股票" in t.text or "QDII" in t.text.upper())
            ]
            if title_candidates:
                title_candidates.sort(key=lambda t: (-len(t.text), t.y0))
                return title_candidates[0].text.strip()

            for tok in doc.tokens:
                code = extract_code(tok.text)
                if not code or tok.y0 > 0.35:
                    continue
                name = re.sub(r"\d{6}.*", "", tok.text).strip(" 【(（")
                if _is_plausible_fund_name(name, tok):
                    return name

        if spec.labels:
            anchor = doc.find_tokens_containing(spec.labels[0])
            if anchor:
                below = [
                    t
                    for t in doc.tokens
                    if t.y0 > min(a.y1 for a in anchor)
                    and t.y0 - min(a.y1 for a in anchor) < spec.max_distance
                ]
                below.sort(key=lambda t: t.y0)
                for tok in below:
                    if _is_plausible_fund_name(tok.text, tok):
                        return tok.text.strip()

        candidates = [
            t
            for t in doc.tokens
            if _is_plausible_fund_name(t.text, t)
            and not any(l in t.text for l in ("持有资产", "持有份额", "最新净值", "基金净值"))
        ]
        if not candidates:
            return None
        # Prefer longer Chinese names in the upper content area (skip chart/footer).
        candidates = [t for t in candidates if t.y0 < 0.55]
        if not candidates:
            return None
        candidates.sort(key=lambda t: (-len(t.text), t.y0))
        return candidates[0].text.strip()

    def _extract_code(self, doc: Document) -> str | None:
        upper_tokens = [t for t in doc.tokens if t.y0 < 0.4]
        for tok in upper_tokens:
            code = extract_code(tok.text)
            if code:
                return code
        for tok in doc.tokens:
            code = extract_code(tok.text)
            if code:
                return code
        return None

    def _aggregate_confidence(self, record: PartialRecord) -> float:
        obs_list = [record.quantity, record.unit_price, record.amount]
        confs = [o.confidence for o in obs_list if o is not None]
        if record.name:
            confs.append(0.8)
        if record.code:
            confs.append(0.8)
        return sum(confs) / len(confs) if confs else 0.0


class ListExtractor:
    """Extract holdings from LIST archetype (repeating rows)."""

    def extract(
        self,
        doc: Document,
        config: PlatformConfig,
        source_image: str,
        page_id: str | None = None,
    ) -> list[PartialRecord]:
        if config.card_delimiter:
            return self._extract_cards(doc, config, source_image, page_id)
        if config.platform_id == "cmb_stock":
            return self._extract_cmb(doc, config, source_image, page_id)
        if config.platform_id == "tencent_wesee":
            return self._extract_tencent_wesee(doc, config, source_image, page_id)
        return self._extract_generic_list(doc, config, source_image, page_id)

    def _extract_cmb(
        self,
        doc: Document,
        config: PlatformConfig,
        source_image: str,
        page_id: str | None,
    ) -> list[PartialRecord]:
        records: list[PartialRecord] = []
        rows = cluster_rows(doc.tokens, doc.median_token_height() * 0.55)

        holding_rows: list[list[Token]] = []
        for row in rows:
            row_text = " ".join(t.text for t in row)
            if re.search(r"\d{6}", row_text) and not any(
                lbl in row_text for lbl in ("持仓市值", "持仓数", "现价", "成本", "可用")
            ):
                holding_rows.append(row)

        for idx, row in enumerate(holding_rows):
            record = PartialRecord(
                asset_type=config.asset_type,
                source=config.platform_id,
                source_image=source_image,
                page_id=page_id,
            )
            row_sorted = sorted(row, key=lambda t: t.x0)
            name_tok = row_sorted[0]
            record.name = name_tok.text.strip()

            for tok in row:
                code = extract_code(tok.text)
                if code:
                    record.code = code
                    break

            y0 = min(t.y0 for t in row) - 0.005
            if idx + 1 < len(holding_rows):
                y1 = min(t.y0 for t in holding_rows[idx + 1]) - 0.005
            else:
                y1 = y0 + 0.18
            scope = tokens_in_y_band(doc.tokens, y0, y1)

            for field_name in ("amount", "quantity", "unit_price"):
                spec = config.fields[field_name]
                obs = resolve_field(
                    doc,
                    spec.labels,
                    fallback_labels=spec.fallback_labels,
                    inline_first=spec.inline_first,
                    scope_tokens=scope,
                )
                if obs and field_name == "amount":
                    val = obs.value
                    if isinstance(val, Decimal) and (val < Decimal("100") or val < 0):
                        obs = None
                if obs:
                    setattr(record, field_name, obs)

            if record.amount is None:
                for tok in scope:
                    val = parse_decimal(tok.text)
                    if val is None or val < Decimal("1000"):
                        continue
                    if record.code and str(int(val)).zfill(6) == record.code:
                        continue
                    if re.fullmatch(r"0?\d{6}", tok.text.replace(" ", "")):
                        continue
                    record.amount = _obs(val, 0.7, _STRATEGY_COLUMN, tok)
                    break

            record.confidence = DetailExtractor()._aggregate_confidence(record)
            if record.name:
                records.append(record)

        return records

    def _extract_tencent_wesee(
        self,
        doc: Document,
        config: PlatformConfig,
        source_image: str,
        page_id: str | None,
    ) -> list[PartialRecord]:
        records: list[PartialRecord] = []
        market_headers = doc.find_tokens_containing("市值/股数")
        price_headers = doc.find_tokens_containing("现价/成本")
        if not market_headers or not price_headers:
            return records

        market_x = market_headers[0].cx
        price_x = price_headers[0].cx
        split_x = (market_x + price_x) / 2
        header_y = max(t.y1 for t in market_headers + price_headers)

        code_tokens = [
            t
            for t in doc.tokens
            if t.y0 > header_y
            and t.x0 < 0.28
            and extract_code(t.text)
            and re.search(r"\d{6}", t.text.replace(" ", ""))
        ]
        code_tokens.sort(key=lambda t: t.y0)

        for idx, code_tok in enumerate(code_tokens):
            code = extract_code(code_tok.text)
            if not code:
                continue

            name_candidates = [
                t
                for t in doc.tokens
                if t.y0 < code_tok.y0
                and t.y0 >= code_tok.y0 - 0.06
                and t.x0 < 0.35
                and re.search(r"[\u4e00-\u9fff]", t.text)
                and not extract_code(t.text)
            ]
            if not name_candidates:
                continue
            name = max(name_candidates, key=lambda t: t.y1).text.strip()

            y_end = code_tok.y1 + 0.055
            next_names = [
                t.y0
                for t in doc.tokens
                if t.y0 > code_tok.y1 + 0.02
                and t.x0 < 0.35
                and re.search(r"[\u4e00-\u9fff]", t.text)
                and not extract_code(t.text)
                and t.text.strip() != name
            ]
            if next_names:
                y_end = min(y_end, min(next_names) - 0.005)

            band = tokens_in_y_band(doc.tokens, name_candidates[0].y0 - 0.005, y_end)

            amount: Decimal | None = None
            quantity: Decimal | None = None
            unit_price: Decimal | None = None
            price_candidates: list[tuple[float, Decimal]] = []
            left_integers: list[Decimal] = []

            for tok in band:
                if any(k in tok.text for k in ("%", "SH", "SZ", "盈亏")):
                    continue
                if re.fullmatch(r"0?\d{6}", tok.text.replace(" ", "")):
                    continue
                val = parse_decimal(tok.text)
                if val is None:
                    continue
                if val == 0:
                    continue
                if code and str(int(val)).zfill(6) == code:
                    continue

                if tok.cx < split_x:
                    if val == val.to_integral_value() and val < Decimal("500000"):
                        left_integers.append(val)
                    elif "," in tok.text or val >= Decimal("1000"):
                        if amount is None or val > amount:
                            amount = val
                elif val < Decimal("1000") and "." in tok.text:
                    price_candidates.append((tok.y0, val))

            if left_integers:
                left_integers = sorted(set(left_integers))
                if len(left_integers) >= 2:
                    quantity = left_integers[0]
                    if amount is None:
                        amount = left_integers[-1]
                elif len(left_integers) == 1 and left_integers[0] < Decimal("100000"):
                    quantity = left_integers[0]

            if price_candidates:
                price_candidates.sort(key=lambda x: x[0])
                unit_price = price_candidates[0][1]

            if quantity and amount and unit_price is None and quantity > 0:
                unit_price = amount / quantity
            if quantity and unit_price and amount is None:
                amount = quantity * unit_price

            record = PartialRecord(
                asset_type=config.asset_type,
                source=config.platform_id,
                source_image=source_image,
                name=name,
                code=code,
                page_id=page_id,
            )
            if amount is not None:
                record.amount = _obs(amount, 0.85, _STRATEGY_COLUMN)
            if quantity is not None:
                record.quantity = _obs(quantity, 0.85, _STRATEGY_COLUMN)
            if unit_price is not None:
                record.unit_price = _obs(unit_price, 0.85, _STRATEGY_COLUMN)

            record.confidence = DetailExtractor()._aggregate_confidence(record)
            records.append(record)

        return records

    def _extract_cards(
        self,
        doc: Document,
        config: PlatformConfig,
        source_image: str,
        page_id: str | None,
    ) -> list[PartialRecord]:
        records: list[PartialRecord] = []
        entry_tokens = [
            t
            for t in doc.tokens
            if t.text.rstrip().endswith(">") or t.text.rstrip().endswith("》")
        ]

        for idx, entry in enumerate(entry_tokens):
            name, code = extract_name_code_from_merged(entry.text)
            y0 = entry.y0
            y1 = (
                entry_tokens[idx + 1].y0
                if idx + 1 < len(entry_tokens)
                else min(entry.y1 + doc.median_token_height() * 8, 1.0)
            )
            scope = tokens_in_y_band(doc.tokens, y0, y1)

            record = PartialRecord(
                asset_type=config.asset_type,
                source=config.platform_id,
                source_image=source_image,
                name=name,
                code=code,
                page_id=page_id,
            )

            for field_name in ("amount", "quantity", "unit_price"):
                spec = config.fields[field_name]
                obs = resolve_field(
                    doc,
                    spec.labels,
                    fallback_labels=spec.fallback_labels,
                    inline_first=spec.inline_first,
                    scope_tokens=scope,
                )
                if obs:
                    setattr(record, field_name, obs)

            record.confidence = DetailExtractor()._aggregate_confidence(record)
            if record.name:
                records.append(record)

        return records

    def _extract_generic_list(
        self,
        doc: Document,
        config: PlatformConfig,
        source_image: str,
        page_id: str | None,
    ) -> list[PartialRecord]:
        records: list[PartialRecord] = []
        header_y = 0.0
        if config.list_headers:
            headers = doc.find_tokens_containing(config.list_headers[0])
            if headers:
                header_y = max(t.y1 for t in headers)

        body = [t for t in doc.tokens if t.y0 > header_y]
        rows = cluster_rows(body, doc.median_token_height() * 0.55)

        for row in rows:
            record = PartialRecord(
                asset_type=config.asset_type,
                source=config.platform_id,
                source_image=source_image,
                page_id=page_id,
            )
            for tok in row:
                if not record.name:
                    record.name = tok.text
                code = extract_code(tok.text)
                if code:
                    record.code = code

            for field_name, spec in config.fields.items():
                if spec.is_name or spec.is_code:
                    continue
                obs = resolve_field(
                    doc,
                    spec.labels,
                    fallback_labels=spec.fallback_labels,
                    inline_first=spec.inline_first,
                    scope_tokens=row,
                )
                if obs:
                    setattr(record, field_name, obs)

            record.confidence = DetailExtractor()._aggregate_confidence(record)
            if record.name:
                records.append(record)

        return records


def extract_document(
    doc: Document,
    config: PlatformConfig,
    source_image: str,
    page_id: str | None = None,
) -> list[PartialRecord]:
    if config.archetype == "list":
        return ListExtractor().extract(doc, config, source_image, page_id)
    return DetailExtractor().extract(doc, config, source_image, page_id)
