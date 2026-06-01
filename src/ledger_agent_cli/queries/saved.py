from __future__ import annotations

import json
from pathlib import Path

from ledger_agent_cli.db import connect, transaction
from ledger_agent_cli.sql_guard import assert_read_only_select


def add_saved_query(db_path: str | Path, name: str, description: str, query: str) -> dict:
    assert_read_only_select(query)
    with transaction(db_path) as conn:
        conn.execute(
            """
            INSERT INTO saved_queries(name, description, query, parameters_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name)
            DO UPDATE SET description=excluded.description, query=excluded.query
            """,
            (name, description, query, json.dumps([], ensure_ascii=False)),
        )
    return {"name": name, "description": description}


def list_saved_queries(db_path: str | Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT name, description, query FROM saved_queries ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def run_saved_query(db_path: str | Path, name: str, limit: int = 200) -> dict:
    safe_limit = min(max(limit, 1), 1000)
    with connect(db_path) as conn:
        saved = conn.execute("SELECT query FROM saved_queries WHERE name=?", (name,)).fetchone()
        if saved is None:
            raise ValueError(f"Saved query not found: {name}")
        query = saved["query"]
        assert_read_only_select(query)
        rows = conn.execute(f"SELECT * FROM ({query.rstrip(';')}) LIMIT ?", (safe_limit,)).fetchall()
    return {"name": name, "rows": [dict(row) for row in rows], "limit": safe_limit}
