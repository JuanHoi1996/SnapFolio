"""Regression tests using OCR fixture files (skip if none present)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from conftest import discover_fixture_pairs, load_expected
from snapfolio.pipeline import process_fixtures

_PAIRS = discover_fixture_pairs()


@pytest.mark.skipif(not _PAIRS, reason="no fixtures in tests/fixtures/")
@pytest.mark.parametrize(
    "fixture_path,expected_path",
    _PAIRS,
    ids=[p[0].stem for p in _PAIRS],
)
def test_regression_fixture(fixture_path: Path, expected_path: Path) -> None:
    records = process_fixtures([fixture_path])
    expected = load_expected(expected_path)

    assert len(records) == len(expected), f"record count mismatch: {len(records)} vs {len(expected)}"

    for rec, exp in zip(records, expected):
        if "source" in exp:
            assert rec.source == exp["source"]
        if "code" in exp and exp["code"]:
            assert rec.code == exp["code"]
        if "name" in exp:
            assert rec.name == exp["name"]
        for field in ("quantity", "unit_price", "amount"):
            if field not in exp or exp[field] is None:
                continue
            actual = getattr(rec, field)
            assert actual is not None, f"missing {field} for {rec.name}"
            tol = Decimal("0.02")
            assert abs(actual - Decimal(str(exp[field]))) <= tol * abs(Decimal(str(exp[field])))
