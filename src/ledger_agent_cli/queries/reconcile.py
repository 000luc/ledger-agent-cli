from __future__ import annotations

from pathlib import Path

from ledger_agent_cli.db import connect
from ledger_agent_cli.queries.accounts import get_company_id


def reconcile_gl_tb(db_path: str | Path, company: str, year: int) -> dict:
    with connect(db_path) as conn:
        company_id = get_company_id(conn, company)
        rows = conn.execute(
            """
            WITH gl AS (
              SELECT account_code, account_name,
                     SUM(debit_cents) AS gl_debit_cents,
                     SUM(credit_cents) AS gl_credit_cents
              FROM journal_lines
              WHERE company_id=? AND year=?
              GROUP BY account_code, account_name
            ),
            tb AS (
              SELECT account_code, account_name,
                     SUM(current_debit_cents) AS tb_debit_cents,
                     SUM(current_credit_cents) AS tb_credit_cents
              FROM trial_balance
              WHERE company_id=? AND year=?
              GROUP BY account_code, account_name
            ),
            combined AS (
              SELECT
                COALESCE(gl.account_code, tb.account_code) AS account_code,
                COALESCE(gl.account_name, tb.account_name) AS account_name,
                COALESCE(gl.gl_debit_cents, 0) AS gl_debit_cents,
                COALESCE(tb.tb_debit_cents, 0) AS tb_debit_cents,
                COALESCE(gl.gl_credit_cents, 0) AS gl_credit_cents,
                COALESCE(tb.tb_credit_cents, 0) AS tb_credit_cents,
                COALESCE(gl.gl_debit_cents, 0) - COALESCE(tb.tb_debit_cents, 0) AS debit_diff_cents,
                COALESCE(gl.gl_credit_cents, 0) - COALESCE(tb.tb_credit_cents, 0) AS credit_diff_cents
              FROM gl
              LEFT JOIN tb ON tb.account_code = gl.account_code
              UNION
              SELECT
                COALESCE(gl.account_code, tb.account_code),
                COALESCE(gl.account_name, tb.account_name),
                COALESCE(gl.gl_debit_cents, 0),
                COALESCE(tb.tb_debit_cents, 0),
                COALESCE(gl.gl_credit_cents, 0),
                COALESCE(tb.tb_credit_cents, 0),
                COALESCE(gl.gl_debit_cents, 0) - COALESCE(tb.tb_debit_cents, 0),
                COALESCE(gl.gl_credit_cents, 0) - COALESCE(tb.tb_credit_cents, 0)
              FROM tb
              LEFT JOIN gl ON gl.account_code = tb.account_code
            )
            SELECT * FROM combined
            """,
            (company_id, year, company_id, year),
        ).fetchall()
    differences = [
        dict(row)
        for row in rows
        if int(row["debit_diff_cents"] or 0) != 0 or int(row["credit_diff_cents"] or 0) != 0
    ]
    return {
        "company": company,
        "year": year,
        "difference_count": len(differences),
        "differences": differences,
    }
