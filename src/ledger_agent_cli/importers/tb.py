from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledger_agent_cli.db import transaction
from ledger_agent_cli.importers.common import apply_mapping, load_mapping, money_to_cents, read_rows
from ledger_agent_cli.importers.gl import create_batch, ensure_account, ensure_company

REQUIRED_TB_FIELDS = ["month", "account_code", "account_name"]


def import_tb(
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
        batch_id = create_batch(conn, company_id, "tb", source_file, year, mapping)

        for row in rows:
            mapped = apply_mapping(row, mapping, REQUIRED_TB_FIELDS)
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
                    mapped.get("auxiliary"),
                    json.dumps(mapped["raw"], ensure_ascii=False),
                ),
            )

        conn.execute("UPDATE import_batches SET row_count=? WHERE id=?", (len(rows), batch_id))

    return {"company": company, "year": year, "row_count": len(rows)}
