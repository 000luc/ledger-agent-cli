from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import typer

from ledger_agent_cli.db import connect, init_db
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.importers.tb import import_tb
from ledger_agent_cli.jsonio import failure, success
from ledger_agent_cli.queries.accounts import search_accounts
from ledger_agent_cli.queries.reconcile import reconcile_gl_tb
from ledger_agent_cli.queries.saved import add_saved_query, list_saved_queries, run_saved_query
from ledger_agent_cli.queries.trace import trace_depreciation
from ledger_agent_cli.queries.variance import gl_variance, tb_variance
from ledger_agent_cli.sql_guard import assert_read_only_select

app = typer.Typer(no_args_is_help=True)
import_app = typer.Typer(no_args_is_help=True)
accounts_app = typer.Typer(no_args_is_help=True)
sql_app = typer.Typer(no_args_is_help=True)
variance_app = typer.Typer(no_args_is_help=True)
trace_app = typer.Typer(no_args_is_help=True)
reconcile_app = typer.Typer(no_args_is_help=True)
saved_query_app = typer.Typer(no_args_is_help=True)

app.add_typer(import_app, name="import")
app.add_typer(accounts_app, name="accounts")
app.add_typer(sql_app, name="sql")
app.add_typer(variance_app, name="variance")
app.add_typer(trace_app, name="trace")
app.add_typer(reconcile_app, name="reconcile")
app.add_typer(saved_query_app, name="saved-query")


def echo_json(payload: str) -> None:
    typer.echo(payload)


def parse_key_values(items: list[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError("--value must use key=value format")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--value key cannot be empty")
        parsed[key] = value
    return parsed


def exit_with_error(command: str, exc: Exception) -> None:
    echo_json(failure(command, "error", str(exc)))
    raise typer.Exit(code=1)


@app.command()
def init(db: Path = typer.Option(..., "--db", help="SQLite database path")) -> None:
    try:
        init_db(db)
        echo_json(success("init", {"db": str(db)}))
    except Exception as exc:
        exit_with_error("init", exc)


@app.command()
def schema(db: Path = typer.Option(..., "--db", help="SQLite database path")) -> None:
    try:
        with connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        echo_json(success("schema", {"tables": [row["name"] for row in rows]}))
    except sqlite3.Error as exc:
        echo_json(failure("schema", "sqlite_error", str(exc)))
        raise typer.Exit(code=1)


@app.command()
def companies(db: Path = typer.Option(..., "--db", help="SQLite database path")) -> None:
    try:
        with connect(db) as conn:
            rows = conn.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
        echo_json(success("companies", [dict(row) for row in rows], {"count": len(rows)}))
    except Exception as exc:
        exit_with_error("companies", exc)


@import_app.command("gl")
def import_gl_command(
    db: Path = typer.Option(..., "--db"),
    file: Path = typer.Option(..., "--file"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    mapping: Path = typer.Option(..., "--mapping"),
) -> None:
    try:
        echo_json(success("import.gl", import_gl(db, file, company, year, mapping)))
    except Exception as exc:
        exit_with_error("import.gl", exc)


@import_app.command("tb")
def import_tb_command(
    db: Path = typer.Option(..., "--db"),
    file: Path = typer.Option(..., "--file"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    mapping: Path = typer.Option(..., "--mapping"),
) -> None:
    try:
        echo_json(success("import.tb", import_tb(db, file, company, year, mapping)))
    except Exception as exc:
        exit_with_error("import.tb", exc)


@accounts_app.command("search")
def accounts_search_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    keyword: str = typer.Option(..., "--keyword"),
) -> None:
    try:
        data = search_accounts(db, company, year, keyword)
        echo_json(success("accounts.search", data, {"count": len(data)}))
    except Exception as exc:
        exit_with_error("accounts.search", exc)


@sql_app.command("select")
def sql_select_command(
    db: Path = typer.Option(..., "--db"),
    query: str = typer.Option(..., "--query"),
    limit: int = typer.Option(200, "--limit"),
) -> None:
    command = "sql.select"
    try:
        assert_read_only_select(query)
        safe_limit = min(max(limit, 1), 1000)
        wrapped = f"SELECT * FROM ({query.rstrip(';')}) LIMIT ?"
        with connect(db) as conn:
            rows = conn.execute(wrapped, (safe_limit,)).fetchall()
        echo_json(
            success(
                command,
                {"rows": [dict(row) for row in rows]},
                {"returned": len(rows), "limit": safe_limit},
            )
        )
    except Exception as exc:
        echo_json(failure(command, "sql_error", str(exc)))
        raise typer.Exit(code=1)


@variance_app.command("tb")
def variance_tb_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    compare_year: int = typer.Option(..., "--compare-year"),
    account: str = typer.Option(..., "--account"),
) -> None:
    try:
        echo_json(success("variance.tb", tb_variance(db, company, year, compare_year, account)))
    except Exception as exc:
        exit_with_error("variance.tb", exc)


@variance_app.command("gl")
def variance_gl_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    compare_year: int = typer.Option(..., "--compare-year"),
    account: str = typer.Option(..., "--account"),
) -> None:
    try:
        echo_json(success("variance.gl", gl_variance(db, company, year, compare_year, account)))
    except Exception as exc:
        exit_with_error("variance.gl", exc)


@trace_app.command("depreciation")
def trace_depreciation_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
) -> None:
    try:
        echo_json(success("trace.depreciation", trace_depreciation(db, company, year)))
    except Exception as exc:
        exit_with_error("trace.depreciation", exc)


@reconcile_app.command("gl-tb")
def reconcile_gl_tb_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
) -> None:
    try:
        echo_json(success("reconcile.gl-tb", reconcile_gl_tb(db, company, year)))
    except Exception as exc:
        exit_with_error("reconcile.gl-tb", exc)


@saved_query_app.command("add")
def saved_query_add_command(
    db: Path = typer.Option(..., "--db"),
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option(..., "--description"),
    query: str = typer.Option(..., "--query"),
    parameter: list[str] = typer.Option(None, "--parameter"),
) -> None:
    try:
        echo_json(success("saved-query.add", add_saved_query(db, name, description, query, parameter)))
    except Exception as exc:
        exit_with_error("saved-query.add", exc)


@saved_query_app.command("list")
def saved_query_list_command(db: Path = typer.Option(..., "--db")) -> None:
    try:
        data = list_saved_queries(db)
        echo_json(success("saved-query.list", data, {"count": len(data)}))
    except Exception as exc:
        exit_with_error("saved-query.list", exc)


@saved_query_app.command("run")
def saved_query_run_command(
    db: Path = typer.Option(..., "--db"),
    name: str = typer.Option(..., "--name"),
    values: str = typer.Option("{}", "--values", help="JSON object for named SQL parameters"),
    value: list[str] = typer.Option(None, "--value", help="Named SQL parameter as key=value"),
    limit: int = typer.Option(200, "--limit"),
) -> None:
    try:
        parsed_values = json.loads(values)
        if not isinstance(parsed_values, dict):
            raise ValueError("--values must be a JSON object")
        parsed_values.update(parse_key_values(value))
        echo_json(success("saved-query.run", run_saved_query(db, name, parsed_values, limit)))
    except Exception as exc:
        exit_with_error("saved-query.run", exc)
