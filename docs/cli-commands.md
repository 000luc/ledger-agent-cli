# CLI 命令

所有命令都输出 JSON，方便 agent 调用和解析。

## 初始化

```powershell
ledger-cli init --db ledger.db
ledger-cli schema --db ledger.db
ledger-cli companies --db ledger.db
```

## 导入

```powershell
ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json
ledger-cli import tb --db ledger.db --file examples\sample_tb.csv --company 公司A --year 2025 --mapping examples\mappings\tb_zh.json
```

导入支持 `--mode error|skip|replace`：

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode error
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode skip
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode replace

ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json --mode replace
```

- `error`：默认模式。遇到重复数据时报错。
- `skip`：跳过已有数据，只导入新数据。
- `replace`：删除同一识别键旧数据，再导入新数据。

## 删除

删除命令不加 `--yes` 时只做 dry-run。

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes

ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12
ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12 --yes

ledger-cli delete batch --db ledger.db --batch-id 1
ledger-cli delete batch --db ledger.db --batch-id 1 --yes
```

`delete gl` 和 `delete tb` 必须指定公司和年度；`--month` 可选，不传就是该年度全部月份。

## 查询

```powershell
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅

ledger-cli variance tb --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费
ledger-cli variance gl --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费

ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
ledger-cli reconcile gl-tb --db ledger.db --company 公司A --year 2025

ledger-cli sql select --db ledger.db --query "SELECT name FROM companies"
```

## 查询模板

```powershell
ledger-cli saved-query add --db ledger.db --name echo-year --description "Echo year" --query "SELECT :year AS year" --parameter year
ledger-cli saved-query list --db ledger.db
ledger-cli saved-query run --db ledger.db --name echo-year --value year=2025
```
