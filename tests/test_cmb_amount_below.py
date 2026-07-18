"""Regression: CMB amount must come from below 持仓市值, not from 盈亏."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from snapfolio.pipeline import ingest_fixture, process_document

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "ml_fixtures"
    / "023a711e7a498d322ec038334732fba7.fixture.txt"
)


@pytest.mark.skipif(not _FIXTURE.is_file(), reason="local OCR fixture not present")
def test_cmb_amount_not_confused_with_pnl() -> None:
    doc = ingest_fixture(_FIXTURE)
    partials = process_document(doc, "023a711e.jpg")
    by_code = {p.code: p for p in partials if p.code}

    chip = by_code["588200"]
    assert chip.amount is not None
    assert chip.amount.value == Decimal("39357.00")
    assert chip.quantity is not None and chip.quantity.value == Decimal("9000")
    assert chip.unit_price is not None and chip.unit_price.value == Decimal("4.3730")

    citic = by_code["600030"]
    assert citic.amount is not None
    assert citic.amount.value == Decimal("43425.00")

    # Spot-check a previously-correct row still works.
    hx = by_code["588000"]
    assert hx.amount is not None
    assert hx.amount.value == Decimal("23122.00")
