from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import init_db
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.importers.tb import import_tb


def test_reconcile_gl_tb_reports_no_difference_for_matching_amounts(runner, tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    tb_path = tmp_path / "tb.csv"
    gl_map = tmp_path / "gl.json"
    tb_map = tmp_path / "tb.json"
    init_db(db_path)
    gl_path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额,辅助核算\n"
        "1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,1200,0,张三\n",
        encoding="utf-8",
    )
    tb_path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        "1,660201,差旅费,2,0,1200,0,1200,0,1200,借,\n",
        encoding="utf-8",
    )
    gl_map.write_text(
        '{"month":"月份","voucher_date":"凭证日期","voucher_no":"凭证字号","line_no":"行号","summary":"摘要","account_code":"科目编码","account_name":"科目名称","debit":"借方金额","credit":"贷方金额","auxiliary":"辅助核算"}',
        encoding="utf-8",
    )
    tb_map.write_text(
        '{"month":"月份","account_code":"科目编码","account_name":"科目名称","account_level":"科目层级","opening_balance":"期初余额","current_debit":"本期借方","current_credit":"本期贷方","ytd_debit":"累计借方","ytd_credit":"累计贷方","ending_balance":"期末余额","balance_direction":"余额方向","auxiliary":"辅助核算"}',
        encoding="utf-8",
    )
    import_gl(db_path, gl_path, "公司A", 2025, gl_map)
    import_tb(db_path, tb_path, "公司A", 2025, tb_map)

    result = runner.invoke(
        app,
        ["reconcile", "gl-tb", "--db", str(db_path), "--company", "公司A", "--year", "2025"],
    )
    payload = parse_json(result)

    assert payload["command"] == "reconcile.gl-tb"
    assert payload["data"]["difference_count"] == 0
