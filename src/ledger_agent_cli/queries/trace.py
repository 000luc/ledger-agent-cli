from __future__ import annotations

from pathlib import Path

from ledger_agent_cli.db import connect
from ledger_agent_cli.importers.common import cents_to_money
from ledger_agent_cli.queries.accounts import get_company_id


def trace_depreciation(db_path: str | Path, company: str, year: int) -> dict:
    with connect(db_path) as conn:
        company_id = get_company_id(conn, company)
        rows = conn.execute(
            """
            WITH depreciation_vouchers AS (
              SELECT DISTINCT header_id
              FROM journal_lines
              WHERE company_id=? AND year=?
                AND credit_cents > 0
                AND (account_name LIKE '%累计折旧%' OR summary LIKE '%折旧%')
            )
            SELECT
              jl.account_code AS debit_account_code,
              jl.account_name AS debit_account_name,
              SUM(jl.debit_cents) AS amount_cents,
              COUNT(DISTINCT jl.header_id) AS voucher_count,
              MIN(jl.voucher_no) AS sample_voucher_no
            FROM journal_lines jl
            JOIN depreciation_vouchers dv ON dv.header_id = jl.header_id
            WHERE jl.debit_cents > 0
            GROUP BY jl.account_code, jl.account_name
            ORDER BY amount_cents DESC
            """,
            (company_id, year),
        ).fetchall()
    data_rows = [dict(row) for row in rows]
    for row in data_rows:
        row["amount"] = cents_to_money(row["amount_cents"])
    return {"company": company, "year": year, "rows": data_rows}
