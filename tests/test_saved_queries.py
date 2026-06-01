from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import init_db


def test_saved_query_add_list_run(runner, tmp_path):
    db_path = tmp_path / "ledger.db"
    init_db(db_path)

    add_result = runner.invoke(
        app,
        [
            "saved-query",
            "add",
            "--db",
            str(db_path),
            "--name",
            "list-companies",
            "--description",
            "List companies",
            "--query",
            "SELECT name FROM companies",
        ],
    )
    assert parse_json(add_result)["ok"] is True

    list_result = runner.invoke(app, ["saved-query", "list", "--db", str(db_path)])
    list_payload = parse_json(list_result)
    assert list_payload["data"][0]["name"] == "list-companies"

    run_result = runner.invoke(
        app,
        ["saved-query", "run", "--db", str(db_path), "--name", "list-companies"],
    )
    run_payload = parse_json(run_result)
    assert run_payload["command"] == "saved-query.run"


def test_saved_query_supports_named_parameters(runner, tmp_path):
    db_path = tmp_path / "ledger.db"
    init_db(db_path)

    add_result = runner.invoke(
        app,
        [
            "saved-query",
            "add",
            "--db",
            str(db_path),
            "--name",
            "echo-year",
            "--description",
            "Echo a year parameter",
            "--query",
            "SELECT :year AS year",
            "--parameter",
            "year",
        ],
    )
    add_payload = parse_json(add_result)
    assert add_payload["data"]["parameters"] == ["year"]

    run_result = runner.invoke(
        app,
        [
            "saved-query",
            "run",
            "--db",
            str(db_path),
            "--name",
            "echo-year",
            "--value",
            "year=2025",
        ],
    )
    run_payload = parse_json(run_result)
    assert run_payload["data"]["rows"][0]["year"] == "2025"
