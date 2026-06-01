# ledger-agent-cli

一个给 agent 用的账套查询 CLI。

它可以把序时账和科目余额表导入 SQLite，然后通过固定 JSON 命令查询账套、分析变动原因、执行常见勾稽测试。

## 快速开始

```powershell
python -m pip install -e .[dev]

ledger-cli init --db ledger.db

ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json

ledger-cli import tb --db ledger.db --file examples\sample_tb.csv --company 公司A --year 2025 --mapping examples\mappings\tb_zh.json

ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅

ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
```

## 主要功能

- 导入序时账和科目余额表
- 标准化公司、年度、月份、凭证、科目、借贷方金额、辅助核算等字段
- 所有 CLI 输出 JSON，方便 agent 调用
- 支持只读 SQL 查询，并拦截写入和管理类 SQL
- 支持查询模板沉淀：`saved-query add/list/run`
- 保留原始导入行 `raw_json`，方便回溯源数据

## 常用命令

```powershell
ledger-cli schema --db ledger.db
ledger-cli companies --db ledger.db
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 管理费用

ledger-cli variance tb --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费

ledger-cli variance gl --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费

ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025

ledger-cli reconcile gl-tb --db ledger.db --company 公司A --year 2025

ledger-cli sql select --db ledger.db --query "SELECT name FROM companies"

ledger-cli saved-query add --db ledger.db --name echo-year --description "测试年份参数" --query "SELECT :year AS year" --parameter year

ledger-cli saved-query run --db ledger.db --name echo-year --value year=2025
```

## 设计思路

agent 不直接改数据库，只调用受控 CLI：

- 高频审计问题做成固定命令
- 临时问题用 `sql select` 只读查询
- 验证过的 SQL 可沉淀成 `saved-query`
- 重要金额用整数分保存，避免浮点误差
- 后续如需 MCP，只做 CLI 的薄封装

## 测试

```powershell
python -m pytest -v
```
