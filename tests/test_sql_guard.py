import pytest

from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import init_db
from ledger_agent_cli.sql_guard import assert_read_only_select


def test_allows_select_and_with_queries():
    assert_read_only_select("SELECT * FROM accounts")
    assert_read_only_select("WITH x AS (SELECT 1 AS n) SELECT n FROM x")


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM accounts",
        "UPDATE accounts SET account_name='x'",
        "INSERT INTO accounts(account_code) VALUES ('1')",
        "DROP TABLE accounts",
        "PRAGMA table_info(accounts)",
        "ATTACH DATABASE 'x.db' AS x",
    ],
)
def test_rejects_write_or_admin_sql(query):
    with pytest.raises(ValueError):
        assert_read_only_select(query)


def test_sql_select_cli_returns_rows(runner, tmp_path):
    db_path = tmp_path / "ledger.db"
    init_db(db_path)

    result = runner.invoke(
        app,
        ["sql", "select", "--db", str(db_path), "--query", "SELECT name FROM sqlite_master"],
    )

    payload = parse_json(result)
    assert payload["ok"] is True
    assert payload["command"] == "sql.select"
    assert payload["meta"]["returned"] > 0
