# ledger-agent-cli

给 agent 使用的账套查询 CLI。

它把序时账和科目余额表导入 SQLite，再通过固定 JSON 命令查询账套、分析变动原因、执行常见勾稽测试。agent 不直接改数据库，只调用受控 CLI。

## 快速开始

```powershell
python -m pip install -e .[dev]

ledger-cli init --db ledger.db

ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json

ledger-cli import tb --db ledger.db --file examples\sample_tb.csv --company 公司A --year 2025 --mapping examples\mappings\tb_zh.json

ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅

ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
```

## 增量导入

导入默认使用 `--mode error`。如果发现重复数据，会报错并停止，避免误覆盖。

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode error
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode skip
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode replace

ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json --mode replace
```

- `error`：遇到重复凭证或余额表行就报错。
- `skip`：已有的数据不再重复导入。
- `replace`：先删除同一识别键的旧数据，再导入新数据。

识别键：

- 序时账导入模式：公司、年度、月份、凭证号；同一凭证内用行号防止重复分录。
- 科目余额表：公司、年度、月份、科目编码、辅助核算。

## 删除和替换

删除命令默认是 dry-run，只返回将删除多少数据，不真实删除。加 `--yes` 才会执行。

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes

ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12 --yes

ledger-cli delete batch --db ledger.db --batch-id 1 --yes
```

## 常用查询

```powershell
ledger-cli schema --db ledger.db
ledger-cli companies --db ledger.db
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 管理费用

ledger-cli variance tb --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费
ledger-cli variance gl --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费

ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
ledger-cli reconcile gl-tb --db ledger.db --company 公司A --year 2025

ledger-cli sql select --db ledger.db --query "SELECT name FROM companies"
```

## 查询沉淀

验证过的 SQL 可以保存成命令模板，后续让 agent 复用。

```powershell
ledger-cli saved-query add --db ledger.db --name echo-year --description "测试年份参数" --query "SELECT :year AS year" --parameter year
ledger-cli saved-query list --db ledger.db
ledger-cli saved-query run --db ledger.db --name echo-year --value year=2025
```

## 主要功能

- 导入序时账和科目余额表。
- 标准化公司、年度、月份、凭证、科目、借贷方金额、辅助核算等字段。
- 所有 CLI 输出 JSON，方便 agent 调用。
- 支持只读 SQL 查询，并拦截写入和管理类 SQL。
- 支持查询模板沉淀：`saved-query add/list/run`。
- 保留原始导入行 `raw_json`，方便回溯源数据。
- 使用整数分保存金额，避免浮点误差。

## 输出格式

CLI 支持三种输出格式，方便人类查看或 agent 解析：

```powershell
# agent 调用建议显式指定 JSON
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅 --format json

# 人类在终端默认看到表格；也可显式指定
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅 --format table

# 贴到 Excel
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅 --format csv
```

- TTY（人类在终端）默认 `table`。
- 非 TTY（agent、管道、CI）默认 `json`。
- 错误信息始终输出 JSON，便于 agent 识别。

## 配置文件

在项目根目录创建 `ledger-cli.toml`，减少重复参数：

```toml
[defaults]
db = "ledger.db"
format = "table"

[defaults.import]
company = "公司A"
year = 2025
```

参数优先级：**CLI flag > 配置文件 > 默认值**。

## 审计日志

所有导入、替换、删除操作都会追加写入数据库同目录的 `ledger-cli.log`，便于审计追溯。

## 测试

```powershell
python -m pytest -v
```
