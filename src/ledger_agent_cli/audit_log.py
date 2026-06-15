from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _log_path(db_path: str | Path) -> Path:
    path = Path(db_path)
    return path.parent / "ledger-cli.log"


def log_operation(
    db_path: str | Path,
    command: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    success: bool = True,
) -> None:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "command": command,
        "arguments": _sanitize_arguments(arguments),
        "result_summary": _summarize_result(result),
        "success": success,
    }
    log_file = _log_path(db_path)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Intentionally silent: audit logging must never break the main operation.
        pass


def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        if key in {"file", "mapping"}:
            safe[key] = str(value)
        else:
            safe[key] = value
    return safe


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "mode",
        "line_count",
        "row_count",
        "inserted_count",
        "skipped_count",
        "deleted_count",
        "duplicate_count",
        "deleted_lines",
        "deleted_headers",
        "deleted_rows",
        "deleted_batches",
        "deleted_tb_rows",
        "batch_id",
        "matched_headers",
        "matched_lines",
        "matched_rows",
        "dry_run",
    ]
    return {k: result.get(k) for k in keys if k in result}
