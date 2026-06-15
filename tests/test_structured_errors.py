import json

from ledger_agent_cli.cli import app


def test_missing_required_flags_returns_structured_json(runner):
    result = runner.invoke(app, ["import", "gl"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "missing_required_flags"
    assert "--db" in payload["error"]["details"]["missing_flags"]


def test_invalid_import_mode_returns_valid_modes(runner):
    result = runner.invoke(
        app,
        [
            "import",
            "gl",
            "--db",
            "ledger.db",
            "--file",
            "gl.csv",
            "--company",
            "公司A",
            "--year",
            "2025",
            "--mapping",
            "gl.json",
            "--mode",
            "append",
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "invalid_import_mode"
    assert payload["error"]["details"]["valid_modes"] == ["error", "skip", "replace"]
