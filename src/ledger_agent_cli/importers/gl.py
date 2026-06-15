from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledger_agent_cli.audit_log import log_operation
from ledger_agent_cli.db import transaction
from ledger_agent_cli.errors import DuplicateImportScopeError, DuplicateInputScopeError
from ledger_agent_cli.importers.common import (
    apply_mapping,
    load_mapping,
    money_to_cents,
    parse_date_text,
    read_rows,
)
from ledger_agent_cli.importers.modes import (
    count_duplicate_keys,
    gl_line_key,
    gl_scope_key,
    validate_import_mode,
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
    mode: str = "error",
) -> dict[str, Any]:
    import_mode = validate_import_mode(mode)
    source_file = Path(file_path)
    mapping = load_mapping(mapping_path)
    rows = read_rows(source_file)
    mapped_rows = [apply_mapping(row, mapping, REQUIRED_GL_FIELDS) for row in rows]
    input_duplicate_count = count_duplicate_keys(
        gl_line_key(mapped, index) for index, mapped in enumerate(mapped_rows, start=1)
    )
    if input_duplicate_count:
        raise DuplicateInputScopeError(input_duplicate_count)
    target_keys = sorted(set(gl_scope_key(mapped) for mapped in mapped_rows))

    with transaction(db_path) as conn:
        company_id = ensure_company(conn, company)
        existing_keys = set()
        for month, voucher_no in target_keys:
            row = conn.execute(
                """
                SELECT id FROM journal_headers
                WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                """,
                (company_id, year, month, voucher_no),
            ).fetchone()
            if row is not None:
                existing_keys.add((month, voucher_no))

        if existing_keys and import_mode == "error":
            raise DuplicateImportScopeError(len(existing_keys))

        deleted_count = 0
        if existing_keys and import_mode == "replace":
            for month, voucher_no in existing_keys:
                deleted_lines = conn.execute(
                    """
                    DELETE FROM journal_lines
                    WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                    """,
                    (company_id, year, month, voucher_no),
                ).rowcount
                conn.execute(
                    """
                    DELETE FROM journal_headers
                    WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                    """,
                    (company_id, year, month, voucher_no),
                )
                if deleted_lines:
                    deleted_count += 1

        batch_id = create_batch(conn, company_id, "gl", source_file, year, mapping)
        header_ids: dict[tuple[int, str], int] = {}
        inserted_keys: set[tuple[int, str]] = set()
        skipped_keys: set[tuple[int, str]] = set()

        for index, mapped in enumerate(mapped_rows, start=1):
            month = int(mapped["month"])
            voucher_no = str(mapped["voucher_no"]).strip()
            row_key = gl_scope_key(mapped)
            if import_mode == "skip" and row_key in existing_keys:
                skipped_keys.add(row_key)
                continue
            inserted_keys.add(row_key)
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

        inserted_line_count = len(
            [key for key in map(gl_scope_key, mapped_rows) if key not in skipped_keys]
        )
        conn.execute(
            "UPDATE import_batches SET row_count=? WHERE id=?", (inserted_line_count, batch_id)
        )

    result = {
        "company": company,
        "year": year,
        "mode": import_mode,
        "line_count": len(rows),
        "inserted_count": len(inserted_keys),
        "skipped_count": len(skipped_keys),
        "deleted_count": deleted_count,
        "duplicate_count": len(existing_keys),
    }
    log_operation(
        db_path,
        "import.gl",
        {
            "company": company,
            "year": year,
            "file": str(source_file),
            "mapping": str(mapping_path),
            "mode": import_mode,
        },
        result,
    )
    return result
