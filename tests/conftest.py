"""Pytest configuration and fixture helpers."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES_DIR = ROOT / "tests" / "fixtures"


def discover_fixture_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    if not FIXTURES_DIR.exists():
        return pairs
    for fixture in sorted(FIXTURES_DIR.glob("*.fixture.txt")):
        expected = fixture.with_suffix("").with_suffix(".expected.json")
        if expected.name.endswith(".fixture.expected.json"):
            expected = fixture.with_name(fixture.stem.replace(".fixture", "") + ".expected.json")
        # fixture foo.fixture.txt -> foo.expected.json
        expected = fixture.parent / (fixture.name.replace(".fixture.txt", ".expected.json"))
        if expected.exists():
            pairs.append((fixture, expected))
    return pairs


def load_expected(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]
