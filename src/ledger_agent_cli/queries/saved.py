from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledger_agent_cli.db import connect, transaction
from ledger_agent_cli.sql_guard import assert_read_only_select


def add_saved_query(
    db_path: str | Path,
    name: str,
    description: str,
    query: str,
    parameters: list[str] | None = None,
) -> dict:
    assert_read_only_select(query)
    parameter_names = parameters or []
    with transaction(db_path) as conn:
        conn.execute(
            """
            INSERT INTO saved_queries(name, description, query, parameters_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              description=excluded.description,
              query=excluded.query,
              parameters_json=excluded.parameters_json
            """,
            (name, description, query, json.dumps(parameter_names, ensure_ascii=False)),
        )
    return {"name": name, "description": description, "parameters": parameter_names}


def list_saved_queries(db_path: str | Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name, description, query, parameters_json FROM saved_queries ORDER BY name"
        ).fetchall()
    data = []
    for row in rows:
        item = dict(row)
        item["parameters"] = json.loads(item.pop("parameters_json"))
        data.append(item)
    return data


def run_saved_query(
    db_path: str | Path,
    name: str,
    values: dict[str, Any] | None = None,
    limit: int = 200,
) -> dict:
    safe_limit = min(max(limit, 1), 1000)
    bind_values = values or {}
    with connect(db_path) as conn:
        saved = conn.execute("SELECT query FROM saved_queries WHERE name=?", (name,)).fetchone()
        if saved is None:
            raise ValueError(f"Saved query not found: {name}")
        query = saved["query"]
        assert_read_only_select(query)
        rows = conn.execute(
            f"SELECT * FROM ({query.rstrip(';')}) LIMIT :__limit",
            {**bind_values, "__limit": safe_limit},
        ).fetchall()
    return {"name": name, "values": bind_values, "rows": [dict(row) for row in rows], "limit": safe_limit}
