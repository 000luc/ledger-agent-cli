from __future__ import annotations

from pathlib import Path

from ledger_agent_cli.audit_log import log_operation
from ledger_agent_cli.db import connect, transaction
from ledger_agent_cli.queries.accounts import get_company_id


def delete_gl(
    db_path: str | Path,
    company: str,
    year: int,
    month: int | None = None,
    yes: bool = False,
) -> dict:
    where = "company_id=? AND year=?"
    params: list[object] = []
    with connect(db_path) as read_conn:
        company_id = get_company_id(read_conn, company)
    params.extend([company_id, year])
    if month is not None:
        where += " AND month=?"
        params.append(month)

    with connect(db_path) as conn:
        matched_headers = conn.execute(
            f"SELECT COUNT(*) AS n FROM journal_headers WHERE {where}",
            params,
        ).fetchone()["n"]
        matched_lines = conn.execute(
            f"SELECT COUNT(*) AS n FROM journal_lines WHERE {where}",
            params,
        ).fetchone()["n"]

    result = {
        "dry_run": not yes,
        "company": company,
        "year": year,
        "month": month,
        "matched_headers": matched_headers,
        "matched_lines": matched_lines,
    }
    if not yes:
        return result

    with transaction(db_path) as conn:
        deleted_lines = conn.execute(f"DELETE FROM journal_lines WHERE {where}", params).rowcount
        deleted_headers = conn.execute(
            f"DELETE FROM journal_headers WHERE {where}", params
        ).rowcount
    result.update({"deleted_lines": deleted_lines, "deleted_headers": deleted_headers})
    log_operation(
        db_path,
        "delete.gl",
        {"company": company, "year": year, "month": month, "yes": yes},
        result,
    )
    return result


def delete_tb(
    db_path: str | Path,
    company: str,
    year: int,
    month: int | None = None,
    yes: bool = False,
) -> dict:
    where = "company_id=? AND year=?"
    params: list[object] = []
    with connect(db_path) as read_conn:
        company_id = get_company_id(read_conn, company)
    params.extend([company_id, year])
    if month is not None:
        where += " AND month=?"
        params.append(month)

    with connect(db_path) as conn:
        matched_rows = conn.execute(
            f"SELECT COUNT(*) AS n FROM trial_balance WHERE {where}",
            params,
        ).fetchone()["n"]

    result = {
        "dry_run": not yes,
        "company": company,
        "year": year,
        "month": month,
        "matched_rows": matched_rows,
    }
    if not yes:
        return result

    with transaction(db_path) as conn:
        deleted_rows = conn.execute(f"DELETE FROM trial_balance WHERE {where}", params).rowcount
    result["deleted_rows"] = deleted_rows
    log_operation(
        db_path,
        "delete.tb",
        {"company": company, "year": year, "month": month, "yes": yes},
        result,
    )
    return result


def delete_batch(db_path: str | Path, batch_id: int, yes: bool = False) -> dict:
    with connect(db_path) as conn:
        batch = conn.execute(
            "SELECT id, source_type FROM import_batches WHERE id=?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            return {"dry_run": not yes, "batch_id": batch_id, "matched_batches": 0}
        source_type = batch["source_type"]
        matched_lines = conn.execute(
            "SELECT COUNT(*) AS n FROM journal_lines WHERE import_batch_id=?",
            (batch_id,),
        ).fetchone()["n"]
        matched_tb_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM trial_balance WHERE import_batch_id=?",
            (batch_id,),
        ).fetchone()["n"]

    result = {
        "dry_run": not yes,
        "batch_id": batch_id,
        "source_type": source_type,
        "matched_batches": 1,
        "matched_lines": matched_lines,
        "matched_tb_rows": matched_tb_rows,
    }
    if not yes:
        return result

    with transaction(db_path) as conn:
        deleted_lines = conn.execute(
            "DELETE FROM journal_lines WHERE import_batch_id=?",
            (batch_id,),
        ).rowcount
        deleted_headers = conn.execute(
            "DELETE FROM journal_headers WHERE import_batch_id=?",
            (batch_id,),
        ).rowcount
        deleted_tb_rows = conn.execute(
            "DELETE FROM trial_balance WHERE import_batch_id=?",
            (batch_id,),
        ).rowcount
        deleted_batches = conn.execute(
            "DELETE FROM import_batches WHERE id=?", (batch_id,)
        ).rowcount
    result.update(
        {
            "deleted_lines": deleted_lines,
            "deleted_headers": deleted_headers,
            "deleted_tb_rows": deleted_tb_rows,
            "deleted_batches": deleted_batches,
        }
    )
    log_operation(
        db_path,
        "delete.batch",
        {"batch_id": batch_id, "yes": yes},
        result,
    )
    return result
