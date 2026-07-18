"""Platform configuration dataclasses and the five supported platforms."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Literal

from snapfolio.models import PartialRecord

Archetype = Literal["list", "detail"]


@dataclass
class FieldSpec:
    """Declarative field extraction spec."""

    labels: tuple[str, ...]
    fallback_labels: tuple[str, ...] = ()
    column_header: str | None = None
    column_subfield: str | None = None  # for split columns like 市值/股数
    inline_first: bool = True
    direction: str = "right"
    max_distance: float = 0.4
    is_code: bool = False
    is_name: bool = False
    parse_nav_date: bool = False


@dataclass
class PageConfig:
    page_id: str
    signature: tuple[str, ...]
    signature_any_of: tuple[str, ...] | None = None


@dataclass
class PlatformConfig:
    platform_id: str
    display_name: str
    asset_type: Literal["fund", "stock"]
    archetype: Archetype
    pages: list[PageConfig]
    fields: dict[str, FieldSpec]
    list_headers: tuple[str, ...] = ()
    row_start_after: str | None = None
    name_code_same_row: bool = False
    card_delimiter: str | None = None
    cross_check_field: str = "amount"


# --- Platform configs ---

CMB_STOCK = PlatformConfig(
    platform_id="cmb_stock",
    display_name="招商证券",
    asset_type="stock",
    archetype="list",
    pages=[
        PageConfig(
            page_id="holdings",
            # Empty primary signature is intentional: all([]) is True, so matching
            # relies entirely on signature_any_of ("我的股票" OR "持仓数").
            signature=(),
            signature_any_of=("我的股票", "持仓数"),
        ),
    ],
    list_headers=("持仓市值",),
    row_start_after="证券/代码",
    name_code_same_row=True,
    fields={
        "name": FieldSpec(labels=(), is_name=True),
        "code": FieldSpec(labels=(), is_code=True),
        "amount": FieldSpec(
            labels=("持仓市值",),
            inline_first=True,
            # Values sit under column headers, not to the right of the label.
            direction="below",
        ),
        "quantity": FieldSpec(
            labels=("持仓数",),
            fallback_labels=("可用数",),
            inline_first=True,
        ),
        "unit_price": FieldSpec(
            labels=("现价",),
            inline_first=True,
        ),
    },
)

TENCENT_WESEE = PlatformConfig(
    platform_id="tencent_wesee",
    display_name="腾讯微证券",
    asset_type="stock",
    archetype="list",
    pages=[
        PageConfig(
            page_id="holdings",
            signature=("证券/代码", "市值/股数", "现价/成本"),
        ),
    ],
    list_headers=("证券/代码", "市值/股数", "现价/成本"),
    fields={
        "name": FieldSpec(labels=(), is_name=True),
        "code": FieldSpec(labels=(), is_code=True),
        "amount": FieldSpec(
            labels=("市值",),
            column_header="市值/股数",
            column_subfield="upper",
        ),
        "quantity": FieldSpec(
            labels=("股数",),
            column_header="市值/股数",
            column_subfield="lower",
        ),
        "unit_price": FieldSpec(
            labels=("现价",),
            column_header="现价/成本",
            column_subfield="upper",
        ),
    },
)

GUOSEN_JTY = PlatformConfig(
    platform_id="guosen_jty_stock",
    display_name="国信金太阳",
    asset_type="stock",
    archetype="list",
    pages=[
        PageConfig(
            page_id="holdings",
            signature=("持仓", "现价", "成本", "持股"),
        ),
    ],
    list_headers=("持仓",),
    card_delimiter=">",
    fields={
        "name": FieldSpec(labels=(), is_name=True),
        "code": FieldSpec(labels=(), is_code=True),
        "amount": FieldSpec(labels=("市值",), inline_first=True),
        "quantity": FieldSpec(
            labels=("持股",),
            fallback_labels=("可用",),
            inline_first=True,
        ),
        "unit_price": FieldSpec(labels=("现价",), inline_first=True),
    },
)

ALIPAY_FUND = PlatformConfig(
    platform_id="alipay_fund",
    display_name="支付宝基金",
    asset_type="fund",
    archetype="detail",
    pages=[
        PageConfig(
            page_id="detail",
            signature=("资产详情", "持有份额", "基金净值"),
        ),
    ],
    fields={
        "name": FieldSpec(
            labels=("资产详情",),
            direction="below",
            max_distance=0.15,
            is_name=True,
        ),
        "code": FieldSpec(labels=(), is_code=True),
        "amount": FieldSpec(
            labels=("金额(元)", "持有金额"),
            inline_first=True,
            direction="either",
            max_distance=0.4,
        ),
        "quantity": FieldSpec(
            labels=("持有份额",),
            inline_first=True,
            direction="either",
            max_distance=0.4,
        ),
        "unit_price": FieldSpec(
            labels=("基金净值",),
            inline_first=True,
            parse_nav_date=True,
            direction="either",
            max_distance=0.4,
        ),
    },
)

LICAITONG_HOLDING = PageConfig(
    page_id="holding",
    signature=("持有中",),
    signature_any_of=("单位净值", "QDII"),
)

LICAITONG_DETAIL = PageConfig(
    page_id="detail",
    signature=("持有资产", "持有份额", "最新净值"),
)

TENCENT_LICAITONG = PlatformConfig(
    platform_id="tencent_licaitong",
    display_name="微信理财通",
    asset_type="fund",
    archetype="detail",
    pages=[LICAITONG_HOLDING, LICAITONG_DETAIL],
    fields={
        "name": FieldSpec(labels=(), is_name=True),
        "code": FieldSpec(labels=(), is_code=True),
        "amount": FieldSpec(
            labels=("持有资产",),
            inline_first=True,
            direction="either",
            max_distance=0.4,
        ),
        "quantity": FieldSpec(
            labels=("持有份额",),
            inline_first=True,
            direction="either",
            max_distance=0.4,
        ),
        "unit_price": FieldSpec(
            labels=("最新净值", "单位净值"),
            inline_first=True,
            parse_nav_date=True,
            direction="either",
            max_distance=0.4,
        ),
    },
)

PLATFORM_CONFIGS: list[PlatformConfig] = [
    CMB_STOCK,
    TENCENT_WESEE,
    GUOSEN_JTY,
    ALIPAY_FUND,
    TENCENT_LICAITONG,
]

PLATFORM_BY_ID: dict[str, PlatformConfig] = {p.platform_id: p for p in PLATFORM_CONFIGS}

_VALID_FIELDS = {f.name for f in dataclasses.fields(PartialRecord)}
for _cfg in PLATFORM_CONFIGS:
    for _key in _cfg.fields:
        assert _key in _VALID_FIELDS, f"{_cfg.platform_id}: unknown field {_key!r}"
