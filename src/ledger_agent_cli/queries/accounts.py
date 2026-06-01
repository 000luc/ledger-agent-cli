from __future__ import annotations

from pathlib import Path

from ledger_agent_cli.db import connect


def get_company_id(conn, company: str) -> int:
    row = conn.execute("SELECT id FROM companies WHERE name=?", (company,)).fetchone()
    if row is None:
        raise ValueError(f"Company not found: {company}")
    return int(row["id"])


def search_accounts(db_path: str | Path, company: str, year: int, keyword: str) -> list[dict]:
    with connect(db_path) as conn:
        company_id = get_company_id(conn, company)
        rows = conn.execute(
            """
            SELECT account_code, account_name, account_level, parent_code, is_leaf
            FROM accounts
            WHERE company_id=? AND year=?
              AND (account_code LIKE ? OR account_name LIKE ?)
            ORDER BY account_code
            """,
            (company_id, year, f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
    return [dict(row) for row in rows]
