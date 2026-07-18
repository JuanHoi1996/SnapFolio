"""Unit tests for cross-image partial reconciliation."""

from __future__ import annotations

from decimal import Decimal

from snapfolio.models import FieldObservation, PartialRecord
from snapfolio.reconcile import merge_partials


def _obs(value: Decimal) -> FieldObservation:
    return FieldObservation(value=value, confidence=0.9, strategy="test")


def test_licaitong_merges_code_holding_with_detail_by_amount() -> None:
    holding = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="holding.png",
        name="6:13",
        code="003095",
        amount=_obs(Decimal("42968.76")),
        page_id="holding",
    )
    detail = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="detail.png",
        name="中欧医疗健康混合A",
        quantity=_obs(Decimal("24511.56")),
        unit_price=_obs(Decimal("1.7530")),
        amount=_obs(Decimal("42968.76")),
        page_id="detail",
    )

    records = merge_partials([holding, detail])

    assert len(records) == 1
    rec = records[0]
    assert rec.code == "003095"
    assert rec.name == "中欧医疗健康混合A"
    assert rec.quantity == Decimal("24511.56")
    assert rec.unit_price == Decimal("1.7530")
    assert rec.amount == Decimal("42968.76")


def test_licaitong_merges_by_compatible_name() -> None:
    holding = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="holding.png",
        name="广发聚富",
        code="270023",
        page_id="holding",
    )
    detail = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="detail.png",
        name="广发聚富价值创造定开混合",
        quantity=_obs(Decimal("736.80")),
        unit_price=_obs(Decimal("5.1786")),
        amount=_obs(Decimal("3815.59")),
        page_id="detail",
    )

    records = merge_partials([holding, detail])

    assert len(records) == 1
    assert records[0].code == "270023"
    assert "广发" in records[0].name


def test_different_sources_are_not_merged() -> None:
    a = PartialRecord(
        asset_type="fund",
        source="tencent_licaitong",
        source_image="a.png",
        name="测试基金A",
        code="000001",
        amount=_obs(Decimal("100")),
    )
    b = PartialRecord(
        asset_type="fund",
        source="alipay_fund",
        source_image="b.png",
        name="测试基金A",
        code="000001",
        amount=_obs(Decimal("100")),
    )

    records = merge_partials([a, b])
    assert len(records) == 2
