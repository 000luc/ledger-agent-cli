import json

from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import connect, init_db, transaction
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


def test_delete_batch_only_deletes_headers_from_target_batch(tmp_path):
    db_path = seed_gl_tb(tmp_path)
    batch_id = first_batch_id(db_path, "gl")
    with transaction(db_path) as conn:
        company_id = conn.execute("SELECT id FROM companies WHERE name=?", ("公司A",)).fetchone()[
            "id"
        ]
        other_batch_id = conn.execute(
            """
            INSERT INTO import_batches(company_id, source_type, source_file, year, mapping_json)
            VALUES (?, 'gl', 'other.csv', 2025, '{}')
            """,
            (company_id,),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO journal_headers(
              company_id, import_batch_id, year, month, voucher_date, voucher_no, raw_json
            )
            VALUES (?, ?, 2025, 2, '2025-02-28', '记-999', '{}')
            """,
            (company_id, other_batch_id),
        )

    result = delete_batch(db_path, batch_id, yes=True)

    assert result["deleted_headers"] == 1
    with connect(db_path) as conn:
        remaining = conn.execute(
            "SELECT voucher_no FROM journal_headers WHERE import_batch_id=?",
            (other_batch_id,),
        ).fetchall()
    assert [row["voucher_no"] for row in remaining] == ["记-999"]


def test_delete_gl_cli_dry_run_and_yes(runner, tmp_path):
    db_path = seed_gl_tb(tmp_path)

    dry_run = runner.invoke(
        app,
        [
            "delete",
            "gl",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--month",
            "1",
        ],
    )
    dry_payload = parse_json(dry_run)
    assert dry_payload["command"] == "delete.gl"
    assert dry_payload["data"]["dry_run"] is True
    assert count_rows(db_path, "journal_lines") == 2

    actual = runner.invoke(
        app,
        [
            "delete",
            "gl",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--month",
            "1",
            "--yes",
        ],
    )
    actual_payload = parse_json(actual)
    assert actual_payload["data"]["deleted_lines"] == 2
    assert count_rows(db_path, "journal_lines") == 0


def test_delete_tb_cli_dry_run_and_yes(runner, tmp_path):
    db_path = seed_gl_tb(tmp_path)

    dry_run = runner.invoke(
        app,
        [
            "delete",
            "tb",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--month",
            "12",
        ],
    )
    dry_payload = parse_json(dry_run)
    assert dry_payload["command"] == "delete.tb"
    assert dry_payload["data"]["dry_run"] is True

    actual = runner.invoke(
        app,
        [
            "delete",
            "tb",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--month",
            "12",
            "--yes",
        ],
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
