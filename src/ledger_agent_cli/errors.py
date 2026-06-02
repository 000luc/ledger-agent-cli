from __future__ import annotations

from typing import Any


class LedgerCliError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class DuplicateImportScopeError(LedgerCliError):
    def __init__(self, duplicate_count: int):
        super().__init__(
            "duplicate_import_scope",
            "Target data already exists. Use --mode replace to overwrite or --mode skip to ignore.",
            {"duplicate_count": duplicate_count},
        )


class DuplicateInputScopeError(LedgerCliError):
    def __init__(self, duplicate_count: int):
        super().__init__(
            "duplicate_input_scope",
            "Input file contains duplicate rows for the import key.",
            {"duplicate_count": duplicate_count},
        )


class InvalidImportModeError(LedgerCliError):
    def __init__(self, mode: str):
        super().__init__(
            "invalid_import_mode",
            "Import mode must be one of: error, skip, replace.",
            {"mode": mode},
        )
