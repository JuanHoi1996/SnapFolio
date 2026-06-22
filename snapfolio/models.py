"""Core data models for SnapFolio extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

AssetType = Literal["fund", "stock"]


@dataclass
class FieldObservation:
    value: Decimal | str
    confidence: float
    strategy: str


@dataclass
class PartialRecord:
    """Per-image extraction result; fields may be incomplete."""

    asset_type: AssetType
    source: str
    source_image: str
    name: str | None = None
    code: str | None = None
    quantity: FieldObservation | None = None
    unit_price: FieldObservation | None = None
    amount: FieldObservation | None = None
    confidence: float = 0.0
    flags: list[str] = field(default_factory=list)
    page_id: str | None = None


@dataclass
class PositionRecord:
    """Final reconciled and validated holding."""

    asset_type: AssetType
    source: str
    source_image: str
    name: str
    code: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    amount: Decimal | None
    confidence: float
    flags: list[str] = field(default_factory=list)
