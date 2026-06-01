from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import init_db, transaction
from ledger_agent_cli.importers.gl import ensure_account, ensure_company


def test_init_schema_companies_commands(runner, tmp_path):
    db_path = tmp_path / "ledger.db"

    init_result = runner.invoke(app, ["init", "--db", str(db_path)])
    init_payload = parse_json(init_result)
    assert init_payload["ok"] is True
    assert init_payload["command"] == "init"
    assert db_path.exists()

    schema_result = runner.invoke(app, ["schema", "--db", str(db_path)])
    schema_payload = parse_json(schema_result)
    assert "journal_lines" in schema_payload["data"]["tables"]

    companies_result = runner.invoke(app, ["companies", "--db", str(db_path)])
    companies_payload = parse_json(companies_result)
    assert companies_payload["data"] == []


def test_accounts_search_command(runner, tmp_path):
    db_path = tmp_path / "ledger.db"
    init_db(db_path)
    with transaction(db_path) as conn:
        company_id = ensure_company(conn, "公司A")
        ensure_account(conn, company_id, 2025, "660201", "差旅费")

    result = runner.invoke(
        app,
        [
            "accounts",
            "search",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--keyword",
            "差旅",
        ],
    )
    payload = parse_json(result)

    assert payload["command"] == "accounts.search"
    assert payload["data"][0]["account_code"] == "660201"
