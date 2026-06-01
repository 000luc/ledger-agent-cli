# CLI Commands

All commands output JSON.

```powershell
ledger-cli init --db ledger.db
ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json
ledger-cli import tb --db ledger.db --file examples\sample_tb.csv --company 公司A --year 2025 --mapping examples\mappings\tb_zh.json
ledger-cli schema --db ledger.db
ledger-cli companies --db ledger.db
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅
ledger-cli variance tb --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费
ledger-cli variance gl --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费
ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
ledger-cli reconcile gl-tb --db ledger.db --company 公司A --year 2025
ledger-cli sql select --db ledger.db --query "SELECT name FROM companies"
ledger-cli saved-query add --db ledger.db --name echo-year --description "Echo year" --query "SELECT :year AS year" --parameter year
ledger-cli saved-query list --db ledger.db
ledger-cli saved-query run --db ledger.db --name echo-year --value year=2025
```
