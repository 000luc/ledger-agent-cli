from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledger_agent_cli.db import transaction
from ledger_agent_cli.importers.common import (
    apply_mapping,
    load_mapping,
    money_to_cents,
    parse_date_text,
    read_rows,
)

REQUIRED_GL_FIELDS = [
    "month",
    "voucher_date",
    "voucher_no",
    "account_code",
    "account_name",
]


def ensure_company(conn, company: str) -> int:
    conn.execute("INSERT OR IGNORE INTO companies(name) VALUES (?)", (company,))
    row = conn.execute("SELECT id FROM companies WHERE name=?", (company,)).fetchone()
    return int(row["id"])


def ensure_account(
    conn,
    company_id: int,
    year: int,
    account_code: str,
    account_name: str,
    account_level: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO accounts(company_id, year, account_code, account_name, account_level)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(company_id, year, account_code)
        DO UPDATE SET account_name=excluded.account_name,
                      account_level=COALESCE(excluded.account_level, accounts.account_level)
        """,
        (company_id, year, account_code, account_name, account_level),
    )


def create_batch(
    conn,
    company_id: int,
    source_type: str,
    source_file: Path,
    year: int,
    mapping: dict[str, str],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO import_batches(company_id, source_type, source_file, year, mapping_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company_id, source_type, str(source_file), year, json.dumps(mapping, ensure_ascii=False)),
    )
    return int(cursor.lastrowid)


def import_gl(
    db_path: str | Path,
    file_path: str | Path,
    company: str,
    year: int,
    mapping_path: str | Path,
) -> dict[str, Any]:
    source_file = Path(file_path)
    mapping = load_mapping(mapping_path)
    rows = read_rows(source_file)

    with transaction(db_path) as conn:
        company_id = ensure_company(conn, company)
        batch_id = create_batch(conn, company_id, "gl", source_file, year, mapping)
        header_ids: dict[tuple[int, str], int] = {}

        for index, row in enumerate(rows, start=1):
            mapped = apply_mapping(row, mapping, REQUIRED_GL_FIELDS)
            month = int(mapped["month"])
            voucher_no = str(mapped["voucher_no"]).strip()
            voucher_date = parse_date_text(mapped["voucher_date"])
            raw_json = json.dumps(mapped["raw"], ensure_ascii=False)
            key = (month, voucher_no)

            if key not in header_ids:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO journal_headers(
                      company_id, import_batch_id, year, month, voucher_date,
                      voucher_no, voucher_type, preparer, reviewer, bookkeeper, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_id,
                        batch_id,
                        year,
                        month,
                        voucher_date,
                        voucher_no,
                        mapped.get("voucher_type"),
                        mapped.get("preparer"),
                        mapped.get("reviewer"),
                        mapped.get("bookkeeper"),
                        raw_json,
                    ),
                )
                if cursor.lastrowid:
                    header_ids[key] = int(cursor.lastrowid)
                else:
                    existing = conn.execute(
                        """
                        SELECT id FROM journal_headers
                        WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                        """,
                        (company_id, year, month, voucher_no),
                    ).fetchone()
                    header_ids[key] = int(existing["id"])

            account_code = str(mapped["account_code"]).strip()
            account_name = str(mapped["account_name"]).strip()
            ensure_account(conn, company_id, year, account_code, account_name)
            conn.execute(
                """
                INSERT INTO journal_lines(
                  header_id, company_id, import_batch_id, year, month, voucher_date,
                  voucher_no, line_no, summary, account_code, account_name,
                  debit_cents, credit_cents, currency, auxiliary,
                  counterparty_account_code, counterparty_account_name, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    header_ids[key],
                    company_id,
                    batch_id,
                    year,
                    month,
                    voucher_date,
                    voucher_no,
                    int(mapped.get("line_no") or index),
                    mapped.get("summary"),
                    account_code,
                    account_name,
                    money_to_cents(mapped.get("debit")),
                    money_to_cents(mapped.get("credit")),
                    mapped.get("currency"),
                    mapped.get("auxiliary"),
                    mapped.get("counterparty_account_code"),
                    mapped.get("counterparty_account_name"),
                    raw_json,
                ),
            )

        conn.execute("UPDATE import_batches SET row_count=? WHERE id=?", (len(rows), batch_id))

    return {"company": company, "year": year, "line_count": len(rows)}
