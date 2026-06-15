---
name: ledger-cli
description: Guidance for using ledger-agent-cli to import and query accounting ledgers safely.
---

# ledger-agent-cli Skill

Use this skill when working with the `ledger-agent-cli` project or when asked to import/query accounting data (general ledger / trial balance).

## Project Purpose

`ledger-agent-cli` is an agent-safe CLI for importing and querying accounting ledgers. It stores data in SQLite and exposes controlled commands. Agents should NOT write to the SQLite database directly; all mutations go through the CLI.

## Typical Workflow

1. Initialize database: `ledger-cli init --db ledger.db`
2. Import data:
   - GL: `ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json`
   - TB: `ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json`
3. Explore: `ledger-cli schema`, `ledger-cli companies`, `ledger-cli accounts search ...`
4. Analyze: `ledger-cli variance tb ...`, `ledger-cli variance gl ...`, `ledger-cli trace depreciation ...`, `ledger-cli reconcile gl-tb ...`
5. Save reusable queries: `ledger-cli saved-query add ...`, `ledger-cli saved-query run ...`

## Import Modes

- `error` (default): fail if target data already exists.
- `skip`: skip existing data, import only new data.
- `replace`: delete old data for the same key, then import new data.

## Delete Safety

Delete commands default to dry-run. Always run without `--yes` first to review impact, then add `--yes` to execute.

Example:

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
```

## Output Formats

- Agent calls should use `--format json` for deterministic parsing.
- Humans in a terminal get table output by default.
- Use `--format csv` to paste into Excel.

## Configuration

Check for `ledger-cli.toml` in the project root. It can set defaults like `db`, `format`, and import `company`/`year`.

## Important Constraints

- Use `ledger-cli sql select --query "SELECT ..."` for read-only exploration only. Write SQL is blocked.
- Never bypass the CLI to modify the SQLite database directly.
- Money is stored as integer cents internally; CLI output converts to yuan strings.
- Audit logs are written to `ledger-cli.log` next to the database for all imports and deletes.
