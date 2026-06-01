from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import init_db
from ledger_agent_cli.importers.gl import import_gl


def test_trace_depreciation_groups_debit_accounts(runner, tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_path = tmp_path / "gl.csv"
    gl_map = tmp_path / "gl.json"
    init_db(db_path)
    gl_path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额,辅助核算\n"
        "2,2025/02/28,记-002,1,计提折旧,660301,折旧费,300,0,\n"
        "2,2025/02/28,记-002,2,计提折旧,1602,累计折旧,0,300,\n",
        encoding="utf-8",
    )
    gl_map.write_text(
        '{"month":"月份","voucher_date":"凭证日期","voucher_no":"凭证字号","line_no":"行号","summary":"摘要","account_code":"科目编码","account_name":"科目名称","debit":"借方金额","credit":"贷方金额","auxiliary":"辅助核算"}',
        encoding="utf-8",
    )
    import_gl(db_path, gl_path, "公司A", 2025, gl_map)

    result = runner.invoke(
        app,
        ["trace", "depreciation", "--db", str(db_path), "--company", "公司A", "--year", "2025"],
    )
    payload = parse_json(result)

    assert payload["command"] == "trace.depreciation"
    assert payload["data"]["rows"][0]["debit_account_name"] == "折旧费"
    assert payload["data"]["rows"][0]["amount_cents"] == 30000
