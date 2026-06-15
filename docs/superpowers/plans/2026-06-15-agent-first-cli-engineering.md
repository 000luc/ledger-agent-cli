# Agent-First CLI Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ledger-agent-cli more agent-friendly with TTY-aware output formats, structured errors, config file support, skill file, audit logging, and lint/CI.

**Architecture:** Add an output abstraction layer that detects TTY and renders JSON/table/CSV; introduce config loader for default values; centralize structured error handling; add audit log file alongside the database; create a Claude Code skill file; set up ruff and GitHub Actions CI.

**Tech Stack:** Python 3.11+, Typer, SQLite, rich, tomli, ruff, pytest, GitHub Actions

---

## File Map

- **Create** `src/ledger_agent_cli/output.py`: TTY detection, format dispatch, table/CSV rendering.
- **Create** `src/ledger_agent_cli/config.py`: Load `ledger-cli.toml` with caching.
- **Create** `src/ledger_agent_cli/audit_log.py`: Append-only audit log for mutations.
- **Create** `.claude/skills/ledger-cli.skill.md`: Claude Code skill guidance.
- **Create** `.github/workflows/ci.yml`: CI workflow.
- **Create** `ledger-cli.example.toml`: Example config.
- **Create** `tests/test_output.py`: Tests for output layer.
- **Create** `tests/test_config.py`: Tests for config loader.
- **Create** `tests/test_audit_log.py`: Tests for audit logging.
- **Create** `tests/test_structured_errors.py`: Tests for structured error output.
- **Modify** `src/ledger_agent_cli/cli.py`: Use output layer, config defaults, structured errors.
- **Modify** `src/ledger_agent_cli/errors.py`: Add `CliValidationError`, `MissingFlagsError`; update `InvalidImportModeError`.
- **Modify** `src/ledger_agent_cli/importers/modes.py`: Include `valid_modes` in error details (via `InvalidImportModeError`).
- **Modify** `src/ledger_agent_cli/importers/gl.py`: Write audit log after import.
- **Modify** `src/ledger_agent_cli/importers/tb.py`: Write audit log after import.
- **Modify** `src/ledger_agent_cli/mutations/delete.py`: Write audit log after delete.
- **Modify** `pyproject.toml`: Add dependencies and ruff config.

---

### Task 1: Add ruff and format codebase

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ruff to dev dependencies**

Edit `pyproject.toml` and replace the `[project.optional-dependencies]` dev list:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "ruff>=0.5.0",
]
```

Add ruff configuration at the bottom of `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = []

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

- [ ] **Step 2: Install dev dependencies**

Run:

```powershell
python -m pip install -e .[dev]
```

Expected: installs pytest and ruff successfully.

- [ ] **Step 3: Run ruff format**

Run:

```powershell
ruff format src tests
```

Expected: reformats source files.

- [ ] **Step 4: Run ruff check and fix auto-fixable issues**

Run:

```powershell
ruff check --fix src tests
```

Expected: fixes import sorting and other auto-fixable issues.

- [ ] **Step 5: Run tests to ensure no regressions**

Run:

```powershell
python -m pytest -v
```

Expected: 47 passed.

- [ ] **Step 6: Commit**

Run:

```powershell
git add pyproject.toml src tests
git commit -m "chore: add ruff and format codebase

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Output format layer

**Files:**
- Create: `src/ledger_agent_cli/output.py`
- Modify: `src/ledger_agent_cli/cli.py`
- Create: `tests/test_output.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add rich dependency**

Edit `pyproject.toml` and add `rich` to project dependencies:

```toml
dependencies = [
  "typer>=0.12.0",
  "pandas>=2.2.0",
  "openpyxl>=3.1.0",
  "rich>=13.0.0",
]
```

Run:

```powershell
python -m pip install -e .
```

- [ ] **Step 2: Create output.py with TTY detection and format dispatch**

Create `src/ledger_agent_cli/output.py`:

```python
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
    # Errors always render as JSON for machine readability.
    typer.echo(failure(command, code, message, details, meta))
```

- [ ] **Step 3: Add Typer global callback to set format**

Edit `src/ledger_agent_cli/cli.py`:

Add import at the top:

```python
from ledger_agent_cli.output import render_error, render_result, set_format
```

Add callback after app definitions:

```python
@app.callback()
def global_options(
    format: str | None = typer.Option(None, "--format", help="Output format: json, table, csv"),
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
```

- [ ] **Step 4: Replace echo_json with render_result in cli.py**

Replace the helper function:

```python
def echo_json(payload: str) -> None:
    typer.echo(payload)
```

with:

```python
def echo_json(payload: str) -> None:
    # Kept for commands that still produce raw JSON strings.
    typer.echo(payload)
```

Then replace every `echo_json(success(...))` with `render_result(...)`, and every `echo_json(failure(...))` with `render_error(...)`.

For example, in `init` command:

```python
@app.command()
def init(db: Path = typer.Option(..., "--db", help="SQLite database path")) -> None:
    try:
        init_db(db)
        render_result("init", {"db": str(db)})
    except Exception as exc:
        exit_with_error("init", exc)
```

Do the same for `schema`, `companies`, `import_gl_command`, `import_tb_command`, `accounts_search_command`, `sql_select_command`, `variance_tb_command`, `variance_gl_command`, `trace_depreciation_command`, `reconcile_gl_tb_command`, `saved_query_add_command`, `saved_query_list_command`, `saved_query_run_command`, `delete_batch_command`, `delete_gl_command`, `delete_tb_command`.

Also update `exit_with_error`:

```python
def exit_with_error(command: str, exc: Exception) -> None:
    if isinstance(exc, LedgerCliError):
        render_error(command, exc.code, str(exc), exc.details)
    else:
        render_error(command, "error", str(exc))
    raise typer.Exit(code=1)
```

- [ ] **Step 5: Write tests for output layer**

Create `tests/test_output.py`:

```python
import json

import pytest

from ledger_agent_cli.output import get_format, is_tty, set_format


def test_get_format_defaults_to_json_when_not_tty(monkeypatch):
    set_format(None)
    monkeypatch.setattr("ledger_agent_cli.output.is_tty", lambda: False)
    assert get_format() == "json"


def test_get_format_defaults_to_table_when_tty(monkeypatch):
    set_format(None)
    monkeypatch.setattr("ledger_agent_cli.output.is_tty", lambda: True)
    assert get_format() == "table"


def test_get_format_respects_explicit_format():
    set_format("csv")
    assert get_format() == "csv"
    set_format(None)
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_output.py -v
```

Expected: 3 passed.

Run full suite:

```powershell
python -m pytest -v
```

Expected: existing tests pass plus new tests.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/ledger_agent_cli/output.py src/ledger_agent_cli/cli.py src/ledger_agent_cli/jsonio.py tests/test_output.py pyproject.toml
git commit -m "feat: add tty-aware output formats (json/table/csv)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Structured errors

**Files:**
- Modify: `src/ledger_agent_cli/errors.py`
- Modify: `src/ledger_agent_cli/cli.py`
- Modify: `src/ledger_agent_cli/importers/modes.py`
- Create: `tests/test_structured_errors.py`

- [ ] **Step 1: Add structured error types**

Edit `src/ledger_agent_cli/errors.py` and append:

```python
class CliValidationError(LedgerCliError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(code, message, details)


class MissingFlagsError(CliValidationError):
    def __init__(self, missing_flags: list[str]):
        super().__init__(
            "missing_required_flags",
            f"Missing required flags: {', '.join(missing_flags)}",
            {"missing_flags": missing_flags},
        )
```

- [ ] **Step 2: Include valid modes in InvalidImportModeError**

Edit `src/ledger_agent_cli/errors.py` and update `InvalidImportModeError`:

```python
class InvalidImportModeError(LedgerCliError):
    def __init__(self, mode: str):
        super().__init__(
            "invalid_import_mode",
            "Import mode must be one of: error, skip, replace.",
            {"mode": mode, "valid_modes": ["error", "skip", "replace"]},
        )
```

- [ ] **Step 3: Intercept Typer validation errors in cli.py**

Edit `src/ledger_agent_cli/cli.py` and add a helper function near the other helpers:

```python
def require_flags(**kwargs: Any) -> None:
    missing = [f"--{name.replace('_', '-')}" for name, value in kwargs.items() if value is None]
    if missing:
        raise MissingFlagsError(missing)
```

Then in each command, call `require_flags` at the start. For example:

```python
@import_app.command("gl")
def import_gl_command(
    db: Path = typer.Option(None, "--db"),
    file: Path = typer.Option(None, "--file"),
    company: str = typer.Option(None, "--company"),
    year: int | None = typer.Option(None, "--year"),
    mapping: Path = typer.Option(None, "--mapping"),
    mode: str = typer.Option("error", "--mode"),
) -> None:
    require_flags(db=db, file=file, company=company, year=year, mapping=mapping)
    try:
        render_result("import.gl", import_gl(db, file, company, year, mapping, mode))
    except Exception as exc:
        exit_with_error("import.gl", exc)
```

Update all commands that have required flags to use `require_flags`. Commands with no required flags (like `schema`, `companies`, `saved-query list`) do not need it.

Change all `typer.Option(..., "--db")` defaults from `...` to `None` so Typer does not block before our helper runs.

- [ ] **Step 4: Update modes.py to use InvalidImportModeError details**

`modes.py` already raises `InvalidImportModeError`, which now includes `valid_modes`.

- [ ] **Step 5: Write tests for structured errors**

Create `tests/test_structured_errors.py`:

```python
import json

from typer.testing import CliRunner

from ledger_agent_cli.cli import app


def test_missing_required_flags_returns_structured_json(runner):
    result = runner.invoke(app, ["import", "gl"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "missing_required_flags"
    assert "--db" in payload["error"]["details"]["missing_flags"]


def test_invalid_import_mode_returns_valid_modes(runner):
    result = runner.invoke(app, [
        "import", "gl",
        "--db", "ledger.db",
        "--file", "gl.csv",
        "--company", "公司A",
        "--year", "2025",
        "--mapping", "gl.json",
        "--mode", "append",
    ])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "invalid_import_mode"
    assert payload["error"]["details"]["valid_modes"] == ["error", "skip", "replace"]
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_structured_errors.py -v
```

Expected: 2 passed.

Run full suite:

```powershell
python -m pytest -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/ledger_agent_cli/errors.py src/ledger_agent_cli/cli.py src/ledger_agent_cli/importers/modes.py tests/test_structured_errors.py
git commit -m "feat: structured errors with missing flags and valid modes

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Config file support

**Files:**
- Create: `src/ledger_agent_cli/config.py`
- Modify: `src/ledger_agent_cli/cli.py`
- Create: `ledger-cli.example.toml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create config loader**

Create `src/ledger_agent_cli/config.py`:

```python
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@lru_cache
def get_config() -> dict[str, Any]:
    path = find_config_file()
    if path is None:
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def find_config_file() -> Path | None:
    candidates = ["ledger-cli.toml", ".ledger-cli.toml"]

    # 1. Current directory and ancestors up to project root
    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        for name in candidates:
            path = directory / name
            if path.exists():
                return path
        if (directory / ".git").exists():
            break

    # 2. User home directory
    home = Path.home()
    for name in candidates:
        path = home / name
        if path.exists():
            return path

    return None


def get_default(key_path: list[str], fallback: Any | None = None) -> Any:
    config = get_config()
    for key in key_path:
        if not isinstance(config, dict):
            return fallback
        config = config.get(key, {})
    return config if config != {} else fallback


def clear_config_cache() -> None:
    get_config.cache_clear()
```

Add `tomli` dependency to `pyproject.toml` for forward compatibility (Python 3.11 has tomllib, but explicit dependency does not hurt):

```toml
dependencies = [
  "typer>=0.12.0",
  "pandas>=2.2.0",
  "openpyxl>=3.1.0",
  "rich>=13.0.0",
  "tomli>=2.0.0; python_version<'3.11'",
]
```

- [ ] **Step 2: Use config defaults in cli.py**

Edit `src/ledger_agent_cli/cli.py`. Add import:

```python
from ledger_agent_cli.config import get_default
```

Define helper functions near the top:

```python
def _default_db() -> Path | None:
    value = get_default(["defaults", "db"])
    return Path(value) if value else None


def _default_company() -> str | None:
    return get_default(["defaults", "import", "company"])


def _default_year() -> int | None:
    return get_default(["defaults", "import", "year"])


def _default_format() -> str | None:
    return get_default(["defaults", "format"])
```

Update the global callback to use config default for format:

```python
@app.callback()
def global_options(
    format: str | None = typer.Option(_default_format, "--format", help="Output format: json, table, csv"),
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
```

Update required options to use config defaults. For example:

```python
@app.command()
def init(db: Path = typer.Option(_default_db, "--db", help="SQLite database path")) -> None:
    require_flags(db=db)
    try:
        init_db(db)
        render_result("init", {"db": str(db)})
    except Exception as exc:
        exit_with_error("init", exc)
```

Update `import_gl_command`:

```python
@import_app.command("gl")
def import_gl_command(
    db: Path = typer.Option(_default_db, "--db"),
    file: Path = typer.Option(None, "--file"),
    company: str | None = typer.Option(_default_company, "--company"),
    year: int | None = typer.Option(_default_year, "--year"),
    mapping: Path = typer.Option(None, "--mapping"),
    mode: str = typer.Option("error", "--mode"),
) -> None:
    require_flags(db=db, file=file, company=company, year=year, mapping=mapping)
    try:
        render_result("import.gl", import_gl(db, file, company, year, mapping, mode))
    except Exception as exc:
        exit_with_error("import.gl", exc)
```

Do the same for `import_tb_command` and other commands with required options. For commands where company/year are required, use `_default_company` and `_default_year`.

- [ ] **Step 3: Create example config file**

Create `ledger-cli.example.toml`:

```toml
[defaults]
db = "ledger.db"
format = "table"

[defaults.import]
company = "公司A"
year = 2025
```

- [ ] **Step 4: Write config tests**

Create `tests/test_config.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from ledger_agent_cli.cli import app
from ledger_agent_cli.config import clear_config_cache, find_config_file, get_config


def test_find_config_file_in_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'test.db'\n", encoding="utf-8")
    found = find_config_file()
    assert found == config_path
    clear_config_cache()


def test_config_default_db_reduces_required_flags(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'ledger.db'\n", encoding="utf-8")

    result = runner.invoke(app, ["schema"])
    clear_config_cache()

    # Without a real db this will fail, but it should NOT be a missing flag error.
    payload = json.loads(result.output)
    assert payload["error"]["code"] != "missing_required_flags"
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_config.py -v
```

Expected: 2 passed.

Run full suite:

```powershell
python -m pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/ledger_agent_cli/config.py src/ledger_agent_cli/cli.py ledger-cli.example.toml tests/test_config.py pyproject.toml
git commit -m "feat: add ledger-cli.toml config support

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Audit log

**Files:**
- Create: `src/ledger_agent_cli/audit_log.py`
- Modify: `src/ledger_agent_cli/importers/gl.py`
- Modify: `src/ledger_agent_cli/importers/tb.py`
- Modify: `src/ledger_agent_cli/mutations/delete.py`
- Create: `tests/test_audit_log.py`

- [ ] **Step 1: Create audit log module**

Create `src/ledger_agent_cli/audit_log.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _log_path(db_path: str | Path) -> Path:
    path = Path(db_path)
    return path.parent / "ledger-cli.log" if path.suffix else path / "ledger-cli.log"


def log_operation(
    db_path: str | Path,
    command: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    success: bool = True,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "arguments": _sanitize_arguments(arguments),
        "result_summary": _summarize_result(result),
        "success": success,
    }
    log_file = _log_path(db_path)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    # Avoid logging full file contents or sensitive data.
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        if key in {"file", "mapping"}:
            safe[key] = str(value)
        else:
            safe[key] = value
    return safe


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    keys = ["mode", "line_count", "row_count", "inserted_count", "skipped_count",
            "deleted_count", "duplicate_count", "deleted_lines", "deleted_headers",
            "deleted_rows", "deleted_batches", "deleted_tb_rows", "batch_id",
            "matched_headers", "matched_lines", "matched_rows", "dry_run"]
    return {k: result.get(k) for k in keys if k in result}
```

- [ ] **Step 2: Log GL imports**

Edit `src/ledger_agent_cli/importers/gl.py`. Add import:

```python
from ledger_agent_cli.audit_log import log_operation
```

At the end of `import_gl`, before the final `return`, add:

```python
        log_operation(
            db_path,
            "import.gl",
            {
                "company": company,
                "year": year,
                "file": str(source_file),
                "mapping": str(mapping_path),
                "mode": import_mode,
            },
            result,
        )
```

Where `result` is the dict being returned. So store it in a variable:

```python
    result = {
        "company": company,
        "year": year,
        "mode": import_mode,
        "line_count": len(rows),
        "inserted_count": len(inserted_keys),
        "skipped_count": len(skipped_keys),
        "deleted_count": deleted_count,
        "duplicate_count": len(existing_keys),
    }
    log_operation(
        db_path,
        "import.gl",
        {
            "company": company,
            "year": year,
            "file": str(source_file),
            "mapping": str(mapping_path),
            "mode": import_mode,
        },
        result,
    )
    return result
```

- [ ] **Step 3: Log TB imports**

Edit `src/ledger_agent_cli/importers/tb.py`. Add import:

```python
from ledger_agent_cli.audit_log import log_operation
```

At the end of `import_tb`:

```python
    result = {
        "company": company,
        "year": year,
        "mode": import_mode,
        "row_count": len(rows),
        "inserted_count": len(inserted_keys),
        "skipped_count": len(skipped_keys),
        "deleted_count": deleted_count,
        "duplicate_count": len(existing_keys),
    }
    log_operation(
        db_path,
        "import.tb",
        {
            "company": company,
            "year": year,
            "file": str(source_file),
            "mapping": str(mapping_path),
            "mode": import_mode,
        },
        result,
    )
    return result
```

- [ ] **Step 4: Log deletes**

Edit `src/ledger_agent_cli/mutations/delete.py`. Add import:

```python
from ledger_agent_cli.audit_log import log_operation
```

At the end of `delete_gl`, before `return result`:

```python
    log_operation(
        db_path,
        "delete.gl",
        {"company": company, "year": year, "month": month, "yes": yes},
        result,
    )
```

At the end of `delete_tb`:

```python
    log_operation(
        db_path,
        "delete.tb",
        {"company": company, "year": year, "month": month, "yes": yes},
        result,
    )
```

At the end of `delete_batch`:

```python
    log_operation(
        db_path,
        "delete.batch",
        {"batch_id": batch_id, "yes": yes},
        result,
    )
```

- [ ] **Step 5: Write audit log tests**

Create `tests/test_audit_log.py`:

```python
import json
from pathlib import Path

from ledger_agent_cli.audit_log import _log_path, log_operation


def test_log_path_next_to_db(tmp_path):
    db = tmp_path / "ledger.db"
    assert _log_path(db) == tmp_path / "ledger-cli.log"


def test_log_operation_appends_json_line(tmp_path):
    db = tmp_path / "ledger.db"
    log_operation(db, "import.gl", {"company": "A"}, {"inserted_count": 5})

    log_file = tmp_path / "ledger-cli.log"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["command"] == "import.gl"
    assert entry["result_summary"]["inserted_count"] == 5
    assert entry["success"] is True
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_audit_log.py -v
```

Expected: 2 passed.

Run full suite:

```powershell
python -m pytest -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/ledger_agent_cli/audit_log.py src/ledger_agent_cli/importers/gl.py src/ledger_agent_cli/importers/tb.py src/ledger_agent_cli/mutations/delete.py tests/test_audit_log.py
git commit -m "feat: add audit logging for imports and deletes

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Claude Code skill file

**Files:**
- Create: `.claude/skills/ledger-cli.skill.md`

- [ ] **Step 1: Create skill file**

Create `.claude/skills/ledger-cli.skill.md`:

```markdown
---
name: ledger-cli
description: Guidance for using ledger-agent-cli to import and query accounting ledgers safely.
---

# ledger-agent-cli Skill

Use this skill when working with the `ledger-agent-cli` project or when asked to import/query accounting data (general ledger / trial balance).

## Project Purpose

`ledger-agent-cli` is an agent-safe CLI for importing and querying accounting ledgers. It stores data in SQLite and exposes controlled commands. Agents should NOT write to the SQLite database directly; all mutations go through the CLI.

## Typical Workflow

1. Initialize database: `ledger-cli init --db ledger.db`
2. Import data:
   - GL: `ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json`
   - TB: `ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json`
3. Explore: `ledger-cli schema`, `ledger-cli companies`, `ledger-cli accounts search ...`
4. Analyze: `ledger-cli variance tb ...`, `ledger-cli variance gl ...`, `ledger-cli trace depreciation ...`, `ledger-cli reconcile gl-tb ...`
5. Save reusable queries: `ledger-cli saved-query add ...`, `ledger-cli saved-query run ...`

## Import Modes

- `error` (default): fail if target data already exists.
- `skip`: skip existing data, import only new data.
- `replace`: delete old data for the same key, then import new data.

## Delete Safety

Delete commands default to dry-run. Always run without `--yes` first to review impact, then add `--yes` to execute.

Example:

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
```

## Output Formats

- Agent calls should use `--format json` for deterministic parsing.
- Humans in a terminal get table output by default.
- Use `--format csv` to paste into Excel.

## Configuration

Check for `ledger-cli.toml` in the project root. It can set defaults like `db`, `format`, and import `company`/`year`.

## Important Constraints

- Use `ledger-cli sql select --query "SELECT ..."` for read-only exploration only. Write SQL is blocked.
- Never bypass the CLI to modify the SQLite database directly.
- Money is stored as integer cents internally; CLI output converts to yuan strings.
```

- [ ] **Step 2: Commit**

Run:

```powershell
git add .claude/skills/ledger-cli.skill.md
git commit -m "docs: add Claude Code skill file for ledger-cli

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]

      - name: Lint with ruff
        run: |
          ruff check src tests
          ruff format --check src tests

      - name: Test with pytest
        run: |
          python -m pytest -v
```

- [ ] **Step 2: Commit**

Run:

```powershell
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for ruff and pytest

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Final Verification

- [ ] Run full test suite:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] Run ruff check:

```powershell
ruff check src tests
```

Expected: no issues.

- [ ] Run ruff format check:

```powershell
ruff format --check src tests
```

Expected: no changes needed.

- [ ] Check git status:

```powershell
git status --short
```

Expected: clean working tree.

---

## Spec Coverage Self-Review

| Spec Requirement | Implementing Task |
|------------------|-------------------|
| TTY detection, default json/table | Task 2 |
| `--format json/table/csv` | Task 2 |
| Errors always JSON | Task 2 |
| Missing flags structured error | Task 3 |
| Invalid enum with valid_modes | Task 3 |
| `ledger-cli.toml` config | Task 4 |
| Skill file | Task 6 |
| ruff + CI | Task 1, Task 7 |
| Audit log | Task 5 |
| Backward compatibility | All tasks |

No placeholders found. Type and function names are consistent across tasks.
