import json

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
