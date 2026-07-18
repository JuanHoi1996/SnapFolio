"""Robust number cleaning, parsing, and security-code extraction."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Inline label+value patterns: label followed immediately by numeric value
_INLINE_NUMERIC = re.compile(
    r"^(?P<label>[^\d\+\-\.]+?)(?P<value>[\+\-]?[\d,，\.。]+(?:\.\d+)?)$"
)
_INLINE_CODE_SUFFIX = re.compile(r"^(?P<name>.+?)(?P<code>\d{6})[>》\s]*$")
_CODE_IN_TEXT = re.compile(r"(?:SH|SZ|sh|sz)?\s*0*(\d{6})")
_SIX_DIGIT = re.compile(r"\d{6}")
# Trailing NAV date like (02-13) / （02-13）; OCR may mix half/full-width parens.
_DATE_SUFFIX = re.compile(r"[(\uFF08]\s*[\d\-]+\s*[)\uFF09]\s*$")


def normalize_numeric_text(text: str) -> str:
    """Normalize OCR quirks in a numeric token before parsing."""
    s = text.strip()
    s = s.replace("，", ",").replace("。", ".")
    s = re.sub(r"[^\d\+\-\.,]", "", s)
    return s


def parse_decimal(text: str) -> Decimal | None:
    """
    Parse a numeric string handling Chinese OCR quirks.
    Multiple dots: all but the last are thousands separators ('9.048.62' -> 9048.62).
    """
    if not text or not text.strip():
        return None

    s = normalize_numeric_text(text)
    if not s or s in ("+", "-"):
        return None

    # Strip leading sign for processing, re-apply later
    negative = s.startswith("-")
    if s.startswith(("+", "-")):
        s = s[1:]

    s = s.replace(",", "")

    dots = s.count(".")
    if dots > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]

    try:
        value = Decimal(s)
        return -value if negative else value
    except InvalidOperation:
        return None


def extract_inline_value(token_text: str, label: str) -> Decimal | None:
    """Extract numeric value when label and value are merged in one token."""
    text = token_text.strip()
    if not text.startswith(label):
        return None

    remainder = text[len(label) :]
    remainder = _DATE_SUFFIX.sub("", remainder)
    return parse_decimal(remainder)


def extract_inline_str(token_text: str, label: str) -> str | None:
    """Extract string value after label in a merged token."""
    text = token_text.strip()
    if not text.startswith(label):
        return None
    return text[len(label) :].strip() or None


def extract_code(text: str) -> str | None:
    """
    Extract a clean 6-digit security code from OCR text.
    Handles SH600150, 0601995, 002230》, etc.
    """
    if not text:
        return None

    m = _CODE_IN_TEXT.search(re.sub(r"\s+", "", text))
    if m:
        return m.group(1)

    m = _INLINE_CODE_SUFFIX.match(text.strip())
    if m:
        return m.group("code")

    digits = _SIX_DIGIT.findall(text)
    if digits:
        return digits[0]

    return None


def extract_name_code_from_merged(text: str) -> tuple[str | None, str | None]:
    """Parse 'name+code>' style tokens e.g. '中科三环000970>'."""
    m = _INLINE_CODE_SUFFIX.match(text.strip())
    if m:
        return m.group("name").strip(), m.group("code")
    code = extract_code(text)
    if code:
        name = text.replace(code, "").strip(">》 \t")
        return name or None, code
    return text.strip() or None, None


def parse_nav_with_date(text: str) -> Decimal | None:
    """Parse unit price that may include a date suffix: '1.4465(02-13)'."""
    cleaned = _DATE_SUFFIX.sub("", text.strip())
    return parse_decimal(cleaned)
