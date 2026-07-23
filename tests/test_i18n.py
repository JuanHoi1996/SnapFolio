"""Smoke tests for UI i18n catalogs."""

from __future__ import annotations

from snapfolio.i18n import LANG_OPTIONS, _COLUMNS, _PLATFORM, _STRINGS, display_columns, platform_labels, t


def test_all_langs_have_same_keys() -> None:
    base = set(_STRINGS["zh-CN"])
    for lang in LANG_OPTIONS:
        assert set(_STRINGS[lang]) == base
        assert set(_PLATFORM[lang]) == set(_PLATFORM["zh-CN"])
        assert set(_COLUMNS[lang]) == set(_COLUMNS["zh-CN"])


def test_format_placeholders() -> None:
    assert "3" in t("en", "success", n=3)
    assert "3" in t("zh-CN", "success", n=3)
    assert "3" in t("zh-TW", "success", n=3)
    assert "foo.png" in t("en", "processing_file", name="foo.png", i=1, total=2)


def test_platform_and_columns() -> None:
    assert platform_labels("en")["cmb_stock"] == "CMB Securities"
    assert platform_labels("zh-TW")["tencent_licaitong"] == "微信理財通"
    cols = dict(display_columns("en"))
    assert cols["amount"] == "Market value"
