# ledger-agent-cli

`ledger-agent-cli` imports general ledger and trial balance files into SQLite and exposes agent-safe JSON commands for accounting queries and audit checks.

## Quick Start

```powershell
python -m pip install -e .[dev]
ledger-cli init --db ledger.db
ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json
ledger-cli import tb --db ledger.db --file examples\sample_tb.csv --company 公司A --year 2025 --mapping examples\mappings\tb_zh.json
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅
ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
```

## Design

- SQLite stores normalized GL/TB data.
- CLI is the stable interface for agents.
- Money is stored as integer cents.
- Raw source rows are preserved as JSON.
- Fixed commands cover common audit workflows.
- `sql select` is read-only and guarded.
