from conftest import parse_json
from ledger_agent_cli.cli import app
from ledger_agent_cli.db import init_db
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.importers.tb import import_tb


def seed_sample(tmp_path):
    db_path = tmp_path / "ledger.db"
    gl_2024_path = tmp_path / "gl_2024.csv"
    gl_2025_path = tmp_path / "gl_2025.csv"
    tb_2024_path = tmp_path / "tb_2024.csv"
    tb_2025_path = tmp_path / "tb_2025.csv"
    gl_map = tmp_path / "gl.json"
    tb_map = tmp_path / "tb.json"
    init_db(db_path)
    gl_2024_path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额,辅助核算\n"
        "1,2024/01/31,记-001,1,报销差旅费,660201,差旅费,500,0,张三\n",
        encoding="utf-8",
    )
    gl_2025_path.write_text(
        "月份,凭证日期,凭证字号,行号,摘要,科目编码,科目名称,借方金额,贷方金额,辅助核算\n"
        "1,2025/01/31,记-001,1,报销差旅费,660201,差旅费,1200,0,张三\n",
        encoding="utf-8",
    )
    tb_2024_path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        "12,660201,差旅费,2,0,500,0,500,0,500,借,\n",
        encoding="utf-8",
    )
    tb_2025_path.write_text(
        "月份,科目编码,科目名称,科目层级,期初余额,本期借方,本期贷方,累计借方,累计贷方,期末余额,余额方向,辅助核算\n"
        "12,660201,差旅费,2,0,1200,0,1200,0,1200,借,\n",
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
    import_gl(db_path, gl_2024_path, "公司A", 2024, gl_map)
    import_gl(db_path, gl_2025_path, "公司A", 2025, gl_map)
    import_tb(db_path, tb_2024_path, "公司A", 2024, tb_map)
    import_tb(db_path, tb_2025_path, "公司A", 2025, tb_map)
    return db_path


def test_variance_tb_command(runner, tmp_path):
    db_path = seed_sample(tmp_path)

    result = runner.invoke(
        app,
        [
            "variance",
            "tb",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--compare-year",
            "2024",
            "--account",
            "差旅费",
        ],
    )
    payload = parse_json(result)

    assert payload["command"] == "variance.tb"
    assert payload["data"]["rows"][0]["delta_cents"] == 70000


def test_variance_gl_command_lists_current_year_lines(runner, tmp_path):
    db_path = seed_sample(tmp_path)

    result = runner.invoke(
        app,
        [
            "variance",
            "gl",
            "--db",
            str(db_path),
            "--company",
            "公司A",
            "--year",
            "2025",
            "--compare-year",
            "2024",
            "--account",
            "差旅费",
        ],
    )
    payload = parse_json(result)

    assert payload["command"] == "variance.gl"
    assert payload["data"]["current_total_cents"] == 120000
    assert payload["data"]["compare_total_cents"] == 50000
