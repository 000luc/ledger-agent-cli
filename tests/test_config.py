import json
from pathlib import Path

from ledger_agent_cli.cli import app
from ledger_agent_cli.config import clear_config_cache, find_config_file, get_default


def test_find_config_file_in_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'test.db'\n", encoding="utf-8")
    found = find_config_file()
    assert found == config_path
    clear_config_cache()


def test_find_config_file_stops_at_git_root(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    (parent / ".git").mkdir()
    config_path = child / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'child.db'\n", encoding="utf-8")
    monkeypatch.chdir(child)
    clear_config_cache()
    found = find_config_file()
    assert found == config_path
    clear_config_cache()


def test_find_config_file_prefers_dot_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    dotted = tmp_path / ".ledger-cli.toml"
    plain = tmp_path / "ledger-cli.toml"
    dotted.write_text("[defaults]\ndb = 'dotted.db'\n", encoding="utf-8")
    plain.write_text("[defaults]\ndb = 'plain.db'\n", encoding="utf-8")
    found = find_config_file()
    assert found == dotted
    clear_config_cache()


def test_find_config_file_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    found = find_config_file()
    assert found is None
    clear_config_cache()


def test_get_default_returns_fallback_for_missing_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'test.db'\n", encoding="utf-8")
    assert get_default(["defaults", "missing"], "fallback") == "fallback"
    clear_config_cache()


def test_get_default_returns_fallback_for_non_dict_intermediate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'test.db'\n", encoding="utf-8")
    assert get_default(["defaults", "db", "extra"], "fallback") == "fallback"
    clear_config_cache()


def test_get_default_distinguishes_empty_dict_from_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\nimport = {}\n", encoding="utf-8")
    assert get_default(["defaults", "import", "company"], "fallback") == "fallback"
    clear_config_cache()


def test_config_default_company_and_year(tmp_path, monkeypatch, runner):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults.import]\ncompany = 'ACME'\nyear = 2024\n", encoding="utf-8")
    assert get_default(["defaults", "import", "company"]) == "ACME"
    assert get_default(["defaults", "import", "year"]) == 2024
    clear_config_cache()


def test_config_default_format(tmp_path, monkeypatch, runner):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\nformat = 'table'\n", encoding="utf-8")
    assert get_default(["defaults", "format"]) == "table"
    clear_config_cache()


def test_config_default_db_reduces_required_flags(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'ledger.db'\n", encoding="utf-8")

    result = runner.invoke(app, ["schema"])
    clear_config_cache()

    payload = json.loads(result.output)
    assert (
        payload.get("error") is None
        or payload.get("error", {}).get("code") != "missing_required_flags"
    )
