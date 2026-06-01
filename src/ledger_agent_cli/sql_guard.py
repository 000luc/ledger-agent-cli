from __future__ import annotations

import re

BLOCKED_SQL_WORDS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "exec",
    "insert",
    "pragma",
    "replace",
    "truncate",
    "update",
    "vacuum",
}


def assert_read_only_select(query: str) -> None:
    stripped = query.strip().rstrip(";").strip()
    lowered = stripped.lower()
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise ValueError("Only SELECT or WITH queries are allowed")
    tokens = set(re.findall(r"[a-z_]+", lowered))
    blocked = sorted(tokens & BLOCKED_SQL_WORDS)
    if blocked:
        raise ValueError(f"Blocked SQL keyword: {blocked[0]}")
