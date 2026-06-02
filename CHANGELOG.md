# 版本更新说明

## 2026-06-02 - `964af5d`

### 新增功能

- `import gl` 和 `import tb` 支持 `--mode error|skip|replace`。
- 新增 `delete gl`、`delete tb`、`delete batch`。
- 删除命令默认 dry-run，只展示将删除的数据；加 `--yes` 才真实删除。
- 新增导入唯一性保护：
  - 序时账按公司、年度、月份、凭证号识别整张凭证。
  - 序时账同一凭证内用行号防止重复分录。
  - 科目余额表按公司、年度、月份、科目编码、辅助核算识别。

### 修复内容

- 输入文件内部重复时返回受控 JSON 错误，不再等 SQLite 约束报错。
- `delete batch` 只删除目标批次的凭证头，不影响其他批次。

### 测试结果

- `python -m pytest -v`：47 passed。
- CLI 冒烟通过：初始化、导入、重复导入 skip、删除 dry-run、真实删除。

### 使用方式变化

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode skip
ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json --mode replace
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
```

## 2026-06-02 - `3a7d714` / `375efb6`

### 新增内容

- 增量导入和删除功能的 implementation plan。
- 增量导入和删除功能的设计文档。

### 设计结论

- 导入模式使用 `error`、`skip`、`replace` 三种明确策略。
- 删除能力通过受控 CLI 暴露，不让 agent 直接写数据库。
- 删除命令需要公司、年度、月份或批次号等明确范围。

## 2026-06-02 - `ff56cad`

### 新增内容

- README 改为中文版。
- 补充项目定位、快速开始、常用命令、设计思路和测试命令。

## 2026-06-02 - `175412d`

### 新增功能

- 查询模板支持命名参数。
- `saved-query add/list/run` 可沉淀和复用已验证 SQL。

### 使用方式

```powershell
ledger-cli saved-query add --db ledger.db --name echo-year --description "测试年份参数" --query "SELECT :year AS year" --parameter year
ledger-cli saved-query run --db ledger.db --name echo-year --value year=2025
```

## 2026-06-02 - `0818508`

### 新增功能

- 初始化账套数据库：`ledger-cli init`。
- 导入序时账：`ledger-cli import gl`。
- 导入科目余额表：`ledger-cli import tb`。
- 查询公司、科目、差异分析、折旧去向、序时账与余额表勾稽。
- 支持只读 SQL：`ledger-cli sql select`。
- 所有 CLI 输出 JSON，方便 agent 调用。

### 测试结果

- 已建立基础 pytest 测试集，覆盖导入、查询、SQL 防写入、勾稽和变动分析。
