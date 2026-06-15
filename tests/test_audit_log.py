import json

from ledger_agent_cli.audit_log import _log_path, log_operation
from ledger_agent_cli.importers.gl import import_gl
from ledger_agent_cli.mutations.delete import delete_gl


def test_log_path_next_to_db(tmp_path):
    db = tmp_path / "ledger.db"
    assert _log_path(db) == tmp_path / "ledger-cli.log"


def test_log_path_for_path_without_suffix(tmp_path):
    db = tmp_path / "ledger"
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


def test_log_operation_sanitizes_file_and_mapping_arguments(tmp_path):
    db = tmp_path / "ledger.db"
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text("{}", encoding="utf-8")
    file_path = tmp_path / "data.csv"
    file_path.write_text("h\n1", encoding="utf-8")

    log_operation(
        db,
        "import.gl",
        {"file": file_path, "mapping": mapping_path, "company": "A"},
        {"inserted_count": 1},
    )

    log_file = tmp_path / "ledger-cli.log"
    entry = json.loads(log_file.read_text(encoding="utf-8").strip().splitlines()[0])
    assert entry["arguments"]["file"] == str(file_path)
    assert entry["arguments"]["mapping"] == str(mapping_path)
    assert entry["arguments"]["company"] == "A"


def test_log_operation_summarizes_result(tmp_path):
    db = tmp_path / "ledger.db"
    result = {
        "mode": "error",
        "line_count": 10,
        "inserted_count": 5,
        "skipped_count": 2,
        "deleted_count": 1,
        "unknown_key": "should_be_excluded",
    }
    log_operation(db, "import.gl", {"company": "A"}, result)

    log_file = tmp_path / "ledger-cli.log"
    entry = json.loads(log_file.read_text(encoding="utf-8").strip().splitlines()[0])
    summary = entry["result_summary"]
    assert summary == {
        "mode": "error",
        "line_count": 10,
        "inserted_count": 5,
        "skipped_count": 2,
        "deleted_count": 1,
    }
    assert "unknown_key" not in summary


def test_log_operation_failure_does_not_raise(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"

    def _raise(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", _raise)
    log_operation(db, "import.gl", {"company": "A"}, {"inserted_count": 5})
    # No exception should be raised.


def test_import_gl_writes_audit_log_end_to_end(tmp_path):
    db = tmp_path / "ledger.db"
    from ledger_agent_cli.db import init_db

    init_db(db)
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "month": "月份",
                "voucher_date": "凭证日期",
                "voucher_no": "凭证字号",
                "account_code": "科目编码",
                "account_name": "科目名称",
                "debit": "借方金额",
                "credit": "贷方金额",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "月份,凭证日期,凭证字号,科目编码,科目名称,借方金额,贷方金额\n"
        "1,2024-01-01,记-1,1001,现金,100,0\n",
        encoding="utf-8",
    )

    import_gl(db, csv_path, "A", 2024, mapping_path, mode="error")

    log_file = tmp_path / "ledger-cli.log"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["command"] == "import.gl"
    assert entry["arguments"]["company"] == "A"
    assert entry["result_summary"]["inserted_count"] == 1


def test_delete_gl_writes_audit_log_end_to_end(tmp_path):
    db = tmp_path / "ledger.db"
    from ledger_agent_cli.db import init_db

    init_db(db)
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "month": "月份",
                "voucher_date": "凭证日期",
                "voucher_no": "凭证字号",
                "account_code": "科目编码",
                "account_name": "科目名称",
                "debit": "借方金额",
                "credit": "贷方金额",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "月份,凭证日期,凭证字号,科目编码,科目名称,借方金额,贷方金额\n"
        "1,2024-01-01,记-1,1001,现金,100,0\n",
        encoding="utf-8",
    )

    import_gl(db, csv_path, "A", 2024, mapping_path, mode="error")

    delete_gl(db, "A", 2024, yes=True)

    log_file = tmp_path / "ledger-cli.log"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[1])
    assert entry["command"] == "delete.gl"
    assert entry["arguments"]["company"] == "A"
    assert entry["result_summary"]["deleted_headers"] == 1
