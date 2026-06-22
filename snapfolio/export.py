"""Export PositionRecords to DataFrame, xlsx, and csv."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from snapfolio.models import PositionRecord


def records_to_dataframe(records: list[PositionRecord]) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append(
            {
                "asset_type": r.asset_type,
                "source": r.source,
                "source_image": r.source_image,
                "name": r.name,
                "code": r.code or "",
                "quantity": float(r.quantity) if r.quantity is not None else None,
                "unit_price": float(r.unit_price) if r.unit_price is not None else None,
                "amount": float(r.amount) if r.amount is not None else None,
                "confidence": r.confidence,
                "flags": ",".join(r.flags),
            }
        )
    return pd.DataFrame(rows)


def export_xlsx(records: list[PositionRecord], output_path: str | Path) -> None:
    df = records_to_dataframe(records)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="holdings")
        ws = writer.sheets["holdings"]
        if "code" in df.columns:
            code_col = df.columns.get_loc("code") + 1
            for row in range(2, len(df) + 2):
                cell = ws.cell(row=row, column=code_col)
                cell.number_format = "@"


def export_csv(records: list[PositionRecord], output_path: str | Path) -> None:
    df = records_to_dataframe(records)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
