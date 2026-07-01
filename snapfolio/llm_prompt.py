"""Prompt constants for Gemini vision fallback extraction."""

# https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

EXTRACTION_PROMPT = """\
Analyze this Chinese broker/fund app screenshot and extract every visible holding position.

Return ONLY a JSON array (no markdown, no code fences, no commentary). Each object must have:
- "name": fund or stock name (string)
- "code": 6-digit security code, or null if not visible
- "quantity": shares/units held, or null if not visible
- "unit_price": unit price or NAV, or null if not visible
- "amount": market value or total assets, or null if not visible
- "asset_type": "fund" or "stock"

Use null for any field not clearly visible in the screenshot. Do not guess or invent values.
If no holdings are visible, return [].
"""
