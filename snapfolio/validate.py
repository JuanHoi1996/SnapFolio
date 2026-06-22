"""Amount cross-check, confidence aggregation, and review flags."""

from __future__ import annotations

from decimal import Decimal

from snapfolio.models import PositionRecord

DEFAULT_TOLERANCE = Decimal("0.015")
LOW_OCR_THRESHOLD = 0.5


def validate_records(
    records: list[PositionRecord],
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> list[PositionRecord]:
    validated: list[PositionRecord] = []

    for rec in records:
        flags = list(rec.flags)

        if rec.confidence < LOW_OCR_THRESHOLD:
            if "low_ocr_confidence" not in flags:
                flags.append("low_ocr_confidence")

        missing = [
            f
            for f, v in (
                ("quantity", rec.quantity),
                ("unit_price", rec.unit_price),
                ("amount", rec.amount),
            )
            if v is None
        ]
        if missing:
            if "needs_review" not in flags:
                flags.append("needs_review")
            if "incomplete_fields" not in flags:
                flags.append("incomplete_fields")

        if rec.quantity is not None and rec.unit_price is not None and rec.amount is not None:
            expected = rec.quantity * rec.unit_price
            if expected != 0:
                rel_err = abs(rec.amount - expected) / abs(expected)
                if rel_err > tolerance:
                    if "amount_mismatch" not in flags:
                        flags.append("amount_mismatch")
                    if "needs_review" not in flags:
                        flags.append("needs_review")

        validated.append(
            PositionRecord(
                asset_type=rec.asset_type,
                source=rec.source,
                source_image=rec.source_image,
                name=rec.name,
                code=rec.code,
                quantity=rec.quantity,
                unit_price=rec.unit_price,
                amount=rec.amount,
                confidence=rec.confidence,
                flags=flags,
            )
        )

    return validated
