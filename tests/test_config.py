import json

from ledger_agent_cli.cli import app
from ledger_agent_cli.config import clear_config_cache, find_config_file


def test_find_config_file_in_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    config_path = tmp_path / "ledger-cli.toml"
    config_path.write_text("[defaults]\ndb = 'test.db'\n", encoding="utf-8")
    found = find_config_file()
    assert found == config_path
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
