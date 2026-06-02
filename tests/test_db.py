import sqlite3

import pytest

from ledger_agent_cli.db import connect, init_db


def table_names(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [row[0] for row in rows]


def index_names(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
    return [row[0] for row in rows]


def test_init_db_creates_required_tables(tmp_path):
    db_path = tmp_path / "ledger.db"

    init_db(db_path)

    assert table_names(db_path) == [
        "accounts",
        "companies",
        "import_batches",
        "journal_headers",
        "journal_lines",
        "saved_queries",
        "sqlite_sequence",
        "trial_balance",
    ]


def test_connect_returns_row_dicts(tmp_path):
    db_path = tmp_path / "ledger.db"
    init_db(db_path)

    with connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()

    assert row["n"] == 0


def test_init_db_creates_incremental_import_indexes(tmp_path):
    db_path = tmp_path / "ledger.db"

    init_db(db_path)

    names = index_names(db_path)
    assert "idx_journal_lines_unique_line" in names
    assert "idx_trial_balance_unique_row" in names


def test_incremental_import_indexes_reject_duplicate_rows(tmp_path):
    db_path = tmp_path / "ledger.db"
    init_db(db_path)

    with connect(db_path) as conn:
        company_id = conn.execute("INSERT INTO companies(name) VALUES ('公司A')").lastrowid
        batch_id = conn.execute(
            """
            INSERT INTO import_batches(company_id, source_type, source_file, year, mapping_json)
            VALUES (?, 'gl', 'gl.csv', 2025, '{}')
            """,
            (company_id,),
        ).lastrowid
        header_id = conn.execute(
            """
            INSERT INTO journal_headers(
              company_id, import_batch_id, year, month, voucher_date, voucher_no, raw_json
            )
            VALUES (?, ?, 2025, 1, '2025-01-31', '记-001', '{}')
            """,
            (company_id, batch_id),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO journal_lines(
              header_id, company_id, import_batch_id, year, month, voucher_date,
              voucher_no, line_no, account_code, account_name, raw_json
            )
            VALUES (?, ?, ?, 2025, 1, '2025-01-31', '记-001', 1, '660201', '差旅费', '{}')
            """,
            (header_id, company_id, batch_id),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO journal_lines(
                  header_id, company_id, import_batch_id, year, month, voucher_date,
                  voucher_no, line_no, account_code, account_name, raw_json
                )
                VALUES (?, ?, ?, 2025, 1, '2025-01-31', '记-001', 1, '100201', '银行存款', '{}')
                """,
                (header_id, company_id, batch_id),
            )

        conn.execute(
            """
            INSERT INTO trial_balance(
              company_id, import_batch_id, year, month, account_code, account_name, auxiliary, raw_json
            )
            VALUES (?, ?, 2025, 12, '660201', '差旅费', '', '{}')
            """,
            (company_id, batch_id),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO trial_balance(
                  company_id, import_batch_id, year, month, account_code, account_name, auxiliary, raw_json
                )
                VALUES (?, ?, 2025, 12, '660201', '差旅费', '', '{}')
                """,
                (company_id, batch_id),
            )
