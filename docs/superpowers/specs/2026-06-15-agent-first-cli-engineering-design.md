# Agent-First CLI 工程化设计

## 背景与目标

`ledger-agent-cli` 当前已具备 GL/TB 导入、查询、勾稽、安全删除等核心能力，所有命令输出 JSON，便于 agent 调用。但在实际 agent 使用中仍存在以下问题：

- 人类在终端中阅读大段 JSON 体验差。
- 缺少 CSV 模式，财务数据不方便贴入 Excel。
- agent 与人类共用同一输出，未做 TTY 区分。
- Typer 默认的「缺参数」「非法值」错误是纯文本，agent 不易自动重试。
- 每次命令都要重复写 `--db`、`--company`、`--year`。
- 缺少 lint/format/CI，代码风格依赖人工。
- 导入、删除等变更操作没有独立审计日志。

本期目标是在不破坏现有 JSON 输出结构、不改动数据库 schema、不新增审计业务命令的前提下，把 CLI 改造成对 agent 更友好、对人类也更顺手、工程化更完整的工具。

## 设计原则

1. **向后兼容**：显式 `--format json` 时，输出与现有行为完全一致；所有现有 pytest 用例继续通过。
2. **agent 优先**：非 TTY 环境下默认 JSON，错误信息结构化，缺参数时给出 `missing_flags`。
3. **人类友好**：TTY 环境下默认表格输出，带颜色；支持 CSV 导出。
4. **配置复用**：通过 `ledger-cli.toml` 设置常用默认值，减少重复参数。
5. **审计留痕**：所有导入、替换、删除操作写审计日志，与 JSON stdout 分离。

## 输出格式层

### TTY 检测与默认格式

- 通过 `sys.stdout.isatty()` 判断是否人类在终端直接运行。
- TTY → 默认 `table`。
- 非 TTY（agent、管道、CI）→ 默认 `json`。
- 显式 `--format json|table|csv` 覆盖默认行为。

### 三种输出模式

- `json`：保持现有 `{ok, command, data, meta, error}` 结构，紧凑序列化。
- `table`：使用 `rich` 库把 `data` 中的列表渲染为彩色表格；若 `data` 不是列表，则退化为键值对。
- `csv`：把 `data` 中的列表写到 stdout，表头取自字典 keys；方便贴入 Excel。

### 错误输出统一

无论当前格式是 `table` 还是 `csv`，错误统一输出 JSON，便于 agent 和人类都能明确判断失败原因。

### 涉及文件

- 新增 `src/ledger_agent_cli/output.py`：TTY 检测、格式分发、`table`/`csv` 渲染。
- 修改 `src/ledger_agent_cli/cli.py`：把 `echo_json(...)` 替换为 `render_result(...)`。
- 修改 `src/ledger_agent_cli/jsonio.py`：保留 JSON 序列化底层，作为 `output.py` 的依赖。

## 结构化错误信息

### 缺必填参数

Typer 默认抛出的 `MissingParameter` / `BadParameter` 被统一拦截，输出：

```json
{
  "ok": false,
  "command": "import.gl",
  "error": {
    "code": "missing_required_flags",
    "message": "Missing required flags: --db, --file, --company, --year, --mapping",
    "details": {
      "missing_flags": ["--db", "--file", "--company", "--year", "--mapping"]
    }
  }
}
```

### 非法枚举值

以 `--mode` 为例：

```json
{
  "ok": false,
  "command": "import.gl",
  "error": {
    "code": "invalid_import_mode",
    "message": "Import mode must be one of: error, skip, replace.",
    "details": {
      "mode": "append",
      "valid_modes": ["error", "skip", "replace"]
    }
  }
}
```

### 涉及文件

- 修改 `src/ledger_agent_cli/errors.py`：新增 `CliValidationError`、`MissingFlagsError`。
- 修改 `src/ledger_agent_cli/cli.py`：在 `exit_with_error` 中处理 Typer 校验异常。
- 修改 `src/ledger_agent_cli/importers/modes.py`：把合法枚举值写入错误 details。

## 配置文件支持

### 文件位置与优先级

支持 `ledger-cli.toml` 或 `.ledger-cli.toml`，按以下顺序查找（找到即停）：

1. 当前工作目录
2. 向上递归到项目根（含 `.git` 的目录）
3. 用户 home 目录

### 参数优先级

优先级从高到低为：CLI flag、配置文件、默认值。个别选项后续可补充 `envvar` 支持，本期以配置文件为主。

### 配置示例

```toml
[defaults]
db = "ledger.db"
format = "table"

[defaults.import]
company = "公司A"
year = 2025
```

### 加载策略

- 启动时加载一次并缓存。
- 配置中 `db` 若指向不存在的文件，不自动创建，按原有逻辑报错。
- 只提供通用默认值，不覆盖命令级特殊逻辑。

### 涉及文件

- 新增 `src/ledger_agent_cli/config.py`：配置加载、合并、缓存。
- 修改 `src/ledger_agent_cli/cli.py`：Option 默认值从配置读取。
- 新增 `ledger-cli.example.toml`：示例配置。

## Claude Code Skill 文件

为让未来进入该仓库的 Claude Code 实例快速上手，新增 `.claude/skills/ledger-cli.skill.md`。

内容覆盖：

- 项目定位：agent 安全查询账套的 CLI。
- 何时使用：需要导入/查询/勾稽/删除账套数据时优先使用 CLI，不直接写数据库。
- 典型调用链：`init → import gl/tb → accounts search / variance / trace / reconcile → saved-query`。
- 导入模式：`error`（默认）、`skip`、`replace`。
- 删除流程：先不带 `--yes` dry-run，确认后再带 `--yes` 执行。
- 输出格式建议：agent 调用时显式 `--format json`。
- 配置文件：优先检查 `ledger-cli.toml` 是否有默认 `db`。

## Lint / Format / CI

### 工具选择

- `ruff`：同时承担 lint 和 format，速度快，配置简单。
- 配置统一写入 `pyproject.toml`，不新增 `.ruff.toml`。

### CI Workflow

新增 `.github/workflows/ci.yml`，在 push 和 pull_request 时执行：

1. `ruff check src tests`
2. `ruff format --check src tests`
3. `python -m pytest -v`

### 对现有代码的处理

- 引入 ruff 后首次跑 format 会改动大量文件，作为单独提交，避免与功能改动混交。
- 不强制本地 pre-commit hook。

## 操作审计日志

### 记录范围

所有变更类操作：

- `import gl`
- `import tb`
- `delete gl`
- `delete tb`
- `delete batch`

### 日志字段

- `timestamp`：ISO 8601
- `command`：完整命令名，如 `import.gl`
- `arguments`：关键参数（不含敏感信息）
- `result_summary`：影响行数、批次号、模式
- `success`：是否成功

### 日志位置

与数据库同目录，文件名为 `ledger-cli.log`（若配置中指定了 db 路径，则取同目录）。

### 与 stdout 隔离

日志只写文件，不写 stdout/stderr，确保 JSON/table/csv 输出不受污染。

### 涉及文件

- 新增 `src/ledger_agent_cli/audit_log.py`：日志写入、格式化。
- 修改 `src/ledger_agent_cli/importers/gl.py`、`importers/tb.py`、`mutations/delete.py`：在操作成功后写审计日志。

## 本期明确不做

- 不修改 `schema.sql` 和数据库结构。
- 不新增审计业务命令（如抽样、异常检测、重要性水平、工作底稿导出），留到二期。
- 不引入 MCP server、REST API 或 Web UI。
- 不改动现有唯一识别键逻辑（GL 按凭证、TB 按科目+辅助核算）。
- 不破坏现有 JSON 输出结构。

## 验收标准

- TTY 下默认表格输出，非 TTY 下默认 JSON。
- `--format json|table|csv` 三个模式都能正常工作。
- 缺必填参数时返回 `missing_required_flags` 错误并列出缺失 flags。
- `--mode` 非法时返回 `valid_modes`。
- `ledger-cli.toml` 中的默认值能被各命令正确读取。
- `.claude/skills/ledger-cli.skill.md` 能被识别并包含核心使用模式。
- GitHub Actions 跑通 ruff + pytest。
- 导入/删除操作后 `ledger-cli.log` 出现对应记录。
- 全量 `python -m pytest -v` 通过。
- 现有 agent 调用方式（显式 `--format json`）输出与改造前一致。

## 参考资料

- [Building a CLI That Works for Humans and Machines](https://www.openstatus.dev/blog/building-cli-for-human-and-agents)
- [Making your CLI agent-friendly](https://www.speakeasy.com/blog/engineering-agent-friendly-cli)
- [Designing CLIs for AI Agents: Patterns That Work in 2026](https://medium.com/@dminhk/designing-clis-for-ai-agents-patterns-that-work-in-2026-29ac725850de)
- 项目现有 `docs/agent-usage.md`、`docs/cli-commands.md`、`docs/data-model.md`
