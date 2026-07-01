"""Cross-image partial-record reconciliation."""

from __future__ import annotations

import re
from decimal import Decimal

from snapfolio.models import FieldObservation, PartialRecord, PositionRecord

_WEAK_NAME_PATTERNS = (
    re.compile(r"^\d{1,2}:\d{2}"),
    re.compile(r"^\d+[a-z.]*$", re.I),
)


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    s = re.sub(r"\s+", "", name)
    s = re.sub(r"[^\w\u4e00-\u9fff]", "", s)
    s = s.lower()
    # QDI vs QDII OCR variants (e.g. 理财通 holding vs detail page)
    s = re.sub(r"qdil", "qdii", s)
    s = re.sub(r"qdi(?!i)", "qdii", s)
    return s


def _is_weak_name(name: str | None) -> bool:
    if not name:
        return True
    normalized = normalize_name(name)
    if len(normalized) < 4:
        return True
    if "管理人要求" in name or "限购" in name:
        return True
    return any(p.match(normalized) for p in _WEAK_NAME_PATTERNS)


def _names_compatible(a: str | None, b: str | None) -> bool:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(short) >= 4 and short in long


def _amount_compatible(a: PartialRecord, b: PartialRecord) -> bool:
    av = _obs_value(a.amount)
    bv = _obs_value(b.amount)
    if not isinstance(av, Decimal) or not isinstance(bv, Decimal):
        return False
    if av == 0:
        return bv == 0
    return abs(av - bv) / av <= Decimal("0.02")


def _is_code_only_partial(p: PartialRecord) -> bool:
    return bool(p.code) and p.quantity is None


def _is_detail_partial(p: PartialRecord) -> bool:
    return p.code is None and p.quantity is not None


def _should_link_partials(a: PartialRecord, b: PartialRecord) -> bool:
    if a.source != b.source:
        return False
    if a.code and b.code and a.code == b.code:
        return True
    if _names_compatible(a.name, b.name) and not (_is_weak_name(a.name) and _is_weak_name(b.name)):
        return True
    code_detail_pair = (_is_code_only_partial(a) and _is_detail_partial(b)) or (
        _is_code_only_partial(b) and _is_detail_partial(a)
    )
    if code_detail_pair:
        if _names_compatible(a.name, b.name):
            return True
        if _amount_compatible(a, b):
            return True
    return False


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _group_partials(partials: list[PartialRecord]) -> list[list[PartialRecord]]:
    if not partials:
        return []

    uf = _UnionFind(len(partials))
    for i in range(len(partials)):
        for j in range(i + 1, len(partials)):
            if _should_link_partials(partials[i], partials[j]):
                uf.union(i, j)

    grouped: dict[int, list[PartialRecord]] = {}
    for idx, partial in enumerate(partials):
        root = uf.find(idx)
        grouped.setdefault(root, []).append(partial)
    return list(grouped.values())


def _pick_obs(
    existing: FieldObservation | None,
    incoming: FieldObservation | None,
) -> FieldObservation | None:
    if incoming is None:
        return existing
    if existing is None:
        return incoming
    return incoming if incoming.confidence >= existing.confidence else existing


def _obs_value(obs: FieldObservation | None) -> Decimal | str | None:
    return obs.value if obs else None


def merge_partials(partials: list[PartialRecord]) -> list[PositionRecord]:
    """
    Merge PARTIAL records across images.
    Links records by shared code, compatible fund names, or holding/detail pairs
    (code on one image, holdings on another — typical for 理财通).
    """
    results: list[PositionRecord] = []

    by_source: dict[str, list[PartialRecord]] = {}
    for p in partials:
        by_source.setdefault(p.source, []).append(p)

    for source, source_partials in by_source.items():
        for group in _group_partials(source_partials):
            merged_name: str | None = None
            merged_code: str | None = None
            merged_qty: FieldObservation | None = None
            merged_price: FieldObservation | None = None
            merged_amount: FieldObservation | None = None
            asset_type = group[0].asset_type
            source_images: list[str] = []
            flags: list[str] = []
            confs: list[float] = []

            for p in sorted(group, key=lambda x: x.confidence, reverse=True):
                if p.name and (not merged_name or _is_weak_name(merged_name)):
                    merged_name = p.name
                elif (
                    p.name
                    and merged_name
                    and len(p.name) > len(merged_name)
                    and "管理人" not in p.name
                ):
                    merged_name = p.name
                if p.code and not merged_code:
                    merged_code = p.code
                merged_qty = _pick_obs(merged_qty, p.quantity)
                merged_price = _pick_obs(merged_price, p.unit_price)
                merged_amount = _pick_obs(merged_amount, p.amount)
                if p.source_image not in source_images:
                    source_images.append(p.source_image)
                confs.append(p.confidence)
                for f in p.flags:
                    if f not in flags:
                        flags.append(f)

            if not merged_name:
                continue

            qty_val = _obs_value(merged_qty)
            price_val = _obs_value(merged_price)
            amount_val = _obs_value(merged_amount)

            results.append(
                PositionRecord(
                    asset_type=asset_type,
                    source=source,
                    source_image="; ".join(source_images),
                    name=merged_name,
                    code=merged_code if isinstance(merged_code, str) else None,
                    quantity=qty_val if isinstance(qty_val, Decimal) else None,
                    unit_price=price_val if isinstance(price_val, Decimal) else None,
                    amount=amount_val if isinstance(amount_val, Decimal) else None,
                    confidence=sum(confs) / len(confs) if confs else 0.0,
                    flags=flags,
                )
            )

    return results
