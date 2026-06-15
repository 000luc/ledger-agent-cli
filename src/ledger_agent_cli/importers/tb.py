from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledger_agent_cli.db import transaction
from ledger_agent_cli.errors import DuplicateImportScopeError, DuplicateInputScopeError
from ledger_agent_cli.importers.common import apply_mapping, load_mapping, money_to_cents, read_rows
from ledger_agent_cli.importers.gl import create_batch, ensure_account, ensure_company
from ledger_agent_cli.importers.modes import (
    count_duplicate_keys,
    normalize_auxiliary,
    tb_scope_key,
    validate_import_mode,
)

REQUIRED_TB_FIELDS = ["month", "account_code", "account_name"]


def import_tb(
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
    mapped_rows = [apply_mapping(row, mapping, REQUIRED_TB_FIELDS) for row in rows]
    input_duplicate_count = count_duplicate_keys(tb_scope_key(mapped) for mapped in mapped_rows)
    if input_duplicate_count:
        raise DuplicateInputScopeError(input_duplicate_count)
    target_keys = sorted(set(tb_scope_key(mapped) for mapped in mapped_rows))

    with transaction(db_path) as conn:
        company_id = ensure_company(conn, company)
        existing_keys = set()
        for month, account_code, auxiliary in target_keys:
            row = conn.execute(
                """
                SELECT id FROM trial_balance
                WHERE company_id=? AND year=? AND month=? AND account_code=?
                  AND COALESCE(auxiliary, '')=?
                """,
                (company_id, year, month, account_code, auxiliary),
            ).fetchone()
            if row is not None:
                existing_keys.add((month, account_code, auxiliary))

        if existing_keys and import_mode == "error":
            raise DuplicateImportScopeError(len(existing_keys))

        deleted_count = 0
        if existing_keys and import_mode == "replace":
            for month, account_code, auxiliary in existing_keys:
                deleted_count += conn.execute(
                    """
                    DELETE FROM trial_balance
                    WHERE company_id=? AND year=? AND month=? AND account_code=?
                      AND COALESCE(auxiliary, '')=?
                    """,
                    (company_id, year, month, account_code, auxiliary),
                ).rowcount

        batch_id = create_batch(conn, company_id, "tb", source_file, year, mapping)
        inserted_keys: set[tuple[int, str, str]] = set()
        skipped_keys: set[tuple[int, str, str]] = set()

        for mapped in mapped_rows:
            row_key = tb_scope_key(mapped)
            if import_mode == "skip" and row_key in existing_keys:
                skipped_keys.add(row_key)
                continue
            inserted_keys.add(row_key)
            account_code = str(mapped["account_code"]).strip()
            account_name = str(mapped["account_name"]).strip()
            account_level_text = str(mapped.get("account_level", "")).strip()
            account_level = int(account_level_text) if account_level_text else None
            ensure_account(conn, company_id, year, account_code, account_name, account_level)
            conn.execute(
                """
                INSERT INTO trial_balance(
                  company_id, import_batch_id, year, month, account_code, account_name,
                  account_level, opening_balance_cents, current_debit_cents,
                  current_credit_cents, ytd_debit_cents, ytd_credit_cents,
                  ending_balance_cents, balance_direction, auxiliary, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    batch_id,
                    year,
                    int(mapped["month"]),
                    account_code,
                    account_name,
                    account_level,
                    money_to_cents(mapped.get("opening_balance")),
                    money_to_cents(mapped.get("current_debit")),
                    money_to_cents(mapped.get("current_credit")),
                    money_to_cents(mapped.get("ytd_debit")),
                    money_to_cents(mapped.get("ytd_credit")),
                    money_to_cents(mapped.get("ending_balance")),
                    mapped.get("balance_direction"),
                    normalize_auxiliary(mapped.get("auxiliary")),
                    json.dumps(mapped["raw"], ensure_ascii=False),
                ),
            )

        conn.execute(
            "UPDATE import_batches SET row_count=? WHERE id=?",
            (len(mapped_rows) - len(skipped_keys), batch_id),
        )

    return {
        "company": company,
        "year": year,
        "mode": import_mode,
        "row_count": len(rows),
        "inserted_count": len(inserted_keys),
        "skipped_count": len(skipped_keys),
        "deleted_count": deleted_count,
        "duplicate_count": len(existing_keys),
    }
