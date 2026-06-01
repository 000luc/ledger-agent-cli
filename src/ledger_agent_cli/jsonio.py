from __future__ import annotations

import json
from typing import Any


def success(command: str, data: Any, meta: dict[str, Any] | None = None) -> str:
    return json.dumps(
        {"ok": True, "command": command, "data": data, "meta": meta or {}, "error": None},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def failure(
    command: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    return json.dumps(
        {
            "ok": False,
            "command": command,
            "data": None,
            "meta": meta or {},
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
