from unittest.mock import MagicMock

from ledger_agent_cli.output import (
    _flatten_rows,
    get_format,
    render_result,
    set_format,
)


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


# --- _flatten_rows tests ---


def test_flatten_rows_with_rows_shape():
    data = {"rows": [{"a": 1}, {"a": 2}], "meta": {"count": 2}}
    assert _flatten_rows(data) == [{"a": 1}, {"a": 2}]


def test_flatten_rows_with_data_shape():
    data = {"data": [{"b": 1}, {"b": 2}], "meta": {"count": 2}}
    assert _flatten_rows(data) == [{"b": 1}, {"b": 2}]


def test_flatten_rows_with_plain_list_of_dicts():
    data = [{"c": 1}, {"c": 2}]
    assert _flatten_rows(data) == [{"c": 1}, {"c": 2}]


def test_flatten_rows_filters_non_dict_elements():
    data = [{"a": 1}, "not a dict", {"a": 2}, None, 42]
    assert _flatten_rows(data) == [{"a": 1}, {"a": 2}]


def test_flatten_rows_with_rows_shape_filters_non_dict():
    data = {"rows": [{"a": 1}, "bad", {"a": 2}]}
    assert _flatten_rows(data) == [{"a": 1}, {"a": 2}]


def test_flatten_rows_empty_list():
    assert _flatten_rows([]) == []


def test_flatten_rows_non_dict_non_list():
    assert _flatten_rows("hello") == []


# --- render_result dispatch tests ---


def test_render_result_dispatches_to_json(monkeypatch):
    set_format("json")
    mock_echo = MagicMock()
    monkeypatch.setattr("ledger_agent_cli.output.typer.echo", mock_echo)
    render_result("test", [{"a": 1}])
    assert mock_echo.call_count == 1
    output = mock_echo.call_args[0][0]
    assert '"ok":true' in output
    assert '"command":"test"' in output


def test_render_result_dispatches_to_csv(monkeypatch):
    set_format("csv")
    mock_echo = MagicMock()
    monkeypatch.setattr("ledger_agent_cli.output.typer.echo", mock_echo)
    render_result("test", [{"a": 1}, {"a": 2}])
    assert mock_echo.call_count == 1
    output = mock_echo.call_args[0][0]
    assert output.replace("\r\n", "\n").rstrip("\n") == "a\n1\n2"


def test_render_result_csv_empty_fallback(monkeypatch):
    set_format("csv")
    mock_echo = MagicMock()
    monkeypatch.setattr("ledger_agent_cli.output.typer.echo", mock_echo)
    render_result("test", "plain string")
    assert mock_echo.call_count == 1
    output = mock_echo.call_args[0][0]
    assert output == "plain string"


def test_render_result_table_empty_fallback(monkeypatch):
    set_format("table")
    mock_echo = MagicMock()
    monkeypatch.setattr("ledger_agent_cli.output.typer.echo", mock_echo)
    render_result("test", "plain string")
    assert mock_echo.call_count == 1
    output = mock_echo.call_args[0][0]
    assert output == "plain string"
