import json

import pytest
from typer.testing import CliRunner

from ledger_agent_cli.cli import app
from ledger_agent_cli.db import connect, init_db
from ledger_agent_cli.errors import InvalidImportModeError
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.importers.modes import (
    gl_scope_key,
    normalize_auxiliary,
    tb_scope_key,
    validate_import_mode,
)
from ledger_agent_cli.importers.tb import import_tb

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


def write_gl_file(path, amount):
    path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额\n"
        f"1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,{amount},0\n"
        f"1,2025/01/31,记-001,2,报销差旅费,100201,银行存款,0,{amount}\n",
        encoding="utf-8",
    )


def write_duplicate_gl_line_file(path):
    path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额\n"
        "1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,1200,0\n"
        "1,2025/01/31,记-001,1,报销差旅费,100201,银行存款,0,1200\n",
        encoding="utf-8",
    )


def write_tb_file(path, amount, auxiliary=""):
    path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        f"12,660201,差旅费,2,0,{amount},0,{amount},0,{amount},借,{auxiliary}\n",
        encoding="utf-8",
    )


def write_duplicate_tb_file(path):
    path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        "12,660201,差旅费,2,0,1200,0,1200,0,1200,借,部门A\n"
        "12,660201,差旅费,2,0,1500,0,1500,0,1500,借,部门A\n",
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


def tb_row_count(db_path):
    with connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM trial_balance").fetchone()["n"]


def tb_debit_total(db_path):
    with connect(db_path) as conn:
        return conn.execute("SELECT SUM(current_debit_cents) AS n FROM trial_balance").fetchone()["n"]


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
        [
            "import",
            "gl",
            "--db",
            str(db_path),
            "--file",
            str(gl_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--mapping",
            str(map_path),
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "duplicate_import_scope"
    assert gl_line_count(db_path) == 2


def test_gl_input_duplicate_line_returns_controlled_error(tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    map_path = tmp_path / "gl.json"
    init_db(db_path)
    write_duplicate_gl_line_file(gl_path)
    write_mapping(map_path, GL_MAPPING)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "import",
            "gl",
            "--db",
            str(db_path),
            "--file",
            str(gl_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--mapping",
            str(map_path),
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "duplicate_input_scope"
    assert payload["error"]["details"]["duplicate_count"] == 1
    assert gl_line_count(db_path) == 0


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
        [
            "import",
            "tb",
            "--db",
            str(db_path),
            "--file",
            str(tb_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--mapping",
            str(map_path),
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "duplicate_import_scope"
    assert tb_row_count(db_path) == 1


def test_tb_input_duplicate_row_returns_controlled_error(tmp_path):
    db_path = tmp_path / "ledger.db"
    tb_path = tmp_path / "tb.csv"
    map_path = tmp_path / "tb.json"
    init_db(db_path)
    write_duplicate_tb_file(tb_path)
    write_mapping(map_path, TB_MAPPING)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "import",
            "tb",
            "--db",
            str(db_path),
            "--file",
            str(tb_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--mapping",
            str(map_path),
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "duplicate_input_scope"
    assert payload["error"]["details"]["duplicate_count"] == 1
    assert tb_row_count(db_path) == 0


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
