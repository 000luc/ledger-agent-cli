from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pandas as pd


def money_to_cents(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return 0
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "")
    amount = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cents = int(amount * 100)
    return -cents if negative else cents


def cents_to_money(cents: int) -> str:
    return str((Decimal(int(cents)) / Decimal(100)).quantize(Decimal("0.01")))


def parse_date_text(value: Any) -> str:
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception as exc:
        raise ValueError(f"Invalid date: {value}") from exc


def apply_mapping(
    row: dict[str, Any],
    mapping: dict[str, str],
    required: list[str] | None = None,
) -> dict[str, Any]:
    mapped: dict[str, Any] = {"raw": dict(row)}
    for target, source in mapping.items():
        if source in row:
            mapped[target] = row[source]
    for field in required or []:
        if field not in mapped or str(mapped[field]).strip() == "":
            raise ValueError(f"Missing mapped field: {field}")
    return mapped


def load_mapping(mapping_path: str | Path) -> dict[str, str]:
    return json.loads(Path(mapping_path).read_text(encoding="utf-8"))


def read_rows(file_path: str | Path) -> list[dict[str, Any]]:
    path = Path(file_path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=str).fillna("")
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str).fillna("")
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return frame.to_dict(orient="records")
