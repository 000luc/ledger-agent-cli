import sqlite3

from ledger_agent_cli.db import connect, init_db


def table_names(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
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
