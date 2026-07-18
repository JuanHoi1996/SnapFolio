"""Unit tests for number cleaning and code extraction."""

from __future__ import annotations

from decimal import Decimal

import pytest

from snapfolio.numbers import (
    extract_code,
    extract_inline_value,
    extract_name_code_from_merged,
    parse_decimal,
    parse_nav_with_date,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("9.048.62", Decimal("9048.62")),
        ("+12,779.20", Decimal("12779.20")),
        ("1.5480", Decimal("1.5480")),
        ("9048.62", Decimal("9048.62")),
        ("1,234.56", Decimal("1234.56")),
    ],
)
def test_parse_decimal(text: str, expected: Decimal) -> None:
    assert parse_decimal(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("SH600150", "600150"),
        ("SH 600150", "600150"),
        ("0601995", "601995"),
        ("002230》", "002230"),
        ("270023中高风险", "270023"),
    ],
)
def test_extract_code(text: str, expected: str) -> None:
    assert extract_code(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.4465(02-13)", Decimal("1.4465")),
        ("1.4465（02-13）", Decimal("1.4465")),
        ("1.4465(02-13）", Decimal("1.4465")),
        ("1.4465", Decimal("1.4465")),
    ],
)
def test_parse_nav_with_date(text: str, expected: Decimal) -> None:
    assert parse_nav_with_date(text) == expected


def test_extract_inline_value() -> None:
    assert extract_inline_value("持仓数24500", "持仓数") == Decimal("24500")
    assert extract_inline_value("现价1.5480", "现价") == Decimal("1.5480")
    assert extract_inline_value("成本1.4574", "成本") == Decimal("1.4574")
    assert extract_inline_value("基金净值1.4465（02-13）", "基金净值") == Decimal("1.4465")


def test_extract_code_fullwidth_space() -> None:
    assert extract_code("005\u3000827") == "005827"


def test_extract_name_code_merged() -> None:
    name, code = extract_name_code_from_merged("中科三环000970>")
    assert name == "中科三环"
    assert code == "000970"

    name2, code2 = extract_name_code_from_merged("科大讯飞002230》")
    assert name2 == "科大讯飞"
    assert code2 == "002230"
