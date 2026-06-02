# 增量导入、替换和删除设计

## 目标

补上账套数据库的安全更新能力：

- 重复导入不能悄悄制造重复数据。
- 导入错了可以按批次、期间、数据类型删除。
- 需要覆盖旧数据时必须显式声明。
- 所有操作仍然通过 JSON CLI 完成，方便 agent 调用和留痕。

## 当前问题

现有版本已经有 `import_batches`，但导入行为还不完整：

- GL 凭证头有唯一约束：`company_id + year + month + voucher_no`。
- GL 分录行没有唯一约束，重复导入会继续追加分录行。
- TB 没有唯一约束，重复导入会继续追加余额表行。
- 没有受控删除命令。
- 没有导入模式，无法区分“首次导入、跳过重复、替换旧数据、重复时报错”。

## 推荐方案

默认采用保守模式：

```text
--mode error
```

也就是发现目标范围已有数据就报错，不自动覆盖。

支持三种导入模式：

- `error`：默认。目标范围已有数据就报错。
- `skip`：目标范围已有数据就跳过，不导入。
- `replace`：先删除目标范围旧数据，再导入新数据。

这样最符合审计数据处理习惯：默认不破坏旧数据，需要覆盖时必须明确写出来。

## 唯一识别口径

### 序时账 GL

第一版以凭证作为最小替换单位。

唯一识别：

```text
company + year + month + voucher_no
```

原因：

- 凭证号是用户明确提到的唯一标识。
- 一张凭证通常包含多行分录，替换时应整张凭证一起替换。
- 如果只按分录行替换，容易留下半张凭证。

后续如遇到同一月份凭证号重复，可再扩展 `voucher_type` 或 `source_system`。

### 科目余额表 TB

唯一识别：

```text
company + year + month + account_code + auxiliary
```

原因：

- 科目余额表通常每个科目每期一行。
- 有辅助核算时，同一科目可能拆成多行。
- `auxiliary` 为空时按空字符串处理。

## 导入范围判断

GL 导入前先扫描文件，得到目标凭证集合：

```text
company + year + month + voucher_no
```

然后检查数据库是否已存在这些凭证。

TB 导入前先扫描文件，得到目标余额表行集合：

```text
company + year + month + account_code + auxiliary
```

然后检查数据库是否已存在这些余额表行。

## 导入模式行为

### error

发现重复：

```json
{
  "ok": false,
  "error": {
    "code": "duplicate_import_scope",
    "message": "Target data already exists. Use --mode replace to overwrite or --mode skip to ignore.",
    "details": {
      "duplicate_count": 3
    }
  }
}
```

不写入任何新数据。

### skip

发现重复：

- 跳过重复范围。
- 只导入不存在的凭证或余额表行。
- 返回 `inserted_count`、`skipped_count`。

### replace

发现重复：

- 先删除重复范围内旧数据。
- 再插入新数据。
- 返回 `deleted_count`、`inserted_count`。

GL 的 replace 删除整张凭证：

1. 删除相关 `journal_lines`。
2. 删除相关 `journal_headers`。

TB 的 replace 删除匹配的 `trial_balance` 行。

## 删除命令

新增受控删除命令：

```powershell
ledger-cli delete batch --db ledger.db --batch-id 1
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
ledger-cli delete tb --db ledger.db --company 公司A --year 2025 --month 12
```

删除默认需要确认参数：

```powershell
--yes
```

没有 `--yes` 时只返回将删除多少数据，不真正删除。

示例：

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1
```

返回：

```json
{
  "ok": true,
  "command": "delete.gl",
  "data": {
    "dry_run": true,
    "matched_headers": 10,
    "matched_lines": 35
  }
}
```

真正删除：

```powershell
ledger-cli delete gl --db ledger.db --company 公司A --year 2025 --month 1 --yes
```

## 批次删除

`delete batch` 根据 `import_batch_id` 删除。

规则：

- GL 批次：删除该批次导入的 `journal_lines`，再删除没有分录行的 `journal_headers`。
- TB 批次：删除该批次导入的 `trial_balance`。
- 最后删除对应 `import_batches` 记录。

不自动删除 `companies` 和 `accounts`，因为这些可能被其他批次共用。

## 数据库结构调整

新增索引和唯一约束：

```sql
CREATE UNIQUE INDEX idx_journal_lines_unique_line
ON journal_lines(company_id, year, month, voucher_no, line_no);

CREATE UNIQUE INDEX idx_trial_balance_unique_row
ON trial_balance(company_id, year, month, account_code, COALESCE(auxiliary, ''));
```

SQLite 不支持在普通唯一索引表达式里跨所有版本无风险迁移时，需要用兼容写法实现；实际实现时优先采用表达式索引，测试覆盖空辅助核算。

## CLI 变化

导入命令新增参数：

```powershell
ledger-cli import gl --db ledger.db --file gl.csv --company 公司A --year 2025 --mapping gl.json --mode error
ledger-cli import tb --db ledger.db --file tb.csv --company 公司A --year 2025 --mapping tb.json --mode replace
```

默认：

```text
--mode error
```

返回结果新增：

- `inserted_count`
- `skipped_count`
- `deleted_count`
- `duplicate_count`
- `mode`

## 错误处理

- `mode` 只能是 `error`、`skip`、`replace`。
- `delete` 命令必须限定公司和年度，避免误删全库。
- `delete gl` 支持 `month` 可选；不传 month 时删除全年 GL，但必须 `--yes`。
- `delete tb` 支持 `month` 可选；不传 month 时删除全年 TB，但必须 `--yes`。
- 删除命令全部先支持 dry-run。

## 测试

需要新增测试：

- GL 重复导入默认报错。
- GL `--mode skip` 不重复插入。
- GL `--mode replace` 替换旧凭证。
- TB 重复导入默认报错。
- TB `--mode skip` 不重复插入。
- TB `--mode replace` 替换旧行。
- `delete batch` dry-run 和真实删除。
- `delete gl` dry-run 和真实删除。
- `delete tb` dry-run 和真实删除。
- 删除后查询命令不报错。

## 不做的事

第一版不做：

- 自动识别同一凭证内容是否完全一致。
- 复杂版本历史。
- 回滚到某个旧批次。
- UI 删除确认。
- 多人权限控制。

这些以后可以基于 `import_batches` 扩展。

## 验收标准

- 默认重复导入会报错。
- 明确 `--mode skip` 时不会重复插入。
- 明确 `--mode replace` 时能覆盖旧数据。
- 能按批次删除。
- 能按公司、年度、月份删除 GL/TB。
- 删除命令默认 dry-run。
- 所有命令输出 JSON。
- 全量测试通过。
