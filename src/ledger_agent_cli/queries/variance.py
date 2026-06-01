from __future__ import annotations

from pathlib import Path

from ledger_agent_cli.db import connect
from ledger_agent_cli.importers.common import cents_to_money
from ledger_agent_cli.queries.accounts import get_company_id


def tb_variance(db_path: str | Path, company: str, year: int, compare_year: int, account: str) -> dict:
    with connect(db_path) as conn:
        company_id = get_company_id(conn, company)
        rows = conn.execute(
            """
            WITH cur AS (
              SELECT account_code, account_name, SUM(current_debit_cents - current_credit_cents) AS amount
              FROM trial_balance
              WHERE company_id=? AND year=? AND account_name LIKE ?
              GROUP BY account_code, account_name
            ),
            cmp AS (
              SELECT account_code, account_name, SUM(current_debit_cents - current_credit_cents) AS amount
              FROM trial_balance
              WHERE company_id=? AND year=? AND account_name LIKE ?
              GROUP BY account_code, account_name
            ),
            combined AS (
              SELECT
                COALESCE(cur.account_code, cmp.account_code) AS account_code,
                COALESCE(cur.account_name, cmp.account_name) AS account_name,
                COALESCE(cur.amount, 0) AS current_cents,
                COALESCE(cmp.amount, 0) AS compare_cents,
                COALESCE(cur.amount, 0) - COALESCE(cmp.amount, 0) AS delta_cents
              FROM cur
              LEFT JOIN cmp ON cmp.account_code = cur.account_code
              UNION
              SELECT
                COALESCE(cur.account_code, cmp.account_code),
                COALESCE(cur.account_name, cmp.account_name),
                COALESCE(cur.amount, 0),
                COALESCE(cmp.amount, 0),
                COALESCE(cur.amount, 0) - COALESCE(cmp.amount, 0)
              FROM cmp
              LEFT JOIN cur ON cur.account_code = cmp.account_code
            )
            SELECT account_code, account_name, current_cents, compare_cents, delta_cents
            FROM combined
            ORDER BY ABS(delta_cents) DESC
            """,
            (company_id, year, f"%{account}%", company_id, compare_year, f"%{account}%"),
        ).fetchall()
    data_rows = [dict(row) for row in rows]
    for row in data_rows:
        row["current_amount"] = cents_to_money(row["current_cents"])
        row["compare_amount"] = cents_to_money(row["compare_cents"])
        row["delta_amount"] = cents_to_money(row["delta_cents"])
    return {
        "company": company,
        "year": year,
        "compare_year": compare_year,
        "account": account,
        "rows": data_rows,
    }


def gl_variance(db_path: str | Path, company: str, year: int, compare_year: int, account: str) -> dict:
    with connect(db_path) as conn:
        company_id = get_company_id(conn, company)
        totals = conn.execute(
            """
            SELECT
              SUM(CASE WHEN year=? THEN debit_cents - credit_cents ELSE 0 END) AS current_total_cents,
              SUM(CASE WHEN year=? THEN debit_cents - credit_cents ELSE 0 END) AS compare_total_cents
            FROM journal_lines
            WHERE company_id=? AND account_name LIKE ?
            """,
            (year, compare_year, company_id, f"%{account}%"),
        ).fetchone()
        current_lines = conn.execute(
            """
            SELECT voucher_date, voucher_no, summary, account_code, account_name,
                   debit_cents, credit_cents, auxiliary
            FROM journal_lines
            WHERE company_id=? AND year=? AND account_name LIKE ?
            ORDER BY ABS(debit_cents - credit_cents) DESC, voucher_date
            LIMIT 50
            """,
            (company_id, year, f"%{account}%"),
        ).fetchall()
    current_total = int(totals["current_total_cents"] or 0)
    compare_total = int(totals["compare_total_cents"] or 0)
    return {
        "company": company,
        "year": year,
        "compare_year": compare_year,
        "account": account,
        "current_total_cents": current_total,
        "compare_total_cents": compare_total,
        "delta_cents": current_total - compare_total,
        "current_total_amount": cents_to_money(current_total),
        "compare_total_amount": cents_to_money(compare_total),
        "delta_amount": cents_to_money(current_total - compare_total),
        "current_lines": [dict(row) for row in current_lines],
    }
