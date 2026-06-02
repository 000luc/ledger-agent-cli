# Incremental Import And Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe incremental import, replacement, and deletion controls so GL/TB data cannot be duplicated silently and mistaken imports can be removed through JSON CLI commands.

**Architecture:** Importers will scan input rows first, detect the target scope, and apply one explicit mode: `error`, `skip`, or `replace`. Deletion logic lives in a focused mutation module used by both import replacement and `ledger-cli delete ...` commands. Database uniqueness is reinforced with indexes while CLI-level duplicate checks produce readable JSON errors before SQLite constraint failures.

**Tech Stack:** Python 3.11+, Typer, SQLite, pytest, existing `ledger_agent_cli` package.

---

## File Map

- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\schema.sql`
  Add unique indexes for GL line identity and TB row identity.
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\errors.py`
  Define CLI-safe exception types with error codes and details.
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\mutations\__init__.py`
  Package marker.
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\mutations\delete.py`
  Delete and dry-run helpers for batch, GL, and TB.
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\modes.py`
  Import mode validation, duplicate-scope helpers, and shared result counters.
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\gl.py`
  Add `mode`, duplicate detection, skip, and replace behavior.
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\tb.py`
  Add `mode`, duplicate detection, skip, and replace behavior.
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`
  Add `--mode` to import commands and add `delete` command group.
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\README.md`
  Document safe import modes and delete commands.
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\docs\cli-commands.md`
  Document `--mode`, `delete batch`, `delete gl`, `delete tb`.
- Test: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`
  New tests for GL/TB duplicate mode behavior.
- Test: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_delete_commands.py`
  New tests for dry-run and real deletion.
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_db.py`
  Verify unique indexes exist.

---

### Task 1: Error Types And Unique Indexes

**Files:**
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\errors.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\schema.sql`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_db.py`

- [ ] **Step 1: Add failing tests for unique indexes**

Append to `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_db.py`:

```python
def index_names(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
    return [row[0] for row in rows]


def test_init_db_creates_incremental_import_indexes(tmp_path):
    db_path = tmp_path / "ledger.db"

    init_db(db_path)

    names = index_names(db_path)
    assert "idx_journal_lines_unique_line" in names
    assert "idx_trial_balance_unique_row" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests\test_db.py::test_init_db_creates_incremental_import_indexes -v
```

Expected: FAIL because the two index names do not exist.

- [ ] **Step 3: Add unique indexes to schema**

Append to `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\schema.sql`:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_lines_unique_line
  ON journal_lines(company_id, year, month, voucher_no, line_no);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_balance_unique_row
  ON trial_balance(company_id, year, month, account_code, COALESCE(auxiliary, ''));
```

- [ ] **Step 4: Create CLI-safe error types**

Create `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\errors.py`:

```python
from __future__ import annotations

from typing import Any


class LedgerCliError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class DuplicateImportScopeError(LedgerCliError):
    def __init__(self, duplicate_count: int):
        super().__init__(
            "duplicate_import_scope",
            "Target data already exists. Use --mode replace to overwrite or --mode skip to ignore.",
            {"duplicate_count": duplicate_count},
        )


class InvalidImportModeError(LedgerCliError):
    def __init__(self, mode: str):
        super().__init__(
            "invalid_import_mode",
            "Import mode must be one of: error, skip, replace.",
            {"mode": mode},
        )
```

- [ ] **Step 5: Teach CLI error output to preserve custom codes**

Modify `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`.

Add import:

```python
from ledger_agent_cli.errors import LedgerCliError
```

Replace `exit_with_error` with:

```python
def exit_with_error(command: str, exc: Exception) -> None:
    if isinstance(exc, LedgerCliError):
        echo_json(failure(command, exc.code, str(exc), exc.details))
    else:
        echo_json(failure(command, "error", str(exc)))
    raise typer.Exit(code=1)
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests\test_db.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src\ledger_agent_cli\errors.py src\ledger_agent_cli\schema.sql src\ledger_agent_cli\cli.py tests\test_db.py
git commit -m "feat: add import safety indexes and errors"
```

Expected: commit succeeds.

---

### Task 2: Shared Import Mode Helpers

**Files:**
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\modes.py`
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`

- [ ] **Step 1: Create failing tests for mode validation and row keys**

Create `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`:

```python
import pytest

from ledger_agent_cli.errors import InvalidImportModeError
from ledger_agent_cli.importers.modes import (
    gl_scope_key,
    normalize_auxiliary,
    tb_scope_key,
    validate_import_mode,
)


def test_validate_import_mode_accepts_supported_modes():
    assert validate_import_mode("error") == "error"
    assert validate_import_mode("skip") == "skip"
    assert validate_import_mode("replace") == "replace"


def test_validate_import_mode_rejects_unknown_mode():
    with pytest.raises(InvalidImportModeError):
        validate_import_mode("append")


def test_gl_scope_key_uses_month_and_voucher_no():
    mapped = {"month": "1", "voucher_no": "记-001"}

    assert gl_scope_key(mapped) == (1, "记-001")


def test_tb_scope_key_uses_empty_string_for_blank_auxiliary():
    mapped = {"month": "12", "account_code": "660201", "auxiliary": ""}

    assert tb_scope_key(mapped) == (12, "660201", "")
    assert normalize_auxiliary(None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests\test_import_modes.py -v
```

Expected: FAIL because `ledger_agent_cli.importers.modes` does not exist.

- [ ] **Step 3: Implement import mode helpers**

Create `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\modes.py`:

```python
from __future__ import annotations

from typing import Literal

from ledger_agent_cli.errors import InvalidImportModeError

ImportMode = Literal["error", "skip", "replace"]
VALID_IMPORT_MODES = {"error", "skip", "replace"}


def validate_import_mode(mode: str) -> ImportMode:
    if mode not in VALID_IMPORT_MODES:
        raise InvalidImportModeError(mode)
    return mode  # type: ignore[return-value]


def normalize_auxiliary(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def gl_scope_key(mapped: dict) -> tuple[int, str]:
    return int(mapped["month"]), str(mapped["voucher_no"]).strip()


def tb_scope_key(mapped: dict) -> tuple[int, str, str]:
    return (
        int(mapped["month"]),
        str(mapped["account_code"]).strip(),
        normalize_auxiliary(mapped.get("auxiliary")),
    )
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests\test_import_modes.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src\ledger_agent_cli\importers\modes.py tests\test_import_modes.py
git commit -m "feat: add import mode helpers"
```

Expected: commit succeeds.

---

### Task 3: GL Duplicate Detection, Skip, And Replace

**Files:**
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\gl.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`

- [ ] **Step 1: Add failing GL import mode tests**

Append to `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`:

```python
import json

from typer.testing import CliRunner

from ledger_agent_cli.cli import app
from ledger_agent_cli.db import connect, init_db
from ledger_agent_cli.importers.gl import import_gl


GL_MAPPING = {
    "month": "月份",
    "voucher_date": "凭证日期",
    "voucher_no": "凭证字号",
    "line_no": "行号",
    "summary": "摘要",
    "account_code": "科目编码",
    "account_name": "科目名称",
    "debit": "借方金额",
    "credit": "贷方金额",
}


def write_gl_file(path, amount):
    path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额\n"
        f"1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,{amount},0\n"
        f"1,2025/01/31,记-001,2,报销差旅费,100201,银行存款,0,{amount}\n",
        encoding="utf-8",
    )


def write_mapping(path, mapping):
    path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")


def gl_line_count(db_path):
    with connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM journal_lines").fetchone()["n"]


def gl_debit_total(db_path):
    with connect(db_path) as conn:
        return conn.execute("SELECT SUM(debit_cents) AS n FROM journal_lines").fetchone()["n"]


def test_gl_duplicate_import_defaults_to_error(tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    map_path = tmp_path / "gl.json"
    init_db(db_path)
    write_gl_file(gl_path, 1200)
    write_mapping(map_path, GL_MAPPING)
    import_gl(db_path, gl_path, "公司A", 2025, map_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["import", "gl", "--db", str(db_path), "--file", str(gl_path), "--company", "公司A", "--year", "2025", "--mapping", str(map_path)],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "duplicate_import_scope"
    assert gl_line_count(db_path) == 2


def test_gl_skip_mode_does_not_duplicate_existing_voucher(tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    map_path = tmp_path / "gl.json"
    init_db(db_path)
    write_gl_file(gl_path, 1200)
    write_mapping(map_path, GL_MAPPING)
    import_gl(db_path, gl_path, "公司A", 2025, map_path)

    result = import_gl(db_path, gl_path, "公司A", 2025, map_path, mode="skip")

    assert result["inserted_count"] == 0
    assert result["skipped_count"] == 1
    assert gl_line_count(db_path) == 2


def test_gl_replace_mode_replaces_existing_voucher(tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    replacement_path = tmp_path / "gl_replacement.csv"
    map_path = tmp_path / "gl.json"
    init_db(db_path)
    write_gl_file(gl_path, 1200)
    write_gl_file(replacement_path, 1500)
    write_mapping(map_path, GL_MAPPING)
    import_gl(db_path, gl_path, "公司A", 2025, map_path)

    result = import_gl(db_path, replacement_path, "公司A", 2025, map_path, mode="replace")

    assert result["deleted_count"] == 1
    assert result["inserted_count"] == 1
    assert gl_line_count(db_path) == 2
    assert gl_debit_total(db_path) == 150000
```

- [ ] **Step 2: Run GL mode tests to verify they fail**

Run:

```powershell
python -m pytest tests\test_import_modes.py::test_gl_duplicate_import_defaults_to_error tests\test_import_modes.py::test_gl_skip_mode_does_not_duplicate_existing_voucher tests\test_import_modes.py::test_gl_replace_mode_replaces_existing_voucher -v
```

Expected: FAIL because `import_gl` has no `mode` parameter and CLI has no `--mode`.

- [ ] **Step 3: Update `import_gl` signature and duplicate pre-scan**

Modify `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\gl.py`.

Add imports:

```python
from ledger_agent_cli.errors import DuplicateImportScopeError
from ledger_agent_cli.importers.modes import gl_scope_key, validate_import_mode
```

Change signature:

```python
def import_gl(
    db_path: str | Path,
    file_path: str | Path,
    company: str,
    year: int,
    mapping_path: str | Path,
    mode: str = "error",
) -> dict[str, Any]:
```

After loading rows, add:

```python
    import_mode = validate_import_mode(mode)
    mapped_rows = [apply_mapping(row, mapping, REQUIRED_GL_FIELDS) for row in rows]
    target_keys = sorted(set(gl_scope_key(mapped) for mapped in mapped_rows))
```

Inside the transaction, immediately after `company_id = ensure_company(...)`, add:

```python
        existing_keys = set()
        for month, voucher_no in target_keys:
            row = conn.execute(
                """
                SELECT id FROM journal_headers
                WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                """,
                (company_id, year, month, voucher_no),
            ).fetchone()
            if row is not None:
                existing_keys.add((month, voucher_no))

        if existing_keys and import_mode == "error":
            raise DuplicateImportScopeError(len(existing_keys))

        deleted_count = 0
        if existing_keys and import_mode == "replace":
            for month, voucher_no in existing_keys:
                deleted = conn.execute(
                    """
                    DELETE FROM journal_lines
                    WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                    """,
                    (company_id, year, month, voucher_no),
                ).rowcount
                conn.execute(
                    """
                    DELETE FROM journal_headers
                    WHERE company_id=? AND year=? AND month=? AND voucher_no=?
                    """,
                    (company_id, year, month, voucher_no),
                )
                deleted_count += 1 if deleted else 0
```

- [ ] **Step 4: Change GL import loop to use pre-mapped rows and skip mode**

In `import_gl`, replace:

```python
        for index, row in enumerate(rows, start=1):
            mapped = apply_mapping(row, mapping, REQUIRED_GL_FIELDS)
```

with:

```python
        inserted_keys: set[tuple[int, str]] = set()
        skipped_keys: set[tuple[int, str]] = set()

        for index, mapped in enumerate(mapped_rows, start=1):
            row_key = gl_scope_key(mapped)
            if import_mode == "skip" and row_key in existing_keys:
                skipped_keys.add(row_key)
                continue
            inserted_keys.add(row_key)
```

At the end, return:

```python
    return {
        "company": company,
        "year": year,
        "mode": import_mode,
        "line_count": len(rows),
        "inserted_count": len(inserted_keys),
        "skipped_count": len(skipped_keys),
        "deleted_count": deleted_count,
        "duplicate_count": len(existing_keys),
    }
```

- [ ] **Step 5: Add `--mode` to GL CLI command**

Modify `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`.

Change `import_gl_command` parameters:

```python
    mode: str = typer.Option("error", "--mode"),
```

Change call:

```python
echo_json(success("import.gl", import_gl(db, file, company, year, mapping, mode)))
```

- [ ] **Step 6: Run GL mode tests**

Run:

```powershell
python -m pytest tests\test_import_modes.py::test_gl_duplicate_import_defaults_to_error tests\test_import_modes.py::test_gl_skip_mode_does_not_duplicate_existing_voucher tests\test_import_modes.py::test_gl_replace_mode_replaces_existing_voucher -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src\ledger_agent_cli\importers\gl.py src\ledger_agent_cli\cli.py tests\test_import_modes.py
git commit -m "feat: add gl incremental import modes"
```

Expected: commit succeeds.

---

### Task 4: TB Duplicate Detection, Skip, And Replace

**Files:**
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\tb.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`

- [ ] **Step 1: Add failing TB import mode tests**

Append to `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_import_modes.py`:

```python
from ledger_agent_cli.importers.tb import import_tb


TB_MAPPING = {
    "month": "月份",
    "account_code": "科目编码",
    "account_name": "科目名称",
    "account_level": "科目层级",
    "opening_balance": "期初余额",
    "current_debit": "本期借方",
    "current_credit": "本期贷方",
    "ytd_debit": "累计借方",
    "ytd_credit": "累计贷方",
    "ending_balance": "期末余额",
    "balance_direction": "余额方向",
    "auxiliary": "辅助核算",
}


def write_tb_file(path, amount, auxiliary=""):
    path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        f"12,660201,差旅费,2,0,{amount},0,{amount},0,{amount},借,{auxiliary}\n",
        encoding="utf-8",
    )


def tb_row_count(db_path):
    with connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM trial_balance").fetchone()["n"]


def tb_debit_total(db_path):
    with connect(db_path) as conn:
        return conn.execute("SELECT SUM(current_debit_cents) AS n FROM trial_balance").fetchone()["n"]


def test_tb_duplicate_import_defaults_to_error(tmp_path):
    db_path = tmp_path / "ledger.db"
    tb_path = tmp_path / "tb.csv"
    map_path = tmp_path / "tb.json"
    init_db(db_path)
    write_tb_file(tb_path, 1200)
    write_mapping(map_path, TB_MAPPING)
    import_tb(db_path, tb_path, "公司A", 2025, map_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["import", "tb", "--db", str(db_path), "--file", str(tb_path), "--company", "公司A", "--year", "2025", "--mapping", str(map_path)],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "duplicate_import_scope"
    assert tb_row_count(db_path) == 1


def test_tb_skip_mode_does_not_duplicate_existing_row(tmp_path):
    db_path = tmp_path / "ledger.db"
    tb_path = tmp_path / "tb.csv"
    map_path = tmp_path / "tb.json"
    init_db(db_path)
    write_tb_file(tb_path, 1200)
    write_mapping(map_path, TB_MAPPING)
    import_tb(db_path, tb_path, "公司A", 2025, map_path)

    result = import_tb(db_path, tb_path, "公司A", 2025, map_path, mode="skip")

    assert result["inserted_count"] == 0
    assert result["skipped_count"] == 1
    assert tb_row_count(db_path) == 1


def test_tb_replace_mode_replaces_existing_row(tmp_path):
    db_path = tmp_path / "ledger.db"
    tb_path = tmp_path / "tb.csv"
    replacement_path = tmp_path / "tb_replacement.csv"
    map_path = tmp_path / "tb.json"
    init_db(db_path)
    write_tb_file(tb_path, 1200)
    write_tb_file(replacement_path, 1500)
    write_mapping(map_path, TB_MAPPING)
    import_tb(db_path, tb_path, "公司A", 2025, map_path)

    result = import_tb(db_path, replacement_path, "公司A", 2025, map_path, mode="replace")

    assert result["deleted_count"] == 1
    assert result["inserted_count"] == 1
    assert tb_row_count(db_path) == 1
    assert tb_debit_total(db_path) == 150000
```

- [ ] **Step 2: Run TB mode tests to verify they fail**

Run:

```powershell
python -m pytest tests\test_import_modes.py::test_tb_duplicate_import_defaults_to_error tests\test_import_modes.py::test_tb_skip_mode_does_not_duplicate_existing_row tests\test_import_modes.py::test_tb_replace_mode_replaces_existing_row -v
```

Expected: FAIL because `import_tb` has no `mode` parameter and CLI has no `--mode`.

- [ ] **Step 3: Update TB importer for modes**

Modify `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\importers\tb.py`.

Add imports:

```python
from ledger_agent_cli.errors import DuplicateImportScopeError
from ledger_agent_cli.importers.modes import normalize_auxiliary, tb_scope_key, validate_import_mode
```

Change signature:

```python
def import_tb(
    db_path: str | Path,
    file_path: str | Path,
    company: str,
    year: int,
    mapping_path: str | Path,
    mode: str = "error",
) -> dict[str, Any]:
```

After loading rows:

```python
    import_mode = validate_import_mode(mode)
    mapped_rows = [apply_mapping(row, mapping, REQUIRED_TB_FIELDS) for row in rows]
    target_keys = sorted(set(tb_scope_key(mapped) for mapped in mapped_rows))
```

Inside transaction after `company_id`:

```python
        existing_keys = set()
        for month, account_code, auxiliary in target_keys:
            row = conn.execute(
                """
                SELECT id FROM trial_balance
                WHERE company_id=? AND year=? AND month=? AND account_code=?
                  AND COALESCE(auxiliary, '')=?
                """,
                (company_id, year, month, account_code, auxiliary),
            ).fetchone()
            if row is not None:
                existing_keys.add((month, account_code, auxiliary))

        if existing_keys and import_mode == "error":
            raise DuplicateImportScopeError(len(existing_keys))

        deleted_count = 0
        if existing_keys and import_mode == "replace":
            for month, account_code, auxiliary in existing_keys:
                deleted_count += conn.execute(
                    """
                    DELETE FROM trial_balance
                    WHERE company_id=? AND year=? AND month=? AND account_code=?
                      AND COALESCE(auxiliary, '')=?
                    """,
                    (company_id, year, month, account_code, auxiliary),
                ).rowcount
```

Replace loop start:

```python
        inserted_keys: set[tuple[int, str, str]] = set()
        skipped_keys: set[tuple[int, str, str]] = set()

        for mapped in mapped_rows:
            row_key = tb_scope_key(mapped)
            if import_mode == "skip" and row_key in existing_keys:
                skipped_keys.add(row_key)
                continue
            inserted_keys.add(row_key)
```

Use normalized auxiliary when inserting:

```python
                    normalize_auxiliary(mapped.get("auxiliary")),
```

Return:

```python
    return {
        "company": company,
        "year": year,
        "mode": import_mode,
        "row_count": len(rows),
        "inserted_count": len(inserted_keys),
        "skipped_count": len(skipped_keys),
        "deleted_count": deleted_count,
        "duplicate_count": len(existing_keys),
    }
```

- [ ] **Step 4: Add `--mode` to TB CLI command**

Modify `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`.

Change `import_tb_command` parameters:

```python
    mode: str = typer.Option("error", "--mode"),
```

Change call:

```python
echo_json(success("import.tb", import_tb(db, file, company, year, mapping, mode)))
```

- [ ] **Step 5: Run TB mode tests**

Run:

```powershell
python -m pytest tests\test_import_modes.py::test_tb_duplicate_import_defaults_to_error tests\test_import_modes.py::test_tb_skip_mode_does_not_duplicate_existing_row tests\test_import_modes.py::test_tb_replace_mode_replaces_existing_row -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src\ledger_agent_cli\importers\tb.py src\ledger_agent_cli\cli.py tests\test_import_modes.py
git commit -m "feat: add tb incremental import modes"
```

Expected: commit succeeds.

---

### Task 5: Delete Helpers

**Files:**
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\mutations\__init__.py`
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\mutations\delete.py`
- Create: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_delete_commands.py`

- [ ] **Step 1: Write failing tests for dry-run delete helpers**

Create `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_delete_commands.py`:

```python
import json

from ledger_agent_cli.db import connect, init_db
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.importers.tb import import_tb
from ledger_agent_cli.mutations.delete import delete_batch, delete_gl, delete_tb


GL_MAPPING = {
    "month": "月份",
    "voucher_date": "凭证日期",
    "voucher_no": "凭证字号",
    "line_no": "行号",
    "summary": "摘要",
    "account_code": "科目编码",
    "account_name": "科目名称",
    "debit": "借方金额",
    "credit": "贷方金额",
}

TB_MAPPING = {
    "month": "月份",
    "account_code": "科目编码",
    "account_name": "科目名称",
    "account_level": "科目层级",
    "opening_balance": "期初余额",
    "current_debit": "本期借方",
    "current_credit": "本期贷方",
    "ytd_debit": "累计借方",
    "ytd_credit": "累计贷方",
    "ending_balance": "期末余额",
    "balance_direction": "余额方向",
    "auxiliary": "辅助核算",
}


def write_mapping(path, mapping):
    path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")


def seed_gl_tb(tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    tb_path = tmp_path / "tb.csv"
    gl_map = tmp_path / "gl.json"
    tb_map = tmp_path / "tb.json"
    init_db(db_path)
    gl_path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额\n"
        "1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,1200,0\n"
        "1,2025/01/31,记-001,2,报销差旅费,100201,银行存款,0,1200\n",
        encoding="utf-8",
    )
    tb_path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        "12,660201,差旅费,2,0,1200,0,1200,0,1200,借,\n",
        encoding="utf-8",
    )
    write_mapping(gl_map, GL_MAPPING)
    write_mapping(tb_map, TB_MAPPING)
    import_gl(db_path, gl_path, "公司A", 2025, gl_map)
    import_tb(db_path, tb_path, "公司A", 2025, tb_map)
    return db_path


def count_rows(db_path, table):
    with connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def first_batch_id(db_path, source_type):
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT id FROM import_batches WHERE source_type=? ORDER BY id LIMIT 1",
            (source_type,),
        ).fetchone()["id"]


def test_delete_gl_dry_run_does_not_delete(tmp_path):
    db_path = seed_gl_tb(tmp_path)

    result = delete_gl(db_path, "公司A", 2025, month=1, yes=False)

    assert result["dry_run"] is True
    assert result["matched_headers"] == 1
    assert result["matched_lines"] == 2
    assert count_rows(db_path, "journal_lines") == 2


def test_delete_gl_with_yes_deletes_rows(tmp_path):
    db_path = seed_gl_tb(tmp_path)

    result = delete_gl(db_path, "公司A", 2025, month=1, yes=True)

    assert result["dry_run"] is False
    assert result["deleted_headers"] == 1
    assert result["deleted_lines"] == 2
    assert count_rows(db_path, "journal_lines") == 0


def test_delete_tb_dry_run_and_yes(tmp_path):
    db_path = seed_gl_tb(tmp_path)

    dry_run = delete_tb(db_path, "公司A", 2025, month=12, yes=False)
    actual = delete_tb(db_path, "公司A", 2025, month=12, yes=True)

    assert dry_run["matched_rows"] == 1
    assert actual["deleted_rows"] == 1
    assert count_rows(db_path, "trial_balance") == 0


def test_delete_batch_deletes_batch_rows_and_batch_record(tmp_path):
    db_path = seed_gl_tb(tmp_path)
    batch_id = first_batch_id(db_path, "gl")

    result = delete_batch(db_path, batch_id, yes=True)

    assert result["deleted_lines"] == 2
    assert result["deleted_batches"] == 1
    assert count_rows(db_path, "journal_lines") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests\test_delete_commands.py -v
```

Expected: FAIL because `ledger_agent_cli.mutations.delete` does not exist.

- [ ] **Step 3: Implement delete helpers**

Create `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\mutations\__init__.py`:

```python
"""Database mutation helpers for controlled CLI operations."""
```

Create `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\mutations\delete.py`:

```python
from __future__ import annotations

from pathlib import Path

from ledger_agent_cli.db import connect, transaction
from ledger_agent_cli.queries.accounts import get_company_id


def delete_gl(db_path: str | Path, company: str, year: int, month: int | None = None, yes: bool = False) -> dict:
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
        deleted_headers = conn.execute(f"DELETE FROM journal_headers WHERE {where}", params).rowcount
    result.update({"deleted_lines": deleted_lines, "deleted_headers": deleted_headers})
    return result


def delete_tb(db_path: str | Path, company: str, year: int, month: int | None = None, yes: bool = False) -> dict:
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

    result = {"dry_run": not yes, "company": company, "year": year, "month": month, "matched_rows": matched_rows}
    if not yes:
        return result

    with transaction(db_path) as conn:
        deleted_rows = conn.execute(f"DELETE FROM trial_balance WHERE {where}", params).rowcount
    result["deleted_rows"] = deleted_rows
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
        conn.execute(
            """
            DELETE FROM journal_headers
            WHERE NOT EXISTS (
              SELECT 1 FROM journal_lines WHERE journal_lines.header_id = journal_headers.id
            )
            """
        )
        deleted_tb_rows = conn.execute(
            "DELETE FROM trial_balance WHERE import_batch_id=?",
            (batch_id,),
        ).rowcount
        deleted_batches = conn.execute("DELETE FROM import_batches WHERE id=?", (batch_id,)).rowcount
    result.update(
        {
            "deleted_lines": deleted_lines,
            "deleted_tb_rows": deleted_tb_rows,
            "deleted_batches": deleted_batches,
        }
    )
    return result
```

- [ ] **Step 4: Run delete helper tests**

Run:

```powershell
python -m pytest tests\test_delete_commands.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src\ledger_agent_cli\mutations tests\test_delete_commands.py
git commit -m "feat: add controlled delete helpers"
```

Expected: commit succeeds.

---

### Task 6: Delete CLI Commands

**Files:**
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_delete_commands.py`

- [ ] **Step 1: Add failing CLI tests for delete commands**

Append to `D:\BaiduSyncdisk\claude\ledger-agent-cli\tests\test_delete_commands.py`:

```python
from conftest import parse_json
from ledger_agent_cli.cli import app


def test_delete_gl_cli_dry_run_and_yes(runner, tmp_path):
    db_path = seed_gl_tb(tmp_path)

    dry_run = runner.invoke(
        app,
        ["delete", "gl", "--db", str(db_path), "--company", "公司A", "--year", "2025", "--month", "1"],
    )
    dry_payload = parse_json(dry_run)
    assert dry_payload["command"] == "delete.gl"
    assert dry_payload["data"]["dry_run"] is True
    assert count_rows(db_path, "journal_lines") == 2

    actual = runner.invoke(
        app,
        ["delete", "gl", "--db", str(db_path), "--company", "公司A", "--year", "2025", "--month", "1", "--yes"],
    )
    actual_payload = parse_json(actual)
    assert actual_payload["data"]["deleted_lines"] == 2
    assert count_rows(db_path, "journal_lines") == 0


def test_delete_tb_cli_dry_run_and_yes(runner, tmp_path):
    db_path = seed_gl_tb(tmp_path)

    dry_run = runner.invoke(
        app,
        ["delete", "tb", "--db", str(db_path), "--company", "公司A", "--year", "2025", "--month", "12"],
    )
    dry_payload = parse_json(dry_run)
    assert dry_payload["command"] == "delete.tb"
    assert dry_payload["data"]["dry_run"] is True

    actual = runner.invoke(
        app,
        ["delete", "tb", "--db", str(db_path), "--company", "公司A", "--year", "2025", "--month", "12", "--yes"],
    )
    actual_payload = parse_json(actual)
    assert actual_payload["data"]["deleted_rows"] == 1


def test_delete_batch_cli_deletes_batch(runner, tmp_path):
    db_path = seed_gl_tb(tmp_path)
    batch_id = first_batch_id(db_path, "gl")

    result = runner.invoke(
        app,
        ["delete", "batch", "--db", str(db_path), "--batch-id", str(batch_id), "--yes"],
    )
    payload = parse_json(result)

    assert payload["command"] == "delete.batch"
    assert payload["data"]["deleted_batches"] == 1
```

- [ ] **Step 2: Run CLI delete tests to verify they fail**

Run:

```powershell
python -m pytest tests\test_delete_commands.py::test_delete_gl_cli_dry_run_and_yes tests\test_delete_commands.py::test_delete_tb_cli_dry_run_and_yes tests\test_delete_commands.py::test_delete_batch_cli_deletes_batch -v
```

Expected: FAIL because `delete` command group does not exist.

- [ ] **Step 3: Add delete CLI group**

Modify `D:\BaiduSyncdisk\claude\ledger-agent-cli\src\ledger_agent_cli\cli.py`.

Add import:

```python
from ledger_agent_cli.mutations.delete import delete_batch, delete_gl, delete_tb
```

Add group near other Typer groups:

```python
delete_app = typer.Typer(no_args_is_help=True)
app.add_typer(delete_app, name="delete")
```

Add commands:

```python
@delete_app.command("batch")
def delete_batch_command(
    db: Path = typer.Option(..., "--db"),
    batch_id: int = typer.Option(..., "--batch-id"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        echo_json(success("delete.batch", delete_batch(db, batch_id, yes)))
    except Exception as exc:
        exit_with_error("delete.batch", exc)


@delete_app.command("gl")
def delete_gl_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    month: int | None = typer.Option(None, "--month"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        echo_json(success("delete.gl", delete_gl(db, company, year, month, yes)))
    except Exception as exc:
        exit_with_error("delete.gl", exc)


@delete_app.command("tb")
def delete_tb_command(
    db: Path = typer.Option(..., "--db"),
    company: str = typer.Option(..., "--company"),
    year: int = typer.Option(..., "--year"),
    month: int | None = typer.Option(None, "--month"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        echo_json(success("delete.tb", delete_tb(db, company, year, month, yes)))
    except Exception as exc:
        exit_with_error("delete.tb", exc)
```

- [ ] **Step 4: Run delete CLI tests**

Run:

```powershell
python -m pytest tests\test_delete_commands.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src\ledger_agent_cli\cli.py tests\test_delete_commands.py
git commit -m "feat: add delete cli commands"
```

Expected: commit succeeds.

---

### Task 7: Documentation And Full Verification

**Files:**
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\README.md`
- Modify: `D:\BaiduSyncdisk\claude\ledger-agent-cli\docs\cli-commands.md`

- [ ] **Step 1: Update README**

Add this section to `D:\BaiduSyncdisk\claude\ledger-agent-cli\README.md` after “常用命令”:

````markdown
## 安全导入和删除

导入默认使用 `--mode error`。如果目标范围已经有数据，会直接报错，不会重复插入。

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode error
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode skip
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode replace
```

删除命令默认 dry-run，不加 `--yes` 时只显示将删除多少数据。

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12 --yes
ledger-cli delete batch --db ledger.db --batch-id 1 --yes
```
````

- [ ] **Step 2: Update command docs**

Add these lines to the command block in `D:\BaiduSyncdisk\claude\ledger-agent-cli\docs\cli-commands.md`:

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode replace
ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json --mode skip
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12 --yes
ledger-cli delete batch --db ledger.db --batch-id 1 --yes
```

- [ ] **Step 3: Run full test suite**

Run:

```powershell
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Run CLI smoke test**

Run:

```powershell
Remove-Item -Path .\ledger.db -ErrorAction SilentlyContinue
ledger-cli init --db ledger.db
ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json
ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json --mode skip
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
```

Expected:

- first import returns `"ok":true`
- second import returns `"ok":true` with `"mode":"skip"`
- delete command returns `"dry_run":true`

- [ ] **Step 5: Commit**

Run:

```powershell
git add README.md docs\cli-commands.md
git commit -m "docs: document safe imports and deletes"
```

Expected: commit succeeds.

---

## Final Verification

- [ ] Run:

```powershell
python -m pytest -v
```

Expected: all tests PASS.

- [ ] Run:

```powershell
git status --short --branch
```

Expected: clean working tree on `master`, ahead of `origin/master` until pushed.

- [ ] Push after implementation:

```powershell
git push
```

Expected: GitHub repository receives all commits.

## Spec Coverage Self-Review

- Default duplicate import error: Task 3 and Task 4.
- `--mode skip`: Task 3 and Task 4.
- `--mode replace`: Task 3 and Task 4.
- GL uniqueness by voucher: Task 1 and Task 3.
- TB uniqueness by account plus auxiliary: Task 1 and Task 4.
- Batch deletion: Task 5 and Task 6.
- GL/TB period deletion: Task 5 and Task 6.
- Delete dry-run default: Task 5 and Task 6.
- JSON CLI output: Task 1, Task 3, Task 4, Task 6.
- Documentation: Task 7.
- Full verification: Task 7 and Final Verification.
