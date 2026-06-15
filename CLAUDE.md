# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

`ledger-agent-cli` 是给 agent 使用的账套查询 CLI。它把序时账（GL）和科目余额表（TB）导入 SQLite，再通过固定 JSON 命令查询账套、分析变动原因、执行常见勾稽测试。agent 不直接改数据库，只调用受控 CLI。

## 常用命令

### 环境准备

```powershell
python -m pip install -e .[dev]
```

开发依赖包含 `pytest` 和 `ruff`。ruff 负责 lint 和 format，配置在 `pyproject.toml` 中。

### 测试

```powershell
# 全量测试
python -m pytest -v

# 单个测试文件
python -m pytest tests\test_import_modes.py -v

# 单个测试用例
python -m pytest tests\test_import_modes.py::test_gl_replace_mode_replaces_existing_voucher -v
```

### CLI 运行

安装后入口点为 `ledger-cli`。所有命令输出 JSON，便于 agent 解析。

```powershell
ledger-cli init --db ledger.db

ledger-cli import gl --db ledger.db --file examples\sample_gl.csv --company 公司A --year 2025 --mapping examples\mappings\gl_zh.json
ledger-cli import tb --db ledger.db --file examples\sample_tb.csv --company 公司A --year 2025 --mapping examples\mappings\tb_zh.json

ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅
ledger-cli variance tb --db ledger.db --company 公司A --year 2025 --compare-year 2024 --account 差旅费
ledger-cli trace depreciation --db ledger.db --company 公司A --year 2025
ledger-cli reconcile gl-tb --db ledger.db --company 公司A --year 2025

ledger-cli sql select --db ledger.db --query "SELECT name FROM companies"
```

### 输出格式

CLI 支持 `--format json|table|csv`：

- TTY（人类在终端）默认 `table`。
- 非 TTY（agent、管道、CI）默认 `json`。
- 错误信息始终输出 JSON。

```powershell
ledger-cli accounts search --db ledger.db --company 公司A --year 2025 --keyword 差旅 --format table
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --format json
```

### 配置文件

支持 `ledger-cli.toml` / `.ledger-cli.toml`，优先级：**CLI flag > 配置文件 > 默认值**。

```toml
[defaults]
db = "ledger.db"
format = "table"

[defaults.import]
company = "公司A"
year = 2025
```

### 导入与删除

导入默认 `--mode error`，发现重复即报错。支持 `error`、`skip`、`replace`。

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode replace
ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json --mode skip
```

删除命令默认 dry-run，只有加 `--yes` 才真正删除。

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12 --yes
ledger-cli delete batch --db ledger.db --batch-id 1 --yes
```

## 架构总览

### 分层

CLI 入口统一在 `src/ledger_agent_cli/cli.py`，使用 Typer 组织命令组。业务逻辑按职责分到四个模块：

- `importers/`：GL/TB 导入、字段映射、金额转换、导入模式（error/skip/replace）。
- `queries/`：查询与审计分析，包括科目搜索、年度差异、折旧去向、GL/TB 勾稽、保存的查询模板。
- `mutations/`：受控的数据变更，目前只有删除。
- `db.py` / `schema.sql`：SQLite 连接、事务、`import_batches` 等核心表结构。
- `output.py`：TTY 检测和 JSON/table/CSV 输出渲染。
- `config.py`：`ledger-cli.toml` 配置加载。
- `audit_log.py`：导入/删除操作的审计日志写入。
- `.claude/skills/ledger-cli.skill.md`：Claude Code 使用指南。

所有 CLI 输出都经过 `jsonio.py` 包装成统一 JSON 结构：`{ok, command, data, meta, error}`。

### 数据模型要点

- 金额全部以整数“分”存储，避免浮点误差；对外输出时通过 `cents_to_money` 转成字符串元。
- 每张 GL/TB 导入表都保留 `raw_json`，可追溯原始列值。
- `import_batches` 记录每次导入的来源文件、映射、行数，是后续按批次删除的依据。
- 唯一识别键：
  - GL 凭证：`company + year + month + voucher_no`（替换/删除以整张凭证为单位）。
  - GL 分录行：`company + year + month + voucher_no + line_no`。
  - TB 行：`company + year + month + account_code + auxiliary`（空 auxiliary 按空字符串处理）。

### 安全设计

- agent 不应直接写数据库；所有写操作通过 CLI 命令完成，便于留痕。
- `sql_guard.py` 拦截 `sql select` 中的写入/管理类 SQL，只允许 `SELECT` 和 `WITH`。
- 删除必须限定 `company` 和 `year`，可选 `month`；无 `--yes` 只返回 dry-run 结果。
- 导入重复时，`errors.py` 中的 `LedgerCliError` 会输出受控 JSON 错误码（如 `duplicate_import_scope`、`duplicate_input_scope`），不会抛出 SQLite 原生异常。

### 新增命令的常规路径

1. 在 `cli.py` 中声明 Typer 命令并解析参数。
2. 在 `importers/`、`queries/` 或 `mutations/` 中实现纯函数逻辑。
3. 用 `jsonio.success` / `jsonio.failure` 返回统一 JSON；业务异常优先继承 `LedgerCliError`。
4. 在 `tests/` 中新增测试，使用 `typer.testing.CliRunner` 调用 `app` 或直接用 `tmp_path` 调用底层函数。

### 参考资料

- `README.md`：快速开始、常用命令、测试说明。
- `docs/cli-commands.md`：全部 CLI 命令示例。
- `docs/data-model.md`：核心表与字段说明。
- `docs/agent-usage.md`：agent 使用优先级建议（先固定命令，再只读 SQL，再沉淀为 saved-query）。
- `docs/superpowers/specs/2026-06-02-incremental-import-delete-design.md`：增量导入与删除的详细设计。
