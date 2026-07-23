"""Generic ListExtractor and DetailExtractor engines."""

from __future__ import annotations

import re
from collections import Counter
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
_STRATEGY_DERIVED = "derived"

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}")
_CODE_METADATA_RE = re.compile(r"^\d{6}")
_YESTERDAY_CHANGE_RE = re.compile(r"昨日")
_ALIPAY_LABEL_BLACKLIST = (
    "持有份额",
    "基金净值",
    "金额(元)",
    "金额（元）",
    "持有金额",
    "资产详情",
)


def _looks_like_pnl_or_ratio(text: str) -> bool:
    """True for signed P/L or percentage tokens that must not be market value."""
    s = text.strip()
    return bool(s) and (s.startswith(("+", "-", "＋", "－")) or "%" in s)


def _is_licaitong_ui_chrome(text: str) -> bool:
    """Chart labels, daily change lines, and section headers — not fund names."""
    if _YESTERDAY_CHANGE_RE.search(text):
        return True
    chrome = (
        "近1年涨跌幅",
        "近一年涨跌幅",
        "业绩表现",
        "持仓成本",
        "持仓收益",
        "持仓收益率",
        "日涨跌幅",
        "持有资产",
        "持有份额",
        "最新净值",
        "单位净值",
        "腾讯腾安",
        "持有中",
        "讨论区",
        "已加自选",
        "交易明细",
        "收益明细",
        "累计收益",
        "定投计划",
        "一本基金",
        "一同类平均",
        "沪深300",
        "涨跌幅",
        "版块",
        "同类平均",
        "民交易明细",
    )
    return any(k in text for k in chrome)


def _is_licaitong_name_blacklist(text: str) -> bool:
    """Licaitong-only fallback filter; not used for other platforms."""
    if _is_licaitong_ui_chrome(text):
        return True
    if any(k in text for k in ("管理人", "限额", "要求", "费率", "定投", "买入")):
        return True
    if any(k in text for k in ("详情", "提供", "腾安", "大促", "交易明细")):
        return True
    if "净值" in text and "混合" not in text and "基金" not in text:
        return True
    return False


def _title_cluster_key(text: str) -> str:
    """Normalize titles so OCR-truncated duplicates cluster together."""
    chars = re.findall(r"[\u4e00-\u9fffA-Za-z]", text)
    return "".join(chars[:8])


def _starts_with_fund_code(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return bool(_CODE_METADATA_RE.match(compact))


def _is_plausible_fund_name(text: str, token: Token) -> bool:
    if not text or len(text) < 3:
        return False
    if _TIME_RE.match(text.strip()):
        return False
    if re.match(r"^[\d\+\-\.,%]+$", text):
        return False
    if _starts_with_fund_code(text):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", text))


def _extract_licaitong_name(doc: Document) -> tuple[str | None, bool]:
    """
  理财通基金名抽取：
  - 资产详情页（持有资产）：名称在「由…基金管理…提供」正上方
  - 基金档案页：导航栏与正文各出现一次（允许 OCR 截断差异）
  """
    provider_lines = [
        t
        for t in doc.tokens
        if "提供" in t.text and ("基金" in t.text or "管理" in t.text) and t.y0 < 0.38
    ]
    if provider_lines:
        provider_y = min(t.y0 for t in provider_lines)
        above = [
            t
            for t in doc.tokens
            if provider_y - 0.14 < t.y0 < provider_y - 0.003
            and _is_plausible_fund_name(t.text, t)
            and not _starts_with_fund_code(t.text)
            and not _is_licaitong_name_blacklist(t.text)
        ]
        if above:
            return max(above, key=lambda t: (len(t.text), -t.y0)).text.strip(), False

    upper = [
        t
        for t in doc.tokens
        if 0.06 < t.y0 < 0.42
        and _is_plausible_fund_name(t.text, t)
        and not _starts_with_fund_code(t.text)
        and not _is_licaitong_name_blacklist(t.text)
    ]
    if not upper:
        return None, False

    exact_counts = Counter(t.text.strip() for t in upper)
    for text, count in sorted(exact_counts.items(), key=lambda x: (-x[1], -len(x[0]))):
        if count >= 2:
            return text, False

    cluster_counts = Counter(_title_cluster_key(t.text) for t in upper)
    for key, count in sorted(cluster_counts.items(), key=lambda x: (-x[1], -len(x[0]))):
        if count >= 2 and len(key) >= 4:
            variants = [t for t in upper if _title_cluster_key(t.text) == key]
            return max(variants, key=lambda t: len(t.text)).text.strip(), False

    fallback = [t for t in upper]
    if not fallback:
        return None, False
    return max(fallback, key=lambda t: (len(t.text), -t.y0)).text.strip(), True


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

    # Same-row "to the right" shortcut only when searching sideways.
    if direction in ("right", "either"):
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
                name, needs_review = self._extract_name(doc, config, spec, page_id)
                if name:
                    record.name = name
                if needs_review and "needs_review" not in record.flags:
                    record.flags.append("needs_review")
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

    def _extract_name(
        self, doc: Document, config: PlatformConfig, spec: FieldSpec, page_id: str | None = None
    ) -> tuple[str | None, bool]:
        if config.platform_id == "tencent_licaitong":
            return _extract_licaitong_name(doc)

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
                        return tok.text.strip(), False

        candidates = [
            t
            for t in doc.tokens
            if _is_plausible_fund_name(t.text, t)
            and not any(l in t.text for l in _ALIPAY_LABEL_BLACKLIST)
        ]
        if not candidates:
            return None, False
        # Prefer longer Chinese names in the upper content area (skip chart/footer).
        candidates = [t for t in candidates if t.y0 < 0.55]
        if not candidates:
            return None, False
        candidates.sort(key=lambda t: (-len(t.text), t.y0))
        return candidates[0].text.strip(), False

    def _extract_code(self, doc: Document) -> str | None:
        # Prefer upper-screen codes only. A full-document fallback would treat
        # date fragments (e.g. 20250213 -> 202502) as security codes and can
        # silently poison reconcile merges. Empty is better than fabricated.
        for tok in sorted(doc.tokens, key=lambda t: t.y0):
            if tok.y0 >= 0.4:
                break
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
                    direction=spec.direction,
                    max_distance=spec.max_distance,
                    scope_tokens=scope,
                )
                if obs and field_name == "amount":
                    val = obs.value
                    if isinstance(val, Decimal) and (val < Decimal("100") or val < 0):
                        obs = None
                    elif isinstance(val, Decimal):
                        # Reject if the matched number came from a signed / % token.
                        for t in scope:
                            if parse_decimal(t.text) == val and _looks_like_pnl_or_ratio(t.text):
                                obs = None
                                break
                if obs:
                    setattr(record, field_name, obs)

            if record.amount is None:
                for tok in sorted(scope, key=lambda t: (t.y0, t.x0)):
                    if _looks_like_pnl_or_ratio(tok.text):
                        continue
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

            # Long names wrap to 2+ lines; keep a taller window and join fragments.
            name_candidates = [
                t
                for t in doc.tokens
                if t.y0 < code_tok.y0
                and t.y0 >= code_tok.y0 - 0.10
                and t.x0 < 0.35
                and re.search(r"[\u4e00-\u9fff]", t.text)
                and not extract_code(t.text)
                and not any(
                    k in t.text for k in ("证券", "代码", "市值", "股数", "现价", "成本", "盈亏")
                )
            ]
            if not name_candidates:
                continue
            name_candidates.sort(key=lambda t: t.y0)
            name = "".join(t.text.strip() for t in name_candidates)
            name_top = name_candidates[0]

            y_end = code_tok.y1 + 0.055
            next_names = [
                t.y0
                for t in doc.tokens
                if t.y0 > code_tok.y1 + 0.02
                and t.x0 < 0.35
                and re.search(r"[\u4e00-\u9fff]", t.text)
                and not extract_code(t.text)
                and t.text.strip() not in {c.text.strip() for c in name_candidates}
            ]
            if next_names:
                y_end = min(y_end, min(next_names) - 0.005)

            band = tokens_in_y_band(doc.tokens, name_top.y0 - 0.005, y_end)

            amount: Decimal | None = None
            quantity: Decimal | None = None
            unit_price: Decimal | None = None
            qty_strategy = price_strategy = amount_strategy = _STRATEGY_COLUMN
            price_candidates: list[tuple[float, Decimal]] = []
            left_integers: list[Decimal] = []

            for tok in band:
                if any(k in tok.text for k in ("%", "SH", "SZ", "盈亏")):
                    continue
                if _looks_like_pnl_or_ratio(tok.text):
                    continue
                # Headers like 证券/代码(4) must not become quantity via digit stripping.
                if re.search(r"[\u4e00-\u9fff]", tok.text):
                    continue
                if re.fullmatch(r"0?\d{6}", re.sub(r"\s+", "", tok.text)):
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
                unit_price = min(price_candidates, key=lambda p: p[0])[1]

            if quantity and amount and unit_price is None and quantity > 0:
                unit_price = (amount / quantity).quantize(Decimal("0.001"))
                price_strategy = _STRATEGY_DERIVED
            if quantity and unit_price and amount is None:
                amount = quantity * unit_price
                amount_strategy = _STRATEGY_DERIVED
            if amount and unit_price and quantity is None and unit_price > 0:
                quantity = (amount / unit_price).quantize(Decimal("1"))
                qty_strategy = _STRATEGY_DERIVED

            record = PartialRecord(
                asset_type=config.asset_type,
                source=config.platform_id,
                source_image=source_image,
                name=name,
                code=code,
                page_id=page_id,
            )
            if amount is not None:
                record.amount = _obs(amount, 0.85, amount_strategy)
            if quantity is not None:
                record.quantity = _obs(quantity, 0.85, qty_strategy)
            if unit_price is not None:
                record.unit_price = _obs(unit_price, 0.85, price_strategy)

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
