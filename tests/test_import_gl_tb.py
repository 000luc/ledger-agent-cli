import json

from ledger_agent_cli.db import connect, init_db
from ledger_agent_cli.importers.gl import import_gl
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
    "auxiliary": "辅助核算",
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


def test_import_gl_creates_company_accounts_headers_and_lines(tmp_path):
    db_path = tmp_path / "ledger.db"
    file_path = tmp_path / "gl.csv"
    mapping_path = tmp_path / "gl_mapping.json"
    init_db(db_path)
    file_path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额,辅助核算,原始列\n"
        "1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,1200,0,张三,保留\n"
        "1,2025/01/31,记-001,2,报销差旅费,100201,银行存款,0,1200,,保留\n",
        encoding="utf-8",
    )
    write_mapping(mapping_path, GL_MAPPING)

    result = import_gl(db_path, file_path, "公司A", 2025, mapping_path)

    assert result["line_count"] == 2
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"] == 1
        assert conn.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"] == 2
        assert conn.execute("SELECT COUNT(*) AS n FROM journal_headers").fetchone()["n"] == 1
        line = conn.execute(
            "SELECT debit_cents, raw_json FROM journal_lines WHERE account_code='660201'"
        ).fetchone()
    assert line["debit_cents"] == 120000
    assert "原始列" in line["raw_json"]


def test_import_tb_creates_trial_balance_rows(tmp_path):
    db_path = tmp_path / "ledger.db"
    file_path = tmp_path / "tb.csv"
    mapping_path = tmp_path / "tb_mapping.json"
    init_db(db_path)
    file_path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        "12,660201,差旅费,2,0,1200,0,1200,0,1200,借,\n",
        encoding="utf-8",
    )
    write_mapping(mapping_path, TB_MAPPING)

    result = import_tb(db_path, file_path, "公司A", 2025, mapping_path)

    assert result["row_count"] == 1
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT current_debit_cents, ending_balance_cents FROM trial_balance"
        ).fetchone()
    assert row["current_debit_cents"] == 120000
    assert row["ending_balance_cents"] == 120000
