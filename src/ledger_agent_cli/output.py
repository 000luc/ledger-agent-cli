from __future__ import annotations

import csv
import io
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ledger_agent_cli.jsonio import failure, success

_output_format: str | None = None


def set_format(fmt: str | None) -> None:
    global _output_format
    _output_format = fmt


def is_tty() -> bool:
    return sys.stdout.isatty()


def get_format() -> str:
    if _output_format is not None:
        return _output_format
    return "table" if is_tty() else "json"


def _flatten_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        if "rows" in data and isinstance(data["rows"], list):
            return data["rows"]
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
    if isinstance(data, list):
        return data
    return []


def _render_table(command: str, data: Any, meta: dict[str, Any] | None) -> None:
    rows = _flatten_rows(data)
    if not rows:
        typer.echo(str(data))
        return

    table = Table(title=f"Command: {command}")
    keys = list(rows[0].keys())
    for key in keys:
        table.add_column(str(key))
    for row in rows:
        table.add_row(*(str(row.get(k, "")) for k in keys))

    console = Console()
    console.print(table)
    if meta:
        typer.echo(f"Meta: {meta}")


def _render_csv(data: Any) -> None:
    rows = _flatten_rows(data)
    if not rows:
        typer.echo("")
        return

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    typer.echo(output.getvalue().rstrip("\n"))


def render_result(
    command: str,
    data: Any,
    meta: dict[str, Any] | None = None,
) -> None:
    fmt = get_format()
    if fmt == "json":
        typer.echo(success(command, data, meta))
    elif fmt == "csv":
        _render_csv(data)
    else:
        _render_table(command, data, meta)


def render_error(
    command: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    typer.echo(failure(command, code, message, details, meta))
