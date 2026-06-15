from ledger_agent_cli.output import get_format, set_format


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
