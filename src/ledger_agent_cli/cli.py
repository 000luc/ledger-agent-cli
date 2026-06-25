from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from ledger_agent_cli.config import get_default
from ledger_agent_cli.db import connect, init_db
from ledger_agent_cli.errors import LedgerCliError, MissingFlagsError
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.importers.tb import import_tb
from ledger_agent_cli.mutations.delete import delete_batch, delete_gl, delete_tb
from ledger_agent_cli.output import render_error, render_result, set_format
from ledger_agent_cli.queries.accounts import search_accounts
from ledger_agent_cli.queries.reconcile import reconcile_gl_tb
from ledger_agent_cli.queries.saved import add_saved_query, list_saved_queries, run_saved_query
from ledger_agent_cli.queries.trace import trace_depreciation
from ledger_agent_cli.queries.variance import gl_variance, tb_variance
from ledger_agent_cli.sql_guard import assert_read_only_select

try:
    from ledger_agent_cli.chat.engine import ChatEngine

    _chat_available = True
except ImportError:
    _chat_available = False

app = typer.Typer(no_args_is_help=True)
import_app = typer.Typer(no_args_is_help=True)
accounts_app = typer.Typer(no_args_is_help=True)
sql_app = typer.Typer(no_args_is_help=True)
variance_app = typer.Typer(no_args_is_help=True)
trace_app = typer.Typer(no_args_is_help=True)
reconcile_app = typer.Typer(no_args_is_help=True)
saved_query_app = typer.Typer(no_args_is_help=True)
delete_app = typer.Typer(no_args_is_help=True)

app.add_typer(import_app, name="import")
app.add_typer(accounts_app, name="accounts")
app.add_typer(sql_app, name="sql")
app.add_typer(variance_app, name="variance")
app.add_typer(trace_app, name="trace")
app.add_typer(reconcile_app, name="reconcile")
app.add_typer(saved_query_app, name="saved-query")
app.add_typer(delete_app, name="delete")


def _default_db() -> Path | None:
    value = get_default(["defaults", "db"])
    return Path(value) if value else None


def _default_company() -> str | None:
    return get_default(["defaults", "import", "company"])


def _default_year() -> int | None:
    return get_default(["defaults", "import", "year"])


def _default_format() -> str | None:
    return get_default(["defaults", "format"])


@app.callback()
def global_options(
    format: str | None = typer.Option(
        _default_format, "--format", help="Output format: json, table, csv"
    ),
) -> None:
    if format is not None and format not in {"json", "table", "csv"}:
        render_error(
            "global",
            "invalid_format",
            "Output format must be one of: json, table, csv.",
            {"format": format, "valid_formats": ["json", "table", "csv"]},
        )
        raise typer.Exit(code=1)
    set_format(format)


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


def require_flags(**kwargs: Any) -> None:
    missing = [f"--{name.replace('_', '-')}" for name, value in kwargs.items() if value is None]
    if missing:
        raise MissingFlagsError(missing)


def exit_with_error(command: str, exc: Exception) -> None:
    if isinstance(exc, LedgerCliError):
        render_error(command, exc.code, str(exc), exc.details)
    else:
        render_error(command, "error", str(exc))
    raise typer.Exit(code=1)


@app.command()
def init(db: Path = typer.Option(_default_db, "--db", help="SQLite database path")) -> None:
    try:
        require_flags(db=db)
        init_db(db)
        render_result("init", {"db": str(db)})
    except Exception as exc:
        exit_with_error("init", exc)


@app.command()
def schema(db: Path = typer.Option(_default_db, "--db", help="SQLite database path")) -> None:
    try:
        require_flags(db=db)
        with connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        render_result("schema", {"tables": [row["name"] for row in rows]})
    except Exception as exc:
        exit_with_error("schema", exc)


@app.command()
def companies(db: Path = typer.Option(_default_db, "--db", help="SQLite database path")) -> None:
    try:
        require_flags(db=db)
        with connect(db) as conn:
            rows = conn.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
        render_result("companies", [dict(row) for row in rows], {"count": len(rows)})
    except Exception as exc:
        exit_with_error("companies", exc)


@import_app.command("gl")
def import_gl_command(
    db: Path = typer.Option(_default_db, "--db"),
    file: Path = typer.Option(None, "--file"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    mapping: Path = typer.Option(None, "--mapping"),
    mode: str = typer.Option("error", "--mode"),
) -> None:
    try:
        require_flags(db=db, file=file, company=company, year=year, mapping=mapping)
        render_result("import.gl", import_gl(db, file, company, year, mapping, mode))
    except Exception as exc:
        exit_with_error("import.gl", exc)


@import_app.command("tb")
def import_tb_command(
    db: Path = typer.Option(_default_db, "--db"),
    file: Path = typer.Option(None, "--file"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    mapping: Path = typer.Option(None, "--mapping"),
    mode: str = typer.Option("error", "--mode"),
) -> None:
    try:
        require_flags(db=db, file=file, company=company, year=year, mapping=mapping)
        render_result("import.tb", import_tb(db, file, company, year, mapping, mode))
    except Exception as exc:
        exit_with_error("import.tb", exc)


@accounts_app.command("search")
def accounts_search_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    keyword: str = typer.Option(None, "--keyword"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year, keyword=keyword)
        data = search_accounts(db, company, year, keyword)
        render_result("accounts.search", data, {"count": len(data)})
    except Exception as exc:
        exit_with_error("accounts.search", exc)


@sql_app.command("select")
def sql_select_command(
    db: Path = typer.Option(_default_db, "--db"),
    query: str = typer.Option(None, "--query"),
    limit: int = typer.Option(200, "--limit"),
) -> None:
    command = "sql.select"
    try:
        require_flags(db=db, query=query)
        assert_read_only_select(query)
        safe_limit = min(max(limit, 1), 1000)
        wrapped = f"SELECT * FROM ({query.rstrip(';')}) LIMIT ?"
        with connect(db) as conn:
            rows = conn.execute(wrapped, (safe_limit,)).fetchall()
        render_result(
            command,
            {"rows": [dict(row) for row in rows]},
            {"returned": len(rows), "limit": safe_limit},
        )
    except Exception as exc:
        exit_with_error(command, exc)


@variance_app.command("tb")
def variance_tb_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    compare_year: int = typer.Option(None, "--compare-year"),
    account: str = typer.Option(None, "--account"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year, compare_year=compare_year, account=account)
        render_result("variance.tb", tb_variance(db, company, year, compare_year, account))
    except Exception as exc:
        exit_with_error("variance.tb", exc)


@variance_app.command("gl")
def variance_gl_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    compare_year: int = typer.Option(None, "--compare-year"),
    account: str = typer.Option(None, "--account"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year, compare_year=compare_year, account=account)
        render_result("variance.gl", gl_variance(db, company, year, compare_year, account))
    except Exception as exc:
        exit_with_error("variance.gl", exc)


@trace_app.command("depreciation")
def trace_depreciation_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year)
        render_result("trace.depreciation", trace_depreciation(db, company, year))
    except Exception as exc:
        exit_with_error("trace.depreciation", exc)


@reconcile_app.command("gl-tb")
def reconcile_gl_tb_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year)
        render_result("reconcile.gl-tb", reconcile_gl_tb(db, company, year))
    except Exception as exc:
        exit_with_error("reconcile.gl-tb", exc)


@saved_query_app.command("add")
def saved_query_add_command(
    db: Path = typer.Option(_default_db, "--db"),
    name: str = typer.Option(None, "--name"),
    description: str = typer.Option(None, "--description"),
    query: str = typer.Option(None, "--query"),
    parameter: list[str] = typer.Option(None, "--parameter"),
) -> None:
    try:
        require_flags(db=db, name=name, description=description, query=query)
        render_result("saved-query.add", add_saved_query(db, name, description, query, parameter))
    except Exception as exc:
        exit_with_error("saved-query.add", exc)


@saved_query_app.command("list")
def saved_query_list_command(db: Path = typer.Option(_default_db, "--db")) -> None:
    try:
        require_flags(db=db)
        data = list_saved_queries(db)
        render_result("saved-query.list", data, {"count": len(data)})
    except Exception as exc:
        exit_with_error("saved-query.list", exc)


@saved_query_app.command("run")
def saved_query_run_command(
    db: Path = typer.Option(_default_db, "--db"),
    name: str = typer.Option(None, "--name"),
    values: str = typer.Option("{}", "--values", help="JSON object for named SQL parameters"),
    value: list[str] = typer.Option(None, "--value", help="Named SQL parameter as key=value"),
    limit: int = typer.Option(200, "--limit"),
) -> None:
    try:
        require_flags(db=db, name=name)
        parsed_values = json.loads(values)
        if not isinstance(parsed_values, dict):
            raise ValueError("--values must be a JSON object")
        parsed_values.update(parse_key_values(value))
        render_result("saved-query.run", run_saved_query(db, name, parsed_values, limit))
    except Exception as exc:
        exit_with_error("saved-query.run", exc)


@delete_app.command("batch")
def delete_batch_command(
    db: Path = typer.Option(_default_db, "--db"),
    batch_id: int = typer.Option(None, "--batch-id"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        require_flags(db=db, batch_id=batch_id)
        render_result("delete.batch", delete_batch(db, batch_id, yes))
    except Exception as exc:
        exit_with_error("delete.batch", exc)


@delete_app.command("gl")
def delete_gl_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    month: int | None = typer.Option(None, "--month"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year)
        render_result("delete.gl", delete_gl(db, company, year, month, yes))
    except Exception as exc:
        exit_with_error("delete.gl", exc)


@delete_app.command("tb")
def delete_tb_command(
    db: Path = typer.Option(_default_db, "--db"),
    company: str = typer.Option(_default_company, "--company"),
    year: int = typer.Option(_default_year, "--year"),
    month: int | None = typer.Option(None, "--month"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        require_flags(db=db, company=company, year=year)
        render_result("delete.tb", delete_tb(db, company, year, month, yes))
    except Exception as exc:
        exit_with_error("delete.tb", exc)


@app.command()
def chat(
    db: Path = typer.Option(_default_db, "--db", help="SQLite database path"),
    api_key: str = typer.Option(
        None,
        "--api-key",
        envvar="DEEPSEEK_API_KEY",
        help="DeepSeek API key, 默认从 DEEPSEEK_API_KEY 环境变量读取",
    ),
    model: str = typer.Option(
        "deepseek-chat", "--model", help="DeepSeek 模型名称"
    ),
) -> None:
    """启动交互式财务问答会话。"""
    try:
        if not api_key:
            render_error(
                "chat",
                "missing_api_key",
                "请设置 DEEPSEEK_API_KEY 环境变量或通过 --api-key 传入。",
            )
            raise typer.Exit(code=1)
        require_flags(db=db)
        if not _chat_available:
            render_error(
                "chat",
                "missing_dependency",
                "缺少 openai 包，请执行: python -m pip install openai",
            )
            raise typer.Exit(code=1)

        engine = ChatEngine(db, api_key, model)

        if engine.is_empty():
            typer.echo("提示：数据库中暂无数据，请先用 import 命令导入序时账和科目余额表。")

        typer.echo(
            f"账簿查询助手已启动（模型：{model}），输入 exit 退出。"
        )
        while True:
            try:
                user_input = input(">>> ")
            except (EOFError, KeyboardInterrupt):
                typer.echo("")
                break
            if user_input.strip().lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue
            try:
                response = engine.chat(user_input.strip())
                typer.echo(response)
            except Exception as exc:
                render_error("chat", "chat_error", str(exc))
    except typer.Exit:
        raise
    except Exception as exc:
        exit_with_error("chat", exc)
