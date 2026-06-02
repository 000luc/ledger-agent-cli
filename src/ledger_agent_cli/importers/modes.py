from __future__ import annotations

from collections.abc import Hashable, Iterable
from typing import Literal

from ledger_agent_cli.errors import InvalidImportModeError

ImportMode = Literal["error", "skip", "replace"]
VALID_IMPORT_MODES = {"error", "skip", "replace"}


def validate_import_mode(mode: str) -> ImportMode:
    if mode not in VALID_IMPORT_MODES:
        raise InvalidImportModeError(mode)
    return mode  # type: ignore[return-value]


def normalize_auxiliary(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def count_duplicate_keys(keys: Iterable[Hashable]) -> int:
    seen = set()
    duplicates = set()
    for key in keys:
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return len(duplicates)


def gl_scope_key(mapped: dict) -> tuple[int, str]:
    return int(mapped["month"]), str(mapped["voucher_no"]).strip()


def gl_line_key(mapped: dict, fallback_line_no: int) -> tuple[int, str, int]:
    return (*gl_scope_key(mapped), int(mapped.get("line_no") or fallback_line_no))


def tb_scope_key(mapped: dict) -> tuple[int, str, str]:
    return (
        int(mapped["month"]),
        str(mapped["account_code"]).strip(),
        normalize_auxiliary(mapped.get("auxiliary")),
    )
